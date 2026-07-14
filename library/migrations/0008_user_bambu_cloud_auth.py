import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0007_collection_icon"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserBambuCloudAuth",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("access_token", models.CharField(max_length=512)),
                ("refresh_token", models.CharField(blank=True, max_length=512)),
                ("token_expiry", models.DateTimeField(blank=True, null=True)),
                ("bambu_uid", models.CharField(blank=True, max_length=64)),
                ("bambu_name", models.CharField(blank=True, max_length=200)),
                ("bambu_email", models.CharField(blank=True, max_length=254)),
                (
                    "region",
                    models.CharField(
                        choices=[("global", "Global"), ("china", "China")],
                        default="global",
                        max_length=16,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bambu_cloud_auth",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Bambu Cloud auth",
                "verbose_name_plural": "Bambu Cloud auth",
            },
        ),
    ]
