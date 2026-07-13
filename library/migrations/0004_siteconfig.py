from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0003_scanjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jetson_host", models.CharField(blank=True, max_length=253)),
                ("jetson_health_port", models.PositiveIntegerField(default=8765)),
                ("jetson_enabled", models.BooleanField(default=False)),
                ("last_test_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_ok", models.BooleanField(default=False)),
                ("last_test_message", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Site configuration",
                "verbose_name_plural": "Site configuration",
            },
        ),
    ]
