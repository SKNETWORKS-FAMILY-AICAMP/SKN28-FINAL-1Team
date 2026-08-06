from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User
from .models import WardrobeItemBatch, WardrobeUploadJob


def photo(name: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"\xff\xd8\xff\xe0image", content_type="image/jpeg")


@patch("apps.wardrobe.views.storage.BUCKET", "test-bucket")
class BatchSmokeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="batch-test")
        self.client.force_authenticate(self.user)

    @patch("apps.wardrobe.views.jobs.enqueue_item")
    @patch("apps.wardrobe.views.storage.upload_fileobj")
    def test_two_images_become_two_qwen_jobs(self, upload, enqueue):
        response = self.client.post(
            reverse("wardrobe:batch-list-create"),
            {"images": [photo("one.jpg"), photo("two.jpg")]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 202)
        batch = WardrobeItemBatch.objects.get(pk=response.data["batch_id"])
        self.assertEqual(batch.jobs.count(), 2)
        self.assertEqual(set(batch.jobs.values_list("pipeline", flat=True)), {"qwen-tag"})
        self.assertEqual((upload.call_count, enqueue.call_count), (2, 2))

    def test_empty_batch_is_rejected(self):
        self.assertEqual(
            self.client.post(reverse("wardrobe:batch-list-create"), {}, format="multipart").status_code,
            400,
        )

    def test_rollup_distinguishes_partial_failure(self):
        batch = WardrobeItemBatch.objects.create(user=self.user, total_count=2)
        for status in ("DONE", "FAILED"):
            WardrobeUploadJob.objects.create(
                user=self.user, batch=batch, source_s3_key=f"{status}.jpg", status=status,
            )
        batch.refresh_status()
        self.assertEqual((batch.status, batch.done_count, batch.failed_count), ("PARTIAL", 1, 1))
