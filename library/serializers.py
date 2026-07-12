from rest_framework import serializers

from library.models import Collection, ModelFile, ModelStatus, SavedModel, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class CollectionListSerializer(serializers.ModelSerializer):
    model_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Collection
        fields = ["id", "name", "slug", "description", "model_count", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class CollectionDetailSerializer(CollectionListSerializer):
    class Meta(CollectionListSerializer.Meta):
        fields = CollectionListSerializer.Meta.fields


class SavedModelListSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = SavedModel
        fields = [
            "id",
            "title",
            "designer",
            "source_url",
            "source_site",
            "thumbnail_url",
            "status",
            "license",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SavedModelDetailSerializer(SavedModelListSerializer):
    collections = CollectionListSerializer(many=True, read_only=True)
    files = serializers.SerializerMethodField()

    class Meta(SavedModelListSerializer.Meta):
        fields = SavedModelListSerializer.Meta.fields + [
            "external_id",
            "metadata",
            "collections",
            "source_type",
            "files",
        ]
        read_only_fields = fields

    def get_files(self, obj):
        return ModelFileSerializer(obj.files.all(), many=True).data


class ModelFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelFile
        fields = [
            "id",
            "original_name",
            "file_type",
            "file_size",
            "triangle_count",
            "dimension_x",
            "dimension_y",
            "dimension_z",
            "volume_cm3",
            "analysis",
            "created_at",
        ]
        read_only_fields = fields


class SavedModelUpdateSerializer(serializers.ModelSerializer):
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        write_only=True,
    )
    collection_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = SavedModel
        fields = ["status", "title", "designer", "license", "tag_names", "collection_ids"]

    def validate_status(self, value):
        if value not in ModelStatus.values:
            raise serializers.ValidationError("Invalid status")
        return value

    def update(self, instance, validated_data):
        tag_names = validated_data.pop("tag_names", None)
        collection_ids = validated_data.pop("collection_ids", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tag_names is not None:
            tags = []
            user = instance.user
            for name in tag_names:
                clean = name.strip()
                if not clean:
                    continue
                tag, _ = Tag.objects.get_or_create(user=user, name=clean)
                tags.append(tag)
            instance.tags.set(tags)

        if collection_ids is not None:
            collections = Collection.objects.filter(user=instance.user, id__in=collection_ids)
            instance.collections.set(collections)

        return instance


class SaveModelSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2000)
    collection_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    status = serializers.ChoiceField(choices=ModelStatus.choices, required=False)

    def save(self, **kwargs):
        user = self.context["request"].user
        return save_model_from_service(user=user, data=self.validated_data)


def save_model_from_service(*, user, data):
    from library.services import save_model_from_url

    return save_model_from_url(
        user=user,
        url=data["url"],
        collection_ids=data.get("collection_ids"),
        tag_names=data.get("tag_names"),
        status=data.get("status"),
    )


class UploadModelSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=500, required=False, allow_blank=True)
    collection_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    status = serializers.ChoiceField(choices=ModelStatus.choices, required=False)

    def validate_file(self, value):
        name = (value.name or "").lower()
        if not name.endswith(".stl"):
            raise serializers.ValidationError("Only .stl files are supported")
        return value

    def save(self, **kwargs):
        from library.services import ModelSaveError, save_model_from_upload

        user = self.context["request"].user
        try:
            return save_model_from_upload(
                user=user,
                uploaded_file=self.validated_data["file"],
                title=self.validated_data.get("title") or None,
                collection_ids=self.validated_data.get("collection_ids"),
                tag_names=self.validated_data.get("tag_names"),
                status=self.validated_data.get("status"),
            )
        except ModelSaveError as exc:
            raise serializers.ValidationError(str(exc)) from exc
