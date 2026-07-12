from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token

from library.forms import CollectionForm, LoginForm, ModelUpdateForm, SaveModelForm, ScanUploadForm, SearchForm, UploadModelForm
from library.models import Collection, ModelFile, ModelStatus, SavedModel, ScanJob
from library.scan_services import (
    ScanError,
    build_status_payload,
    create_scan_job,
    get_pipeline_steps,
    get_scan_outputs,
    import_scan_to_library,
    sync_scan_job,
    workspace_root,
)
from app.pipeline.workspace import JobWorkspace
from library.services import ModelSaveError, save_model_from_upload, save_model_from_url


def _user_collections(user):
    return Collection.objects.filter(user=user).annotate(model_count=Count("models"))


def _parse_bulk_delete_ids(request):
    try:
        return [int(value) for value in request.POST.getlist("model_ids")]
    except ValueError:
        return None


def _redirect_with_query(request):
    if request.GET:
        return redirect(f"{request.path}?{request.GET.urlencode()}")
    return redirect(request.path)


def _handle_bulk_delete(request, queryset, *, empty_message="Select at least one model to delete."):
    model_ids = _parse_bulk_delete_ids(request)
    if model_ids is None:
        messages.error(request, "Invalid selection.")
        return None

    if not model_ids:
        messages.error(request, empty_message)
        return None

    to_delete = queryset.filter(pk__in=model_ids)
    count = to_delete.count()
    if count == 0:
        messages.error(request, "No matching models found.")
        return None

    to_delete.delete()
    label = "model" if count == 1 else "models"
    messages.success(request, f"Deleted {count} {label} from your library.")
    return count


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "home")

    return render(request, "library/login.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def home_view(request):
    recent = (
        SavedModel.objects.filter(user=request.user)
        .prefetch_related("tags")
        .order_by("-created_at")[:12]
    )
    collections = _user_collections(request.user)[:8]
    stats = {
        "total": SavedModel.objects.filter(user=request.user).count(),
        "saved": SavedModel.objects.filter(user=request.user, status=ModelStatus.SAVED).count(),
        "printed": SavedModel.objects.filter(user=request.user, status=ModelStatus.PRINTED).count(),
    }
    return render(
        request,
        "library/home.html",
        {"recent": recent, "collections": collections, "stats": stats},
    )


@login_required
@require_http_methods(["GET", "POST"])
def models_list_view(request):
    form = SearchForm(request.GET or None)
    queryset = SavedModel.objects.filter(user=request.user).prefetch_related("tags", "collections")

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    source_site = request.GET.get("source_site", "").strip()

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(designer__icontains=q)
            | Q(source_site__icontains=q)
            | Q(tags__name__icontains=q)
        ).distinct()
    if status:
        queryset = queryset.filter(status=status)
    if source_site:
        queryset = queryset.filter(source_site__icontains=source_site)

    if request.method == "POST" and "bulk_delete" in request.POST:
        if _handle_bulk_delete(request, queryset) is not None:
            return _redirect_with_query(request)
        return _redirect_with_query(request)

    return render(
        request,
        "library/models_list.html",
        {"models": queryset, "form": form, "query": q},
    )


@login_required
@require_http_methods(["GET", "POST"])
def model_save_view(request):
    url_form = SaveModelForm(request.POST or None, user=request.user, prefix="url")
    upload_form = UploadModelForm(request.POST or None, request.FILES or None, user=request.user, prefix="upload")
    active_tab = request.GET.get("tab", "url")

    if request.method == "POST":
        if "save_url" in request.POST:
            active_tab = "url"
            if url_form.is_valid():
                tag_names = [t.strip() for t in url_form.cleaned_data["tag_names"].split(",") if t.strip()]
                collection_ids = list(url_form.cleaned_data["collections"].values_list("id", flat=True))
                try:
                    model = save_model_from_url(
                        user=request.user,
                        url=url_form.cleaned_data["url"],
                        collection_ids=collection_ids or None,
                        tag_names=tag_names or None,
                        status=url_form.cleaned_data.get("status"),
                    )
                except ModelSaveError as exc:
                    messages.error(request, str(exc))
                else:
                    verb = "saved" if getattr(model, "_was_created", True) else "updated"
                    messages.success(request, f'"{model.title}" {verb} to your library.')
                    return redirect("model_detail", pk=model.pk)

        elif "save_upload" in request.POST:
            active_tab = "upload"
            if upload_form.is_valid():
                tag_names = [t.strip() for t in upload_form.cleaned_data["tag_names"].split(",") if t.strip()]
                collection_ids = list(upload_form.cleaned_data["collections"].values_list("id", flat=True))
                try:
                    model = save_model_from_upload(
                        user=request.user,
                        uploaded_file=upload_form.cleaned_data["file"],
                        title=upload_form.cleaned_data.get("title") or None,
                        collection_ids=collection_ids or None,
                        tag_names=tag_names or None,
                    )
                except ModelSaveError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, f'"{model.title}" uploaded to your library.')
                    return redirect("model_detail", pk=model.pk)
            elif upload_form.errors.get("file"):
                messages.error(request, "Choose an STL file before uploading.")

    return render(
        request,
        "library/model_save.html",
        {
            "url_form": url_form,
            "upload_form": upload_form,
            "active_tab": active_tab,
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        },
    )


