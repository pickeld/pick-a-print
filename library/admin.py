from django.contrib import admin

from library.models import Collection, ModelFile, SavedModel, Tag


@admin.register(ModelFile)
class ModelFileAdmin(admin.ModelAdmin):
    list_display = ["original_name", "model", "file_type", "triangle_count", "file_size", "created_at"]
    search_fields = ["original_name", "model__title"]


@admin.register(SavedModel)
class SavedModelAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "source_site", "status", "designer", "created_at"]
    list_filter = ["status", "source_site", "created_at"]
    search_fields = ["title", "designer", "source_url", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
    filter_horizontal = ["tags", "collections"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "slug", "created_at"]
    search_fields = ["name", "user__username"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "created_at"]
    search_fields = ["name", "user__username"]
