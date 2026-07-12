from django.db.models import Count

from library.models import Collection


def sidebar_collections(request):
    if not request.user.is_authenticated:
        return {"sidebar_collections": []}
    collections = (
        Collection.objects.filter(user=request.user)
        .annotate(model_count=Count("models"))
        .order_by("name")[:20]
    )
    return {"sidebar_collections": collections}
