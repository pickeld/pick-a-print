from django.contrib import admin

from library.models import Collection, ModelFile, SavedModel, ScanJob, SiteConfig, Tag


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


@admin.register(ScanJob)
class ScanJobAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "stage", "progress", "input_file_count", "created_at"]
    list_filter = ["stage", "created_at"]
    search_fields = ["title", "job_id", "user__username"]
    readonly_fields = ["job_id", "created_at", "updated_at"]


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ["jetson_enabled", "jetson_host", "has_health_token", "last_test_ok", "last_test_at"]
    readonly_fields = ["last_test_at", "last_test_ok", "last_test_message"]

    @admin.display(boolean=True, description="Health token set")
    def has_health_token(self, obj: SiteConfig) -> bool:
        return bool(obj.jetson_health_token)
