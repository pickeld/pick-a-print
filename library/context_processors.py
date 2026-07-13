from django.db.models import Count

from library.collection_icons import COLLECTION_ICONS
from library.models import NO_COLLECTION_SLUG, Collection, uncollected_models_for_user


def sidebar_collections(request):
    if not request.user.is_authenticated:
        return {
            "sidebar_collections": [],
            "sidebar_uncollected_count": 0,
            "no_collection_slug": NO_COLLECTION_SLUG,
            "collection_icons": COLLECTION_ICONS,
        }
    collections = (
        Collection.objects.filter(user=request.user)
        .annotate(model_count=Count("models"))
        .order_by("name")[:20]
    )
    return {
        "sidebar_collections": collections,
        "sidebar_uncollected_count": uncollected_models_for_user(request.user).count(),
        "no_collection_slug": NO_COLLECTION_SLUG,
        "collection_icons": COLLECTION_ICONS,
    }


def upload_limits(request):
    from django.conf import settings as django_settings

    return {
        "scan_max_upload_mb": django_settings.EFFECTIVE_SCAN_MAX_UPLOAD_MB,
        "scan_total_max_upload_mb": django_settings.SCAN_MAX_UPLOAD_MB,
        "chunk_upload_size_mb": django_settings.CHUNK_UPLOAD_SIZE_MB,
        "cloudflare_proxy": django_settings.CLOUDFLARE_PROXY,
        "static_asset_version": django_settings.STATIC_ASSET_VERSION,
    }