@login_required
def settings_view(request):
    active_tab = request.GET.get("tab", "api")
    if active_tab not in ("api", "about", "downloads"):
        active_tab = "api"

    token, _ = Token.objects.get_or_create(user=request.user)
    api_base = request.build_absolute_uri("/api").rstrip("/")

    from django.conf import settings as django_settings

    context = {
        "api_token": token.key,
        "api_base": api_base,
        "active_tab": active_tab,
        "download_integrations": [
            {"site": "Printables", "status": "ready", "note": "Works out of the box"},
            {"site": "Thangs", "status": "ready", "note": "May be blocked by Cloudflare from some servers"},
            {
                "site": "MakerWorld",
                "status": "configured" if django_settings.BAMBU_LAB_TOKEN else "needs_token",
                "note": "Set BAMBU_LAB_TOKEN (MakerWorld cookie: token)",
            },
            {
                "site": "Thingiverse",
                "status": "configured" if django_settings.THINGIVERSE_API_TOKEN else "needs_token",
                "note": "Set THINGIVERSE_API_TOKEN from thingiverse.com/apps",
            },
            {
                "site": "MyMiniFactory",
                "status": "configured" if django_settings.MYMINIFACTORY_API_KEY else "needs_token",
                "note": "Set MYMINIFACTORY_API_KEY from myminifactory.com API",
            },
            {"site": "Cults3D", "status": "unsupported", "note": "Metadata only — Cults does not expose file downloads via API"},
        ],
    }

    from library.dependency_info import CACHE_TTL_SECONDS, get_cached_updates_available, peek_cached_about

    context["updates_available"] = get_cached_updates_available()

    if active_tab == "about":
        from library.dependency_info import DOCKER_IMAGES, PIPELINE_TOOLS, _load_image_versions

        context["about_cached"] = peek_cached_about()
        context["cache_ttl_minutes"] = CACHE_TTL_SECONDS // 60
        context["docker_manifest"] = DOCKER_IMAGES
        context["tools_manifest"] = PIPELINE_TOOLS
        context["image_versions"] = _load_image_versions()

    return render(request, "library/settings.html", context)


@login_required
def about_checks_view(request):
    from library.dependency_info import fetch_about_data

    refresh = request.GET.get("refresh") == "1"
    return JsonResponse(fetch_about_data(refresh=refresh))


@login_required
@require_http_methods(["GET", "POST"])
def model_detail_view(request, pk):
    model = get_object_or_404(
        SavedModel.objects.prefetch_related("tags", "collections", "files"),
        pk=pk,
        user=request.user,
    )
    form = ModelUpdateForm(request.POST or None, instance=model, user=request.user)

    if request.method == "POST":
        if "delete" in request.POST:
            title = model.title
            model.delete()
            messages.success(request, f'"{title}" removed from library.')
            return redirect("home")

        if form.is_valid():
            form.save()
            messages.success(request, "Model updated.")
            return redirect("model_detail", pk=model.pk)

    return render(request, "library/model_detail.html", {"model": model, "form": form, "preview_file": _preview_file_for_model(model)})


def _preview_file_for_model(model: SavedModel) -> ModelFile | None:
    return model.files.filter(file_type__in=["stl", "3mf"]).first()


@login_required
def model_preview_view(request, pk, file_id):
    model = get_object_or_404(SavedModel, pk=pk, user=request.user)
    model_file = get_object_or_404(ModelFile, pk=file_id, model=model, file_type__in=["stl", "3mf"])

    from pathlib import Path

    from library.stl_preview import ensure_preview_glb

    glb_path = ensure_preview_glb(Path(model_file.file.path))
    if not glb_path:
        messages.error(request, "Could not generate a 3D preview for this file.")
        return redirect("model_detail", pk=model.pk)

    inline = request.GET.get("inline") == "1"
    response = FileResponse(
        glb_path.open("rb"),
        as_attachment=not inline,
        filename=glb_path.name,
        content_type="model/gltf-binary",
    )
    if inline:
        response["Cache-Control"] = "private, max-age=3600"
    return response


