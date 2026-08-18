from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.chat.models import ChatMessage, ChatRun, ChatSession
from apps.chat.services import identity as identity_service
from apps.chat.services import sessions as session_service
from apps.wardrobe.models import (
    SharedWardrobeItem,
    SharedWardrobeMember,
    SharedWardrobeRoom,
    WardrobeItem,
)

User = get_user_model()


class SharedReferenceSnapshotApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="reference-member")
        self.friend = User.objects.create_user(
            username="reference-friend",
            nickname="하영",
        )
        self.identity = identity_service.get_or_create_member_identity(self.user)
        self.session = session_service.create_session(
            identity=self.identity,
            mode=ChatSession.Mode.WARDROBE_BASED,
        )
        self.url = reverse("chat:session-messages", args=[self.session.pk])
        self.client.force_authenticate(self.user)

        self.room = SharedWardrobeRoom.objects.create(title="친구 옷장")
        SharedWardrobeMember.objects.create(
            room=self.room,
            user=self.user,
            role=SharedWardrobeMember.Role.MEMBER,
        )
        SharedWardrobeMember.objects.create(
            room=self.room,
            user=self.friend,
            role=SharedWardrobeMember.Role.OWNER,
        )
        self.wardrobe_item = WardrobeItem.objects.create(
            user=self.friend,
            s3_key="wardrobe/reference-jacket.webp",
            item_name="친구의 검정 재킷",
            category_large="아우터",
            category_small="재킷",
            season=["봄", "가을"],
            style=["미니멀"],
            color="검정",
            pattern="무지",
            fit="오버핏",
            material="울",
            usage=["데이트"],
            layer_role="아우터",
            layer_order=3,
            confirmed=True,
            added_to_closet_at=timezone.now(),
            embedding_version="fashionsiglip-v1",
        )
        self.shared_item = SharedWardrobeItem.objects.create(
            room=self.room,
            registered_by=self.friend,
            wardrobe_item=self.wardrobe_item,
            status=SharedWardrobeItem.Status.AVAILABLE,
        )

    def _payload(self, client_message_id: str = "shared-reference-1") -> dict:
        return {
            "content": "이 옷과 비슷한 느낌으로 추천해줘",
            "client_message_id": client_message_id,
            "reference": {
                "type": "SHARED_WARDROBE_ITEM",
                "shared_item_id": str(self.shared_item.pk),
            },
        }

    @patch("apps.chat.views.ChatEventStore.publish")
    @patch("apps.chat.views.chat_queue.enqueue")
    def test_message_request_persists_shared_item_reference_snapshot(
        self,
        _enqueue_mock,
        _publish_mock,
    ) -> None:
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        run = ChatRun.objects.get(pk=response.data["run"]["id"])
        snapshot = run.reference_snapshot
        self.assertEqual(snapshot["schema_version"], "1.0")
        self.assertEqual(snapshot["type"], "SHARED_WARDROBE_ITEM")
        self.assertEqual(snapshot["shared_item_id"], str(self.shared_item.pk))
        self.assertEqual(snapshot["room_id"], str(self.room.pk))
        self.assertEqual(
            snapshot["wardrobe_item_id"],
            str(self.wardrobe_item.pk),
        )
        self.assertEqual(
            snapshot["qdrant_point_id"],
            str(self.wardrobe_item.pk),
        )
        self.assertEqual(snapshot["item"]["category_large"], "아우터")
        self.assertEqual(snapshot["item"]["style"], ["미니멀"])
        self.assertEqual(snapshot["owner_name"], "하영")
        self.assertEqual(snapshot["room_name"], "친구 옷장")
        self.assertNotIn("vector", snapshot)

    @patch(
        "apps.chat.serializers.wardrobe_storage.presigned_get",
        return_value="https://images.example/reference-jacket.webp",
    )
    @patch("apps.chat.views.ChatEventStore.publish")
    @patch("apps.chat.views.chat_queue.enqueue")
    def test_message_history_returns_safe_reference_summary(
        self,
        _enqueue_mock,
        _publish_mock,
        _presigned_get_mock,
    ) -> None:
        created = self.client.post(
            self.url,
            self._payload("shared-reference-history"),
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_202_ACCEPTED)
        shared_item_id = str(self.shared_item.pk)
        self.shared_item.delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        summary = response.data[0]["reference_summary"]
        self.assertEqual(
            summary,
            {
                "schema_version": "1.0",
                "type": "SHARED_WARDROBE_ITEM",
                "shared_item_id": shared_item_id,
                "item_name": "친구의 검정 재킷",
                "category_large": "아우터",
                "owner_name": "하영",
                "room_name": "친구 옷장",
                "image_url": "https://images.example/reference-jacket.webp",
            },
        )
        self.assertNotIn("qdrant_collection", summary)
        self.assertNotIn("qdrant_point_id", summary)
        self.assertNotIn("image_s3_key", summary)
        self.assertNotIn("wardrobe_item_id", summary)

    @patch("apps.chat.views.ChatEventStore.publish")
    @patch("apps.chat.views.chat_queue.enqueue")
    def test_message_without_reference_returns_null_summary(
        self,
        _enqueue_mock,
        _publish_mock,
    ) -> None:
        response = self.client.post(
            self.url,
            {
                "content": "일반 추천",
                "client_message_id": "without-shared-reference",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIsNone(response.data["message"]["reference_summary"])

    @patch("apps.chat.views.ChatEventStore.publish")
    @patch("apps.chat.views.chat_queue.enqueue")
    def test_duplicate_client_message_keeps_original_reference_snapshot(
        self,
        _enqueue_mock,
        _publish_mock,
    ) -> None:
        payload = self._payload("shared-reference-idempotent")
        first = self.client.post(self.url, payload, format="json")
        run = ChatRun.objects.get(pk=first.data["run"]["id"])
        original_snapshot = run.reference_snapshot
        self.shared_item.status = SharedWardrobeItem.Status.PRIVATE
        self.shared_item.save(update_fields=["status"])

        duplicate = self.client.post(self.url, payload, format="json")

        self.assertEqual(duplicate.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(duplicate.data["run"]["id"], first.data["run"]["id"])
        run.refresh_from_db()
        self.assertEqual(run.reference_snapshot, original_snapshot)

    def test_private_shared_item_is_rejected_without_partial_message(self) -> None:
        self.shared_item.status = SharedWardrobeItem.Status.PRIVATE
        self.shared_item.save(update_fields=["status"])

        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "REFERENCE_ITEM_FORBIDDEN")
        self.assertFalse(
            ChatMessage.objects.filter(
                session=self.session,
                client_message_id="shared-reference-1",
            ).exists()
        )
        self.assertFalse(ChatRun.objects.filter(session=self.session).exists())

    def test_non_member_cannot_reference_shared_item(self) -> None:
        SharedWardrobeMember.objects.filter(
            room=self.room,
            user=self.user,
        ).delete()

        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "REFERENCE_ITEM_FORBIDDEN")

    @patch("apps.chat.views.ChatEventStore.publish")
    @patch("apps.chat.views.chat_queue.enqueue")
    def test_borrowed_shared_item_can_still_be_used_as_reference(
        self,
        _enqueue_mock,
        _publish_mock,
    ) -> None:
        self.shared_item.status = SharedWardrobeItem.Status.BORROWED
        self.shared_item.save(update_fields=["status"])

        response = self.client.post(
            self.url,
            self._payload("shared-reference-borrowed"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        run = ChatRun.objects.get(pk=response.data["run"]["id"])
        self.assertEqual(
            run.reference_snapshot["source_status"],
            SharedWardrobeItem.Status.BORROWED,
        )

    def test_reference_without_embedding_is_not_ready(self) -> None:
        self.wardrobe_item.embedding_version = ""
        self.wardrobe_item.save(update_fields=["embedding_version"])

        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "REFERENCE_ITEM_NOT_READY")

    def test_reference_contract_rejects_unknown_type(self) -> None:
        payload = self._payload()
        payload["reference"]["type"] = "WARDROBE_ITEM"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reference", response.data)
