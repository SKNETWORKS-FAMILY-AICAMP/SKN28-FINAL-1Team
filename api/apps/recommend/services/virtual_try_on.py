"""사용자 전신 사진의 체형을 유지하는 Qwen 가상 착장."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings

from apps.recommend.services.body_profile import UNKNOWN, build_profile
from apps.recommend.services.mixed_outfit_render import (
    LoadedReferenceImage,
    RenderProviderError,
    RenderItemReference,
    RenderSource,
    _detect_media_type,
)
from apps.users.models import BodyMeasurement

DIRECT_PROMPT_VERSION = "virtual-try-on-direct-v1"
MANNEQUIN_PROMPT_VERSION = "virtual-try-on-mannequin-v7"

BODY_MEASUREMENT_FIELDS = (
    "height",
    "weight",
    "chest",
    "waist",
    "hip",
    "thigh",
    "calf",
    "arm",
    "shoulder",
    "neck_length",
    "thigh_calf_ratio",
    "torso_leg_ratio",
)

DIRECT_PROMPT = """Image 1 is the target person. Image 2 is the outfit reference.
Preserve the exact face, identity, hairstyle, visible body shape, body proportions,
pose, hands, legs, camera angle, framing, and background from Image 1.
Replace only the clothing on the person with the complete outfit from Image 2.
Preserve the outfit's garment types, colors, patterns, materials, layering, sleeve
lengths, neckline, waistline, and hem lengths. Fit the clothes naturally to the
existing body and pose. Do not slim, enlarge, reshape, beautify, or otherwise alter
the person. Do not add text, logos, or watermarks that are not in the outfit."""

MANNEQUIN_PROMPT = """Image 1 is the target person. Image 2 is the outfit reference.
In one edit, replace the person with a modern clothing-store display mannequin and
dress it only in the complete outfit from Image 2. Preserve Image 1's exact body
silhouette, shoulder width, torso length, waist width, hip width, arm and leg
proportions, apparent height, pose, hand and foot positions, camera angle, framing,
and lighting. Replace the entire background with a seamless, featureless pure white
studio background. Show no store interior, clothing racks, furniture, ceiling,
walls, decorations, or horizon line. The mannequin must be smooth glossy white fiberglass.
Its head must be a plain faceless bald seamless oval shell, with no facial features,
hair, likeness, identity, skin texture, or human expression. Visible neck, arms,
hands, ankles, and feet not covered by the reference outfit must be smooth solid
white mannequin material. Completely discard every garment originally worn in
Image 1. Copy the outfit from Image 2 as faithfully as possible. Do not redesign,
restyle, simplify, recolor, or replace any garment. Preserve its exact garment
types, silhouette, colors, prints, logos, patterns, fabric appearance, texture,
seams, buttons, pockets, collar, layering, sleeve lengths, neckline, waistline,
and hem lengths. Change only the drape and geometry required to fit the mannequin's
body and pose. Do not add a base outfit, undershirt, turtleneck, extra sleeves,
extra trousers, socks, or any layer absent from Image 2. Do not create a stone or
plaster statue, realistic skin, or sculpted hairstyle. Do not slim, enlarge,
reshape, idealize, or beautify the source body."""


def load_body_profile(user: Any) -> dict[str, Any]:
    """로그인 사용자의 저장된 체형값을 VTON용 JSON 데이터로 만든다."""
    if not getattr(user, "is_authenticated", False):
        return {}
    measurement = BodyMeasurement.objects.filter(user=user).first()
    if measurement is None:
        return {}

    values = {
        field: float(value) if isinstance(value, Decimal) else value
        for field in BODY_MEASUREMENT_FIELDS
        if (value := getattr(measurement, field, None)) is not None
    }
    if measurement.gender:
        values["gender"] = measurement.gender
    if not values:
        return {}
    profile = build_profile(values)
    return {
        "measurements": values,
        "silhouette": None if profile.silhouette == UNKNOWN else profile.silhouette,
        "bmi_band": None if profile.bmi_band == UNKNOWN else profile.bmi_band,
        "proportion_traits": profile.ratios,
    }


def body_profile_contract(body_profile: dict[str, Any]) -> str:
    """체형값 변경 시 기존 VTON 결과 캐시를 재사용하지 않게 한다."""
    payload = json.dumps(
        body_profile,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _mannequin_prompt(body_profile: dict[str, Any] | None) -> str:
    if not body_profile:
        return MANNEQUIN_PROMPT
    body_json = json.dumps(body_profile, ensure_ascii=False, sort_keys=True)
    return f"""{MANNEQUIN_PROMPT}

