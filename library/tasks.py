from celery import shared_task

from library.adapters import fetch_metadata_from_url
from library.models import ModelFile, SavedModel


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def enrich_model_metadata(self, model_id: int) -> str:
    model = SavedModel.objects.filter(pk=model_id, source_type=SavedModel.SourceType.LINK).first()
    if not model or not model.source_url:
        return "skipped"

    fetched = fetch_metadata_from_url(model.source_url)

    model.title = fetched.title or model.title
    model.designer = fetched.designer or model.designer
    model.license = fetched.license or model.license
    model.thumbnail_url = fetched.thumbnail_url or model.thumbnail_url
    model.source_site = fetched.source_site or model.source_site
    model.external_id = fetched.external_id or model.external_id
    model.metadata = {**model.metadata, **fetched.metadata, "fetch_status": "complete"}
    model.save(
        update_fields=[
            "title",
            "designer",
            "license",
            "thumbnail_url",
            "source_site",
            "external_id",
            "metadata",
            "updated_at",
        ]
    )
    return f"enriched:{model_id}"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def analyze_model_file(self, file_id: int) -> str:
    model_file = ModelFile.objects.select_related("model").filter(pk=file_id).first()
    if not model_file or not model_file.file:
        return "skipped"

    from library.stl_analysis import analyze_stl_file

    analysis = analyze_stl_file(model_file.file.path)
    data = analysis.as_dict()

    model_file.file_size = data["file_size"]
    model_file.triangle_count = data["triangle_count"]
    model_file.dimension_x = data["dimension_x"]
    model_file.dimension_y = data["dimension_y"]
    model_file.dimension_z = data["dimension_z"]
    model_file.volume_cm3 = data["volume_cm3"]
    model_file.analysis = data
    model_file.save()

    meta = model_file.model.metadata or {}
    meta["file_analysis"] = data
    model_file.model.metadata = meta
    model_file.model.save(update_fields=["metadata", "updated_at"])
    return f"analyzed:{file_id}"
