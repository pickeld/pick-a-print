import re
import uuid
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from library.adapters import detect_source_site, fetch_metadata_from_url
from library.adapters.base import FetchedMetadata, canonicalize_model_url, normalize_url
from library.models import Collection, ModelFile, ModelStatus, SavedModel, SourceType, Tag


class ModelSaveError(Exception):
    pass


def _queue_metadata_enrichment(model_id: int) -> None:
    try:
        from library.tasks import enrich_model_metadata

        enrich_model_metadata.delay(model_id)
    except Exception:
        # Celery/Redis unavailable — sync enrich as fallback
        try:
            enrich_model_metadata(model_id)
        except Exception:
            pass


def _queue_model_download(model_id: int) -> None:
    try:
        from library.tasks import download_model_files

        download_model_files.delay(model_id)
    except Exception:
        try:
            download_model_files(model_id)
        except Exception:
            pass


def _queue_file_analysis(file_id: int) -> None:
    try:
        from library.tasks import analyze_model_file

        analyze_model_file.delay(file_id)
    except Exception:
        try:
            analyze_model_file(file_id)
        except Exception:
            pass


@transaction.atomic
def save_model_from_url(
    *,
    user,
    url: str,
    collection_ids: list[int] | None = None,
    tag_names: list[str] | None = None,
    status: str | None = None,
    fetch_sync: bool = False,
) -> SavedModel:
    try:
        normalized_url = canonicalize_model_url(normalize_url(url))
    except ValueError as exc:
        raise ModelSaveError("Invalid URL") from exc

    fetched = None
    try:
        fetched = fetch_metadata_from_url(normalized_url)
    except Exception:
        fetched = None

    if fetched is None:
        fetched = FetchedMetadata(
            title=_title_from_url(normalized_url),
            source_site=detect_source_site(normalized_url),
            metadata={"fetch_status": "pending", "download_status": "pending"},
        )
    elif fetched.metadata.get("download_status") is None:
        fetched.metadata = {**fetched.metadata, "download_status": "pending"}

    lookup = {"user": user, "source_url": normalized_url}
    defaults = {
        "source_type": SourceType.LINK,
        "title": fetched.title or normalized_url,
        "designer": fetched.designer,
        "license": fetched.license,
        "thumbnail_url": fetched.thumbnail_url,
        "source_site": fetched.source_site,
        "external_id": fetched.external_id,
        "metadata": fetched.metadata,
    }
    if status:
        defaults["status"] = status

    model, created = SavedModel.objects.update_or_create(**lookup, defaults=defaults)
    _apply_tags_and_collections(model, user, tag_names, collection_ids)

    if model.metadata.get("fetch_status") != "complete":
        _queue_metadata_enrichment(model.id)

    if model.source_type == SourceType.LINK and not model.files.exists():
        _queue_model_download(model.id)

    model._was_created = created  # type: ignore[attr-defined]
    return model


@transaction.atomic
def save_model_from_upload(
    *,
    user,
    uploaded_file: UploadedFile,
    title: str | None = None,
    collection_ids: list[int] | None = None,
    tag_names: list[str] | None = None,
    status: str | None = None,
) -> SavedModel:
    from library.downloads import MODEL_UPLOAD_EXTENSIONS

    original_name = uploaded_file.name or "model.stl"
    ext = Path(original_name).suffix.lower()
    if ext not in MODEL_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(e.lstrip(".") for e in MODEL_UPLOAD_EXTENSIONS))
        raise ModelSaveError(f"Only {allowed} files are supported for upload")
    ext = ext.lstrip(".")

    upload_id = uuid.uuid4()
    model = SavedModel.objects.create(
        user=user,
        source_type=SourceType.UPLOAD,
        source_url=f"upload://{upload_id}",
        title=title or Path(original_name).stem.replace("_", " ").replace("-", " ").title(),
        source_site="upload",
        status=status or ModelStatus.SAVED,
        metadata={"fetch_status": "upload", "original_filename": original_name},
    )

    model_file = ModelFile.objects.create(
        model=model,
        file=uploaded_file,
        file_type=ext,
        original_name=original_name,
        file_size=uploaded_file.size or 0,
    )

    _apply_tags_and_collections(model, user, tag_names, collection_ids)
    _queue_file_analysis(model_file.id)

    model._was_created = True  # type: ignore[attr-defined]
    return model


def _apply_tags_and_collections(model, user, tag_names, collection_ids):
    if tag_names:
        tags = []
        for name in tag_names:
            clean = name.strip()
            if not clean:
                continue
            tag, _ = Tag.objects.get_or_create(user=user, name=clean)
            tags.append(tag)
        if tags:
            model.tags.add(*tags)

    if collection_ids:
        collections = Collection.objects.filter(user=user, id__in=collection_ids)
        model.collections.add(*collections)


def _title_from_url(url: str) -> str:
    match = re.search(r"/model/\d+-([^/]+)", url)
    if match:
        return match.group(1).replace("-", " ").replace("_", " ").title()
    path = url.rstrip("/").split("/")[-1]
    return path.replace("-", " ").replace("_", " ").title() or url


def repair_model_display_fields(model: SavedModel) -> bool:
    """Normalize title/designer for link models saved before site parsers were updated."""
    if model.source_type != SourceType.LINK:
        return False

    site = (model.source_site or "").lower()
    platform = (model.metadata or {}).get("platform", "")
    raw_title = model.title or ""
    designer = (model.designer or "").strip()

    parsed_title = raw_title
    parsed_designer = designer

    if "printables" in site or platform == "printables":
        from library.adapters.sites import PrintablesAdapter

        parsed_title, parsed_designer = PrintablesAdapter()._parse_printables_title(raw_title)

    if not parsed_designer:
        author = (model.metadata or {}).get("author")
        if isinstance(author, dict):
            parsed_designer = str(author.get("name") or "").strip()
        elif isinstance(author, str):
            parsed_designer = author.strip()

    update_fields: list[str] = []
    if parsed_title and parsed_title != raw_title:
        model.title = parsed_title
        update_fields.append("title")
    if parsed_designer and not designer:
        model.designer = parsed_designer
        update_fields.append("designer")

    if not update_fields:
        return False

    model.save(update_fields=[*update_fields, "updated_at"])
    return True
