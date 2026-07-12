from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token

from library.forms import CollectionForm, LoginForm, ModelUpdateForm, SaveModelForm, ScanUploadForm, SearchForm, UploadModelForm
from library.models import Collection, ModelStatus, SavedModel, ScanJob
from library.scan_services import (
    ScanError,
    build_status_payload,
    create_scan_job,
    get_pipeline_steps,
    get_scan_outputs,
    import_scan_to_library,
    sync_scan_job,
)
from library.services import ModelSaveError, save_model_from_upload, save_model_from_url


def _user_collections(user):
    return Collection.objects.filter(user=user).annotate(model_count=Count("models"))


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
        if "save_url" in request.POST and url_form.is_valid():
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
            active_tab = "url"

        elif "save_upload" in request.POST and upload_form.is_valid():
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
            active_tab = "upload"

    return render(
        request,
        "library/model_save.html",
        {"url_form": url_form, "upload_form": upload_form, "active_tab": active_tab},
    )


@login_required
def settings_view(request):
    active_tab = request.GET.get("tab", "api")
    if active_tab not in ("api", "about"):
        active_tab = "api"

    token, _ = Token.objects.get_or_create(user=request.user)
    api_base = request.build_absolute_uri("/api").rstrip("/")

    context = {
        "api_token": token.key,
        "api_base": api_base,
        "active_tab": active_tab,
    }

    from library.dependency_info import get_about_context, get_cached_updates_available

    context["updates_available"] = get_cached_updates_available()

    if active_tab == "about":
        refresh = request.GET.get("refresh") == "1"
        about = get_about_context(refresh=refresh)
        context.update(about)
        context["updates_available"] = about["updates_available"]

    return render(request, "library/settings.html", context)


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

    return render(request, "library/model_detail.html", {"model": model, "form": form})


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
def collection_detail_view(request, slug):
    collection = get_object_or_404(Collection, slug=slug, user=request.user)
    models = collection.models.prefetch_related("tags").order_by("-created_at")
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

    media_types = {
        ".stl": "model/stl",
        ".glb": "model/gltf-binary",
        ".ply": "application/octet-stream",
        ".obj": "text/plain",
        ".json": "application/json",
    }
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type=media_types.get(path.suffix.lower(), "application/octet-stream"))
