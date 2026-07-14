from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0009_myminifactory_oauth"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserMyMiniFactoryAuth",
        ),
        migrations.RemoveField(
            model_name="siteconfig",
            name="myminifactory_api_key",
        ),
        migrations.RemoveField(
            model_name="siteconfig",
            name="myminifactory_client_secret",
        ),
    ]
