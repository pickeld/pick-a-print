from django.contrib.auth import get_user_model
from django.test import TestCase

from library.download_providers.myminifactory import _file_items_from_payload
from library.integration_tests import test_myminifactory
from library.models import SavedModel, SourceType, UserMyMiniFactoryAuth
from library.services import repair_model_display_fields

User = get_user_model()


class RepairModelDisplayFieldsTests(TestCase):
    def test_repairs_stale_myminifactory_title(self):
        user = User.objects.create_user(username="tester", password="test")
        model = SavedModel.objects.create(
            user=user,
            source_type=SourceType.LINK,
            source_url="https://www.myminifactory.com/object/3d-print-ushi-articulated-704667",
            source_site="myminifactory.com",
            title="3D Printable Ushi Articulated\n            by PipeCox",
            designer="",
            metadata={"platform": "myminifactory", "fetch_status": "complete"},
        )

        self.assertTrue(repair_model_display_fields(model))

        model.refresh_from_db()
        self.assertEqual(model.title, "Ushi Articulated")
        self.assertEqual(model.designer, "PipeCox")

    def test_skips_models_with_designer_already_set(self):
        user = User.objects.create_user(username="tester2", password="test")
        model = SavedModel.objects.create(
            user=user,
            source_type=SourceType.LINK,
            source_url="https://www.myminifactory.com/object/example-1",
            source_site="myminifactory.com",
            title="Example Model",
            designer="Existing Designer",
            metadata={"platform": "myminifactory"},
        )

        self.assertFalse(repair_model_display_fields(model))


class MyMiniFactoryIntegrationTests(TestCase):
    def test_file_items_from_paginated_payload(self):
        payload = {
            "total_count": 2,
            "items": [
                {"id": 1, "filename": "part.stl", "download_url": "https://example.test/part.stl"},
                {"id": 2, "filename": "notes.pdf", "download_url": None},
            ],
        }
        items = _file_items_from_payload(payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["filename"], "part.stl")

    def test_file_items_from_nested_object_payload(self):
        payload = {
            "files": {
                "total_count": 1,
                "items": [{"id": 1, "filename": "model.3mf", "download_url": "https://example.test/model.3mf"}],
            }
        }
        items = _file_items_from_payload(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["filename"], "model.3mf")

    def test_connection_test_uses_oauth_without_legacy_secret(self):
        user = User.objects.create_user(username="mmf-user", password="test")
        from library.models import SiteConfig

        config = SiteConfig.get()
        config.myminifactory_api_key = "pick_a_print"
        config.save(update_fields=["myminifactory_api_key"])
        UserMyMiniFactoryAuth.objects.create(
            user=user,
            access_token="test-token",
            username="davidpickel",
        )

        from unittest.mock import patch

        with patch("library.myminifactory_oauth.validate_access_token", return_value={"username": "davidpickel"}):
            result = test_myminifactory(user=user)

        self.assertTrue(result.ok)
        self.assertIn("davidpickel", result.message)

    def test_connection_test_prompts_for_oauth_when_not_connected(self):
        user = User.objects.create_user(username="mmf-user2", password="test")
        from library.models import SiteConfig

        config = SiteConfig.get()
        config.myminifactory_api_key = "pick_a_print"
        config.save(update_fields=["myminifactory_api_key"])

        result = test_myminifactory(user=user)
        self.assertFalse(result.ok)
        self.assertIn("Connect MyMiniFactory", result.message)
