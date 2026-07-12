import uuid
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from library.adapters import detect_source_site, fetch_metadata_from_url
from library.adapters.base import FetchedMetadata, normalize_url
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
        normalized_url = normalize_url(url)
    except ValueError as exc:
        raise ModelSaveError("Invalid URL") from exc

    fetched = None
    if fetch_sync:
        try:
            fetched = fetch_metadata_from_url(normalized_url)
        except Exception:
            fetched = None

    if fetched is None:
        fetched = FetchedMetadata(
            title=_title_from_url(normalized_url),
            source_site=detect_source_site(normalized_url),
            metadata={"fetch_status": "pending"},
        )

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
    original_name = uploaded_file.name or "model.stl"
    ext = Path(original_name).suffix.lower().lstrip(".")
    if ext not in ("stl",):
        raise ModelSaveError("Only STL files are supported for now")

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
    path = url.rstrip("/").split("/")[-1]
    return path.replace("-", " ").replace("_", " ").title() or url
