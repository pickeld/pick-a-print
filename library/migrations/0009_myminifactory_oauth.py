import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0008_user_bambu_cloud_auth"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfig",
            name="myminifactory_client_secret",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name="UserMyMiniFactoryAuth",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("access_token", models.CharField(max_length=512)),
                ("refresh_token", models.CharField(blank=True, max_length=512)),
                ("token_expiry", models.DateTimeField(blank=True, null=True)),
                ("mmf_user_id", models.CharField(blank=True, max_length=64)),
                ("username", models.CharField(blank=True, max_length=200)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="myminifactory_auth",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "MyMiniFactory auth",
                "verbose_name_plural": "MyMiniFactory auth",
            },
        ),
    ]
