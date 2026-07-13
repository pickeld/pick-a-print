from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.contrib.staticfiles import finders
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from pathlib import Path
from rest_framework.authtoken.models import Token

from library.forms import CollectionForm, LoginForm, ModelUpdateForm, SaveModelForm, ScanUploadForm, SearchForm, UploadModelForm
from library.models import Collection, ModelFile, ModelStatus, SavedModel, ScanJob, SiteConfig
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
from library.pwa_manifest import build_manifest
from library.pwa_share import process_share_import
from library.chunk_upload import (
    AssembledScanFile,
    cleanup_chunk_upload,
    complete_scan_chunk_upload,
    save_scan_chunk,
)
from library.scan_worker import (
    ScanWorkerTestResult,
    count_celery_scan_workers,
    normalize_jetson_host,
    run_jetson_connection_test,
    save_connection_test_result,
    scan_worker_status,
    validate_jetson_health_token,
    validate_jetson_host,
)
from library.provider_credentials import bambu_lab_token, myminifactory_api_key, thingiverse_api_token


def _parse_scan_worker_payload(request) -> dict:
    if request.content_type == "application/json":
        try:
            return json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST


def _apply_scan_worker_fields(config: SiteConfig, payload: dict) -> str | None:
    config.jetson_host = normalize_jetson_host(str(payload.get("jetson_host", "")))
    try:
        config.jetson_health_port = max(1, min(65535, int(payload.get("jetson_health_port", 8765))))
    except (TypeError, ValueError):
        config.jetson_health_port = 8765
    config.jetson_enabled = bool(payload.get("jetson_enabled"))

    if "jetson_health_token" in payload:
        token_value = str(payload.get("jetson_health_token", "")).strip()
        if token_value:
            config.jetson_health_token = token_value

    if config.jetson_enabled:
        host_error = validate_jetson_host(config.jetson_host)
        if host_error:
            return host_error
        return validate_jetson_health_token(config.jetson_health_token)
    return None


def _apply_download_integration_fields(config: SiteConfig, payload: dict) -> None:
    token_fields = (
        "thingiverse_api_token",
        "bambu_lab_token",
        "myminifactory_api_key",
    )
    for field_name in token_fields:
        if field_name not in payload:
            continue
        token_value = str(payload.get(field_name, "")).strip()
        if token_value:
            setattr(config, field_name, token_value)


def _download_integrations_status() -> list[dict]:
    return [
        {"site": "Printables", "status": "ready", "note": "Works out of the box"},
        {"site": "Thangs", "status": "ready", "note": "May be blocked by Cloudflare from some servers"},
        {
            "site": "MakerWorld",
            "status": "configured" if bambu_lab_token() else "needs_token",
            "note": "Bambu Lab token from MakerWorld browser cookie (token)",
        },
        {
            "site": "Thingiverse",
            "status": "configured" if thingiverse_api_token() else "needs_token",
            "note": "API token from thingiverse.com/apps",
        },
        {
            "site": "MyMiniFactory",
            "status": "configured" if myminifactory_api_key() else "needs_token",
            "note": "API key from myminifactory.com",
        },
        {"site": "Cults3D", "status": "unsupported", "note": "Metadata only — Cults does not expose file downloads via API"},
    ]


def _user_collections(user):
    return Collection.objects.filter(user=user).annotate(model_count=Count("models"))


def _parse_bulk_delete_ids(request):
    try:
        return [int(value) for value in request.POST.getlist("model_ids")]
    except ValueError:
        return None


def _parse_file_ids(request):
    try:
        return [int(value) for value in request.POST.getlist("file_ids")]
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


