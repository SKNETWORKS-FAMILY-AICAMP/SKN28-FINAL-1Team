import io
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User
from . import taxonomy as T
from .models import WardrobeItemBatch, WardrobeUploadJob
from .services import storage
from .views import _merge_metadata


@patch("apps.wardrobe.views.storage.BUCKET", "test-bucket")
class BatchSmokeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username="batch-test")
        self.client.force_authenticate(self.user)

    @patch("apps.wardrobe.views.jobs.enqueue_item")
    @patch("apps.wardrobe.views.storage.upload_fileobj")
    @patch("apps.wardrobe.views.storage.fetch_remote_image")
    def test_two_links_become_two_qwen_jobs(self, fetch, upload, enqueue):
        fetch.return_value = (io.BytesIO(b"image"), "image/jpeg", ".jpg", 5)
        response = self.client.post(
            reverse("wardrobe:batch-list-create"),
            {
                "items": [
                    {"image_link": "https://cdn.example.com/one.jpg", "item_name": "상품명"},
                    {"image_link": "https://cdn.example.com/two.jpg"},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        batch = WardrobeItemBatch.objects.get(pk=response.data["batch_id"])
        self.assertEqual(batch.jobs.count(), 2)
        self.assertEqual(set(batch.jobs.values_list("pipeline", flat=True)), {"qwen-tag"})
        self.assertEqual(batch.jobs.get(original_file_name="one.jpg").input_metadata["item_name"], "상품명")
        self.assertEqual((fetch.call_count, upload.call_count, enqueue.call_count), (2, 2, 2))

    def test_empty_batch_is_rejected(self):
        response = self.client.post(
            reverse("wardrobe:batch-list-create"), {"items": []}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rollup_distinguishes_partial_failure(self):
        batch = WardrobeItemBatch.objects.create(user=self.user, total_count=2)
        for job_status in ("DONE", "FAILED"):
            WardrobeUploadJob.objects.create(
                user=self.user,
                batch=batch,
                source_s3_key=f"{job_status}.jpg",
                status=job_status,
            )
        batch.refresh_status()
        self.assertEqual((batch.status, batch.done_count, batch.failed_count), ("PARTIAL", 1, 1))

    def test_browser_metadata_wins_over_qwen_result(self):
        generated = {
            "item_name": "Qwen 이름",
            "category_large": T.CATEGORY_LARGE[0],
            "category_small": T.CATEGORY_SMALL[T.CATEGORY_LARGE[0]][0],
            "color": T.COLORS[0],
        }
        merged = _merge_metadata(
            generated,
            {"item_name": "구매 상품명", "color": T.COLORS[1], "confirmed": False},
        )
        self.assertEqual((merged["item_name"], merged["color"], merged["confirmed"]),
                         ("구매 상품명", T.COLORS[1], False))


class RemoteImageSecurityTest(TestCase):
    @patch("apps.wardrobe.services.storage.socket.getaddrinfo")
    def test_private_network_image_url_is_rejected(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("127.0.0.1", 80))]

        with self.assertRaises(storage.RemoteImageError):
            storage._validate_public_url("http://localhost/image.jpg")
