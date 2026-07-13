from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0005_siteconfig_jetson_health_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfig",
            name="thingiverse_api_token",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="siteconfig",
            name="bambu_lab_token",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="siteconfig",
            name="myminifactory_api_key",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
