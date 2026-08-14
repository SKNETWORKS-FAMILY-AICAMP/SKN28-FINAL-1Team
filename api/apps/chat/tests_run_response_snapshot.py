from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.chat.models import ChatRun, ChatSession
from apps.chat.services import identity as identity_service
from apps.chat.services import orchestrator, sessions

User = get_user_model()


class ChatRunResponseSnapshotTests(TestCase):
    def setUp(self) -> None:
        user = User.objects.create_user(username="run-snapshot-member")
        self.identity = identity_service.get_or_create_member_identity(user)
        self.session = sessions.create_session(
            identity=self.identity,
            mode=ChatSession.Mode.WARDROBE_BASED,
        )

    def _submit(self, client_message_id: str = "snapshot-message"):
        return orchestrator.submit_message_and_create_run(
            identity=self.identity,
            session_id=self.session.id,
            content="출근 코디를 추천해줘",
            client_message_id=client_message_id,
        )

    def test_run_copies_mode_selection_and_versions_at_submission(self) -> None:
        self.session.response_mode = ChatSession.ResponseMode.STYLIST
        self.session.selected_persona_ids = ["minimal", "practical"]
        self.session.full_clean()
        self.session.save(
            update_fields=["response_mode", "selected_persona_ids"]
        )

        _message, message_created, run, run_created = self._submit()

        self.assertTrue(message_created)
        self.assertTrue(run_created)
        self.assertEqual(run.response_mode, ChatSession.ResponseMode.STYLIST)
        self.assertEqual(run.persona_ids, ["minimal", "practical"])
        self.assertEqual(run.persona_versions, {"minimal": 1, "practical": 1})
        self.assertEqual(
            run.persona_prompt_versions,
            {
                "minimal": "stylist-minimal-v1",
                "practical": "stylist-practical-v1",
            },
        )
        self.assertEqual(run.stylist_config_version, "stylist-personas-v1")

    def test_session_change_does_not_mutate_existing_run_snapshot(self) -> None:
        self.session.response_mode = ChatSession.ResponseMode.STYLIST
        self.session.selected_persona_ids = ["minimal"]
        self.session.full_clean()
        self.session.save(
            update_fields=["response_mode", "selected_persona_ids"]
        )
        _message, _message_created, run, _run_created = self._submit()

        self.session.response_mode = ChatSession.ResponseMode.DEFAULT
        self.session.selected_persona_ids = ["experimental"]
        self.session.full_clean()
        self.session.save(
            update_fields=["response_mode", "selected_persona_ids"]
        )
        run.refresh_from_db()

        self.assertEqual(run.response_mode, ChatSession.ResponseMode.STYLIST)
        self.assertEqual(run.persona_ids, ["minimal"])
        self.assertEqual(run.persona_versions, {"minimal": 1})

    def test_duplicate_message_returns_original_run_snapshot(self) -> None:
        self.session.response_mode = ChatSession.ResponseMode.STYLIST
        self.session.selected_persona_ids = ["minimal"]
        self.session.full_clean()
        self.session.save(
            update_fields=["response_mode", "selected_persona_ids"]
        )
        message, _message_created, run, _run_created = self._submit()

        self.session.response_mode = ChatSession.ResponseMode.DEFAULT
        self.session.selected_persona_ids = ["practical"]
        self.session.full_clean()
        self.session.save(
            update_fields=["response_mode", "selected_persona_ids"]
        )
        duplicate, message_created, duplicate_run, run_created = self._submit()

        self.assertFalse(message_created)
        self.assertFalse(run_created)
        self.assertEqual(duplicate.id, message.id)
        self.assertEqual(duplicate_run.id, run.id)
        self.assertEqual(duplicate_run.response_mode, ChatSession.ResponseMode.STYLIST)
        self.assertEqual(duplicate_run.persona_ids, ["minimal"])

    def test_run_validation_rejects_snapshot_key_mismatch(self) -> None:
        message, _created = sessions.append_message(
            identity=self.identity,
            session_id=self.session.id,
            role="USER",
            content="추천해줘",
        )
        run = ChatRun(
            session=self.session,
            request_message=message,
            response_mode=ChatSession.ResponseMode.STYLIST,
            persona_ids=["minimal"],
            persona_versions={"practical": 1},
            persona_prompt_versions={"minimal": "stylist-minimal-v1"},
            stylist_config_version="stylist-personas-v1",
        )

        with self.assertRaisesMessage(ValidationError, "선택 스타일리스트 ID"):
            run.full_clean()
