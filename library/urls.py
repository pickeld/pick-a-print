from django.urls import include, path
from rest_framework.routers import DefaultRouter

from library.views import CollectionViewSet, SavedModelViewSet, TagViewSet

router = DefaultRouter()
router.register("models", SavedModelViewSet, basename="model")
router.register("collections", CollectionViewSet, basename="collection")
router.register("tags", TagViewSet, basename="tag")

urlpatterns = [
    path("", include(router.urls)),
]