def _handle_bulk_delete_files(request, model: SavedModel, *, empty_message="Select at least one part to delete."):
    file_ids = _parse_file_ids(request)
    if file_ids is None:
        messages.error(request, "Invalid selection.")
        return None

    if not file_ids:
        messages.error(request, empty_message)
        return None

    to_delete = model.files.filter(pk__in=file_ids)
    count = to_delete.count()
    if count == 0:
        messages.error(request, "No matching parts found.")
        return None

    to_delete.delete()
    label = "part" if count == 1 else "parts"
    messages.success(request, f"Deleted {count} {label}.")
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
                messages.error(request, "Choose a model file (.stl or .3mf) before uploading.")

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
    if active_tab not in ("api", "about", "downloads", "app", "scan"):
        active_tab = "api"

    if active_tab == "scan" and request.method == "POST" and "save_scan_worker" in request.POST:
        config = SiteConfig.get()
        error = _apply_scan_worker_fields(config, request.POST)
        if error:
            messages.error(request, error)
        else:
            config.save()
            messages.success(request, "Scan worker settings saved.")
        return redirect(f"{reverse('settings')}?tab=scan")

    token, _ = Token.objects.get_or_create(user=request.user)
    api_base = request.build_absolute_uri("/api").rstrip("/")

    context = {
        "api_token": token.key,
        "api_base": api_base,
        "active_tab": active_tab,
        "download_integrations": _download_integrations_status(),
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

    if active_tab == "downloads":
        config = SiteConfig.get()
        context["download_config"] = {
            "thingiverse_api_token": bool(config.thingiverse_api_token),
            "bambu_lab_token": bool(config.bambu_lab_token),
            "myminifactory_api_key": bool(config.myminifactory_api_key),
        }

    if active_tab == "scan":
        config = SiteConfig.get()
        context["scan_worker_config"] = config
        context["scan_worker_status"] = scan_worker_status()
        context["scan_worker_status_json"] = json.dumps(context["scan_worker_status"])

    return render(request, "library/settings.html", context)


@login_required
@require_http_methods(["POST"])
def download_integrations_save_view(request):
    config = SiteConfig.get()
    payload = _parse_scan_worker_payload(request)
    _apply_download_integration_fields(config, payload)
    config.save()
    return JsonResponse(
        {
            "ok": True,
            "message": "Download provider settings saved.",
            "integrations": _download_integrations_status(),
            "saved": {
                "thingiverse_api_token": bool(config.thingiverse_api_token),
                "bambu_lab_token": bool(config.bambu_lab_token),
                "myminifactory_api_key": bool(config.myminifactory_api_key),
            },
        }
    )


@login_required
@require_http_methods(["POST"])
def scan_worker_save_view(request):
    config = SiteConfig.get()
    payload = _parse_scan_worker_payload(request)
    error = _apply_scan_worker_fields(config, payload)
    if error:
        return JsonResponse({"ok": False, "message": error}, status=400)

    config.save()
    status = scan_worker_status()
    return JsonResponse(
        {
            "ok": True,
            "message": "Scan worker settings saved.",
            **status,
        }
    )


@login_required
@require_http_methods(["POST"])
def scan_worker_check_view(request):
    config = SiteConfig.get()
    payload = _parse_scan_worker_payload(request)
    error = _apply_scan_worker_fields(config, payload)
    if error and config.jetson_enabled:
        return JsonResponse({"ok": False, "message": error}, status=400)
    config.save()

    host_reachable = False
    if config.jetson_enabled:
        result = run_jetson_connection_test(
            host=config.jetson_host,
            port=config.jetson_health_port,
            token=config.jetson_health_token,
        )
        host_reachable = result.host_reachable
        save_connection_test_result(config, result)
    else:
        worker_count, worker_error = count_celery_scan_workers()
        result_ok = worker_count > 0
        message = (
            f"{worker_count} scan worker(s) connected."
            if result_ok
            else worker_error or "No scan worker is connected to Redis."
        )
        save_connection_test_result(
            config,
            ScanWorkerTestResult(
                ok=result_ok,
                host_reachable=False,
                celery_workers=worker_count,
                message=message,
            ),
        )

    status = scan_worker_status()
    return JsonResponse(
        {
            "ok": status["last_test_ok"],
            "host_reachable": host_reachable,
            "message": status["last_test_message"],
            **status,
        }
    )


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
        if "bulk_delete_files" in request.POST:
            if _handle_bulk_delete_files(request, model) is not None:
                return redirect("model_detail", pk=model.pk)
            return redirect("model_detail", pk=model.pk)

        if "delete" in request.POST:
            title = model.title
            model.delete()
            messages.success(request, f'"{title}" removed from library.')
            return redirect("home")

        if form.is_valid():
            form.save()
            messages.success(request, "Model updated.")
            return redirect("model_detail", pk=model.pk)

    preview_files = _preview_files_for_model(model)
    model_files = list(model.files.order_by("original_name"))
    preview_file = preview_files[0] if preview_files else None
    return render(
        request,
        "library/model_detail.html",
        {
            "model": model,
            "form": form,
            "preview_files": preview_files,
            "preview_file": preview_file,
            "model_files": model_files,
        },
    )


def _preview_files_for_model(model: SavedModel) -> list[ModelFile]:
    return list(model.files.filter(file_type__in=["stl", "3mf"]).order_by("original_name"))


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
@require_http_methods(["POST"])
def model_files_download_view(request, pk):
    import io
    import zipfile

    model = get_object_or_404(SavedModel, pk=pk, user=request.user)
    file_ids = _parse_file_ids(request)
    if file_ids is None:
        messages.error(request, "Invalid selection.")
        return redirect("model_detail", pk=model.pk)

    if not file_ids:
        messages.error(request, "Select at least one part to download.")
        return redirect("model_detail", pk=model.pk)

    files = list(model.files.filter(pk__in=file_ids).order_by("original_name"))
    if not files:
        messages.error(request, "No matching parts found.")
        return redirect("model_detail", pk=model.pk)

    buffer = io.BytesIO()
    used_names: dict[str, int] = {}
    written = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for model_file in files:
            if not model_file.file:
                continue
            file_path = Path(model_file.file.path)
            if not file_path.is_file():
                continue

            archive_name = model_file.original_name
            if archive_name in used_names:
                used_names[archive_name] += 1
                stem = file_path.stem
                suffix = file_path.suffix or f".{model_file.file_type}"
                archive_name = f"{stem}_{used_names[archive_name]}{suffix}"
            else:
                used_names[archive_name] = 0

            archive.write(file_path, arcname=archive_name)
            written += 1

    if written == 0:
        messages.error(request, "Could not prepare a download for the selected parts.")
        return redirect("model_detail", pk=model.pk)

    buffer.seek(0)
    safe_title = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in model.title[:80]).strip("._-") or "model"
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{safe_title}_parts.zip"'
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
        is_file_drop = request.POST.get("file_drop") == "1"

        if is_file_drop and not files:
            return JsonResponse({"error": "No files received."}, status=400)

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
                if is_file_drop:
                    return JsonResponse({"error": str(exc)}, status=400)
                messages.error(request, str(exc))
            else:
                if is_file_drop:
                    return JsonResponse(
                        {"redirect": reverse("scan_job", kwargs={"job_id": scan_job.job_id})}
                    )
                messages.success(request, "Scan started. Track progress below.")
                return redirect("scan_job", job_id=scan_job.job_id)
        elif is_file_drop:
            return JsonResponse({"error": "Invalid upload."}, status=400)

    return render(
        request,
        "library/scan.html",
        {
            "form": form,
            "recent": recent,
            "pipeline_steps": get_pipeline_steps(),
            "scan_worker_status": scan_worker_status(),
        },
    )


