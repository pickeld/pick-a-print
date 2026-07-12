from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from rest_framework.authtoken.models import Token

from library.forms import CollectionForm, LoginForm, ModelUpdateForm, SaveModelForm, SearchForm, UploadModelForm
from library.models import Collection, ModelStatus, SavedModel
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
    token, _ = Token.objects.get_or_create(user=request.user)
    api_base = request.build_absolute_uri("/api").rstrip("/")
    return render(
        request,
        "library/settings.html",
        {"api_token": token.key, "api_base": api_base},
    )


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