Target user's saved body data (measurements are cm, weight is kg):
{body_json}
Use this data only to preserve the user's body proportions and prevent a generic
fashion-model silhouette. Keep Image 1 as the authority for pose, camera framing,
and visible silhouette when an estimated value conflicts with the photograph.
Do not print, label, or otherwise expose the measurements in the output image."""


@dataclass(frozen=True)
class GeneratedTryOnImage:
    content: bytes
    media_type: str
    usage: dict[str, Any] = field(default_factory=dict)


class VirtualTryOnBusyError(RenderProviderError):
    """GPU가 이미 다른 가상 착장 요청을 처리 중이다."""


class GpuQwenImageProvider:
    """기존 GPU 서버의 Qwen Image Edit 내부 API를 호출한다."""

    provider_name = "gpu"

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def generate(
        self,
        *,
        prompt: str,
        references: tuple[LoadedReferenceImage, ...],
    ) -> tuple[bytes, str, dict[str, Any]]:
        if not settings.VIRTUAL_TRY_ON_ENABLED:
            raise RenderProviderError("가상 착장 기능이 비활성화되어 있습니다.")
        if not settings.VTON_GPU_URL or not settings.VTON_GPU_TOKEN:
            raise RenderProviderError("VTON GPU API 주소 또는 토큰이 설정되지 않았습니다.")
        try:
            response = self.session.post(
                settings.VTON_GPU_URL,
                headers={"Authorization": f"Bearer {settings.VTON_GPU_TOKEN}"},
                json={
                    "prompt": prompt,
                    "images": [
                        base64.b64encode(reference.content).decode("ascii")
                        for reference in references
                    ],
                },
                timeout=settings.VTON_GPU_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise RenderProviderError(f"VTON GPU 요청 실패: {exc}") from exc

        try:
            if response.status_code == 429:
                raise VirtualTryOnBusyError("VTON GPU가 다른 요청을 처리 중입니다.")
            if response.status_code >= 400:
                raise RenderProviderError(
                    f"VTON GPU 요청 실패 HTTP {response.status_code}: {response.text[:500]}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise RenderProviderError("VTON GPU 응답이 JSON이 아닙니다.") from exc
        finally:
            response.close()

        try:
            content = base64.b64decode(payload["image_base64"], validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise RenderProviderError("VTON GPU 응답에 유효한 이미지가 없습니다.") from exc
        if len(content) > settings.OUTFIT_RENDER_MAX_OUTPUT_BYTES:
            raise RenderProviderError("VTON GPU 결과 이미지가 허용 크기를 초과했습니다.")
        media_type = _detect_media_type(content)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return content, media_type, usage


def _reference(label: str, content: bytes) -> LoadedReferenceImage:
    return LoadedReferenceImage(
        item=RenderItemReference(
            item_id=label,
            position=1,
            slot=label,
            source_type=RenderSource.PRODUCT,
            image_ref=label,
        ),
        content=content,
        media_type=_detect_media_type(content),
    )


class VirtualTryOnService:
    def __init__(self, *, provider: GpuQwenImageProvider | None = None) -> None:
        self.provider = provider or GpuQwenImageProvider()

    def _generate(
        self, prompt: str, references: tuple[LoadedReferenceImage, ...]
    ) -> GeneratedTryOnImage:
        content, media_type, usage = self.provider.generate(
            prompt=prompt,
            references=references,
        )
        return GeneratedTryOnImage(content, media_type, usage)

    def fit_person(self, person: bytes, outfit: bytes) -> GeneratedTryOnImage:
        return self._generate(
            DIRECT_PROMPT,
            (_reference("target_person", person), _reference("outfit", outfit)),
        )

    def fit_mannequin(
        self,
        person: bytes,
        outfit: bytes,
        *,
        body_profile: dict[str, Any] | None = None,
    ) -> GeneratedTryOnImage:
        return self._generate(
            _mannequin_prompt(body_profile),
            (_reference("target_person", person), _reference("outfit", outfit)),
        )
