from __future__ import annotations

from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.recommend.services.virtual_try_on import (
    DIRECT_PROMPT,
    MANNEQUIN_PROMPT,
    VirtualTryOnService,
)

PNG = b"\x89PNG\r\n\x1a\nimage"


class VirtualTryOnServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.provider = Mock()
        self.provider.generate.return_value = (PNG, "image/png", {})
        self.service = VirtualTryOnService(provider=self.provider)

    def test_direct_fit_keeps_person_first_and_outfit_second(self) -> None:
        self.service.fit_person(PNG, PNG)

        call = self.provider.generate.call_args.kwargs
        self.assertEqual(call["prompt"], DIRECT_PROMPT)
        self.assertEqual(
            [ref.item.slot for ref in call["references"]],
            ["target_person", "outfit"],
        )
        self.assertIn("Do not slim, enlarge, reshape", call["prompt"])

    def test_mannequin_fit_is_one_edit_without_base_clothes(self) -> None:
        self.service.fit_mannequin(PNG, PNG)

        call = self.provider.generate.call_args.kwargs
        self.assertEqual(call["prompt"], MANNEQUIN_PROMPT)
        self.assertEqual(
            [ref.item.slot for ref in call["references"]],
            ["target_person", "outfit"],
        )
        self.assertIn("Do not add a base outfit", call["prompt"])