@login_required
@require_http_methods(["POST"])
def scan_chunk_upload_view(request):
    try:
        upload_id = str(request.POST.get("upload_id", "")).strip()
        chunk_index = int(request.POST.get("chunk_index", -1))
        total_chunks = int(request.POST.get("total_chunks", 0))
        filename = str(request.POST.get("filename", "")).strip()
        chunk = request.FILES.get("chunk")
        if not chunk:
            return JsonResponse({"error": "Missing chunk data."}, status=400)
        save_scan_chunk(
            user_id=request.user.id,
            upload_id=upload_id,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            filename=filename,
            chunk_file=chunk,
        )
    except (ScanError, ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": f"Chunk upload failed: {exc}"}, status=500)
    return JsonResponse({"ok": True, "chunk_index": chunk_index})


@login_required
@require_http_methods(["POST"])
def scan_chunk_complete_view(request):
    upload_id = str(request.POST.get("upload_id", "")).strip()
    title = str(request.POST.get("title", "")).strip()
    tag_names_raw = str(request.POST.get("tag_names", "")).strip()
    tag_names = [t.strip() for t in tag_names_raw.split(",") if t.strip()]
    collection_ids = []
    for value in request.POST.getlist("collections"):
        try:
            collection_ids.append(int(value))
        except ValueError:
            continue

    try:
        assembled_path = complete_scan_chunk_upload(
            user_id=request.user.id,
            upload_id=upload_id,
            title=title,
            tag_names=tag_names or None,
            collection_ids=collection_ids or None,
        )
        scan_job = create_scan_job(
            user=request.user,
            files=[AssembledScanFile(assembled_path)],
            title=title or None,
            tag_names=tag_names or None,
            collection_ids=collection_ids or None,
            bypass_cloudflare_limit=True,
        )
    except ScanError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    finally:
        cleanup_chunk_upload(request.user.id, upload_id)

    return JsonResponse({"redirect": reverse("scan_job", kwargs={"job_id": scan_job.job_id})})


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


def service_worker_view(request):
    sw_path = finders.find("library/js/service-worker.js")
    if not sw_path:
        return HttpResponse("Service worker not found.", status=404)
    content = Path(sw_path).read_text(encoding="utf-8")
    response = HttpResponse(content, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def manifest_view(request):
    payload = build_manifest(request)
    response = HttpResponse(json.dumps(payload), content_type="application/manifest+json")
    response["Cache-Control"] = "no-cache"
    return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def share_target_view(request):
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to import shared content into Pick-a-Print.")
        return redirect("login")

    source = request.GET if request.method == "GET" else request.POST
    title = source.get("title", "").strip()
    text = source.get("text", "").strip()
    url = source.get("url", "").strip()
    files = request.FILES.getlist("files") if request.method == "POST" else []

    try:
        return process_share_import(request, title=title, text=text, url=url, files=files)
    except (ModelSaveError, ScanError) as exc:
        messages.error(request, str(exc))
        return redirect("home")
