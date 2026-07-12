from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ModelStatus(models.TextChoices):
    SAVED = "saved", "Saved"
    DOWNLOADED = "downloaded", "Downloaded"
    PRINTED = "printed", "Printed"
    PAINTED = "painted", "Painted"
    GIFTED = "gifted", "Gifted"


class SourceType(models.TextChoices):
    LINK = "link", "Link"
    UPLOAD = "upload", "Upload"


class Tag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_tag_per_user"),
        ]

    def __str__(self) -> str:
        return self.name


class Collection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="collections")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "slug"], name="unique_collection_slug_per_user"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "collection"
            slug = base
            counter = 1
            while Collection.objects.filter(user=self.user, slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)


class SavedModel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_models")
    source_type = models.CharField(
        max_length=10,
        choices=SourceType.choices,
        default=SourceType.LINK,
        db_index=True,
    )
    source_url = models.URLField(max_length=2000, blank=True)
    source_site = models.CharField(max_length=100, blank=True, db_index=True)
    external_id = models.CharField(max_length=200, blank=True, db_index=True)

    title = models.CharField(max_length=500)
    designer = models.CharField(max_length=300, blank=True)
    license = models.CharField(max_length=200, blank=True)
    thumbnail_url = models.URLField(max_length=2000, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ModelStatus.choices,
        default=ModelStatus.SAVED,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    tags = models.ManyToManyField(Tag, blank=True, related_name="models")
    collections = models.ManyToManyField(Collection, blank=True, related_name="models")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "source_url"], name="unique_model_url_per_user"),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "source_site"]),
        ]

    def __str__(self) -> str:
        return self.title


class ModelFile(models.Model):
    model = models.ForeignKey(SavedModel, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="models/%Y/%m/")
    file_type = models.CharField(max_length=10, default="stl")
    original_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    triangle_count = models.PositiveIntegerField(null=True, blank=True)
    dimension_x = models.FloatField(null=True, blank=True)
    dimension_y = models.FloatField(null=True, blank=True)
    dimension_z = models.FloatField(null=True, blank=True)
    volume_cm3 = models.FloatField(null=True, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name


class ScanJob(models.Model):
    """Photogrammetry scan tracked in Django; pipeline state lives in job.json on disk."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scan_jobs")
    job_id = models.UUIDField(unique=True, db_index=True)
    title = models.CharField(max_length=500)
    stage = models.CharField(max_length=32, default="UPLOADED", db_index=True)
    progress = models.FloatField(default=0)
    error = models.TextField(blank=True)
    input_file_count = models.PositiveSmallIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    saved_model = models.ForeignKey(
        SavedModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scan_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_terminal(self) -> bool:
        return self.stage in ("COMPLETED", "FAILED")

    @property
    def is_completed(self) -> bool:
        return self.stage == "COMPLETED"
