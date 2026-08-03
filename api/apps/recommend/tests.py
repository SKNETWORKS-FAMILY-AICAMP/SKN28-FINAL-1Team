from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient


def make_image_file(name: str = "outfit.jpg") -> SimpleUploadedFile:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class OutfitAnalysisViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("recommend:outfit-analysis")

    def test_accepts_image_without_authentication(self) -> None:
        response = self.client.post(
            self.url,
            {"image": make_image_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "pending_evaluation")
        self.assertEqual(response.data["received"]["name"], "outfit.jpg")
        self.assertEqual(response.data["received"]["content_type"], "image/jpeg")
        self.assertIsNone(response.data["result"])

    def test_rejects_request_without_image(self) -> None:
        response = self.client.post(self.url, {}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)

    def test_rejects_non_image_file(self) -> None:
        response = self.client.post(
            self.url,
            {
                "image": SimpleUploadedFile(
                    "outfit.txt",
                    b"not an image",
                    content_type="text/plain",
                )
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)

    def test_rejects_json_request(self) -> None:
        response = self.client.post(self.url, {"image": "value"}, format="json")

        self.assertEqual(response.status_code, 415)
