from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0006_siteconfig_provider_keys"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="icon",
            field=models.CharField(blank=True, default="folder", max_length=80),
        ),
    ]
