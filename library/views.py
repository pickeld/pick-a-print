from django.db.models import Count, Q
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from library.models import Collection, ModelStatus, SavedModel, Tag
from library.serializers import (
    CollectionDetailSerializer,
    CollectionListSerializer,
    SaveModelSerializer,
    SavedModelDetailSerializer,
    SavedModelListSerializer,
    SavedModelUpdateSerializer,
    TagSerializer,
    UploadModelSerializer,
)
from library.services import ModelSaveError


class SavedModelFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=ModelStatus.choices)
    source_site = filters.CharFilter(lookup_expr="icontains")
    collection = filters.NumberFilter(field_name="collections__id")
    tag = filters.CharFilter(field_name="tags__name", lookup_expr="iexact")

    class Meta:
        model = SavedModel
        fields = ["status", "source_site", "collection", "tag"]


class SavedModelViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_class = SavedModelFilter
    search_fields = ["title", "designer", "source_site", "tags__name"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            SavedModel.objects.filter(user=self.request.user)
            .prefetch_related("tags", "collections", "files")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "save":
            return SaveModelSerializer
        if self.action == "upload":
            return UploadModelSerializer
        if self.action in ("partial_update", "update"):
            return SavedModelUpdateSerializer
        if self.action == "retrieve":
            return SavedModelDetailSerializer
        return SavedModelListSerializer

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /api/models/save/ with {\"url\": \"...\"}."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=["post"])
    def upload(self, request):
        serializer = UploadModelSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        model = serializer.save()
        response_serializer = SavedModelDetailSerializer(model)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def save(self, request):
        serializer = SaveModelSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            model = serializer.save()
        except ModelSaveError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        created = getattr(model, "_was_created", True)
        response_serializer = SavedModelDetailSerializer(model)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def search(self, request):
        query = request.query_params.get("q", "").strip()
        queryset = self.get_queryset()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(designer__icontains=query)
                | Q(source_site__icontains=query)
                | Q(tags__name__icontains=query)
                | Q(metadata__icontains=query)
            ).distinct()
        page = self.paginate_queryset(queryset)
        serializer = SavedModelListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"])
    def recent(self, request):
        queryset = self.get_queryset()[:12]
        serializer = SavedModelListSerializer(queryset, many=True)
        return Response(serializer.data)


class CollectionViewSet(viewsets.ModelViewSet):
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return Collection.objects.filter(user=self.request.user).annotate(model_count=Count("models"))

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CollectionDetailSerializer
        return CollectionListSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TagViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = TagSerializer
    search_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