@login_required
def collections_list_view(request):
    collections = _user_collections(request.user)
    form = CollectionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        collection = form.save(commit=False)
        collection.user = request.user
        collection.save()
        messages.success(request, f'Collection "{collection.name}" created.')
        return redirect("collection_detail", slug=collection.slug)

    return render(
        request,
        "library/collections_list.html",
        {"collections": collections, "form": form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def collection_detail_view(request, slug):
    collection = get_object_or_404(Collection, slug=slug, user=request.user)
    models = collection.models.filter(user=request.user).prefetch_related("tags").order_by("-created_at")

    if request.method == "POST" and "bulk_delete" in request.POST:
        scoped = SavedModel.objects.filter(user=request.user, collections=collection)
        if _handle_bulk_delete(request, scoped) is not None:
            return redirect("collection_detail", slug=collection.slug)
        return redirect("collection_detail", slug=collection.slug)

    return render(
        request,
        "library/collection_detail.html",
        {"collection": collection, "models": models},
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_list_view(request):
    form = ScanUploadForm(request.POST or None, user=request.user)
    recent = ScanJob.objects.filter(user=request.user).select_related("saved_model")[:12]

    if request.method == "POST":
        files = request.FILES.getlist("files")
        if form.is_valid():
            tag_names = [t.strip() for t in form.cleaned_data["tag_names"].split(",") if t.strip()]
            collection_ids = list(form.cleaned_data["collections"].values_list("id", flat=True))
            try:
                scan_job = create_scan_job(
                    user=request.user,
                    files=files,
                    title=form.cleaned_data.get("title") or None,
                    tag_names=tag_names or None,
                    collection_ids=collection_ids or None,
                )
            except ScanError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Scan started. Track progress below.")
                return redirect("scan_job", job_id=scan_job.job_id)

    return render(
        request,
        "library/scan.html",
        {
            "form": form,
            "recent": recent,
            "pipeline_steps": get_pipeline_steps(),
        },
    )


@login_required
def scan_job_view(request, job_id):
    scan_job = get_object_or_404(ScanJob, job_id=job_id, user=request.user)
    sync_scan_job(scan_job)
    status = build_status_payload(scan_job)
    return render(
        request,
        "library/scan_job.html",
        {
            "scan_job": scan_job,
            "status": status,
            "pipeline_steps": status["steps"],
        },
    )


@login_required
def scan_status_view(request, job_id):
    scan_job = get_object_or_404(ScanJob, job_id=job_id, user=request.user)
    return JsonResponse(build_status_payload(scan_job))


@login_required
@require_http_methods(["POST"])
def scan_import_view(request, job_id):
    scan_job = get_object_or_404(ScanJob, job_id=job_id, user=request.user)
    try:
        scan_job = import_scan_to_library(scan_job)
    except ScanError as exc:
        messages.error(request, str(exc))
        return redirect("scan_job", job_id=scan_job.job_id)

    messages.success(request, f'"{scan_job.title}" saved to your library.')
    return redirect("model_detail", pk=scan_job.saved_model_id)


@login_required
def scan_download_view(request, job_id, filename):
    scan_job = get_object_or_404(ScanJob, job_id=job_id, user=request.user)
    outputs = get_scan_outputs(scan_job)
    path = next((p for p in outputs.values() if p.name == filename), None)
    if not path:
        messages.error(request, "File not found.")
        return redirect("scan_job", job_id=scan_job.job_id)

    try:
        path.resolve().relative_to(
            JobWorkspace(workspace_root(), str(scan_job.job_id)).output_dir.resolve()
        )
    except ValueError as exc:
        messages.error(request, "Invalid file.")
        return redirect("scan_job", job_id=scan_job.job_id)

    media_types = {
        ".stl": "model/stl",
        ".glb": "model/gltf-binary",
        ".ply": "application/octet-stream",
        ".obj": "text/plain",
        ".json": "application/json",
    }
    inline = request.GET.get("inline") == "1"
    response = FileResponse(
        path.open("rb"),
        as_attachment=not inline,
        filename=path.name,
        content_type=media_types.get(path.suffix.lower(), "application/octet-stream"),
    )
    if inline:
        response["Cache-Control"] = "private, max-age=3600"
    return response
