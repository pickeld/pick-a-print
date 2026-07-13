from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0004_siteconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfig",
            name="jetson_health_token",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
