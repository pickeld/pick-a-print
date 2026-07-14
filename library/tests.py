from django.contrib.auth import get_user_model
from django.test import TestCase

from library.models import SavedModel, SourceType
from library.services import repair_model_display_fields

User = get_user_model()


class RepairModelDisplayFieldsTests(TestCase):
    def test_repairs_stale_printables_title(self):
        user = User.objects.create_user(username="tester", password="test")
        model = SavedModel.objects.create(
            user=user,
            source_type=SourceType.LINK,
            source_url="https://www.printables.com/model/123-example",
            source_site="printables.com",
            title="Example Model by Designer | Printables",
            designer="",
            metadata={"platform": "printables", "fetch_status": "complete"},
        )

        self.assertTrue(repair_model_display_fields(model))

        model.refresh_from_db()
        self.assertEqual(model.title, "Example Model")
        self.assertEqual(model.designer, "Designer")

    def test_skips_models_with_designer_already_set(self):
        user = User.objects.create_user(username="tester2", password="test")
        model = SavedModel.objects.create(
            user=user,
            source_type=SourceType.LINK,
            source_url="https://www.printables.com/model/456-other",
            source_site="printables.com",
            title="Example Model",
            designer="Existing Designer",
            metadata={"platform": "printables"},
        )

        self.assertFalse(repair_model_display_fields(model))
