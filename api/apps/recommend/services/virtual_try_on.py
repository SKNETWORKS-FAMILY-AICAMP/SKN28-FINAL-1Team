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
    ReferenceImageLoader,
    RenderProviderError,
    RenderItemReference,
    RenderSource,
    _detect_media_type,
)
from apps.users.models import BodyMeasurement

DIRECT_PROMPT_VERSION = "virtual-try-on-direct-v1"
MANNEQUIN_PROMPT_VERSION = "virtual-try-on-mannequin-v8-two-stage"
MANNEQUIN_BASE_PROMPT_VERSION = "virtual-try-on-body-mannequin-v1"

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

MANNEQUIN_BASE_PROMPT = """Image 1 is the target person's full-body photograph.
Replace the person with a modern retail clothing-store mannequin while preserving
the photograph's exact body silhouette, shoulder, torso, waist, hip, arm and leg
proportions, apparent height, pose, hand and foot positions, camera angle, and
framing. Remove every original garment completely. The output mannequin must have
one continuous smooth glossy white fiberglass surface with no clothing, bodysuit,
underwear, collar, cuffs, waistbands, seams, fabric folds, or layered shapes. Its
head is a plain faceless bald seamless oval. Use a seamless featureless pure white
studio background with no horizon line, furniture, store interior, or text. This
is a neutral garmentless retail display form, not a human nude body, stone statue,
or plaster sculpture. Do not slim, enlarge, idealize, or beautify the source body."""

MANNEQUIN_DRESS_PROMPT = """Image 1 is the already prepared target retail mannequin.
Images 2 onward are garment references. Keep Image 1's exact mannequin body shape,
pose, camera angle, framing, glossy white exposed surface, and pure white background.
Dress it only in the complete referenced outfit. Do not change the mannequin body.
Do not add an undershirt, bodysuit, turtleneck, extra sleeves, extra trousers,
underwear, socks, or any garment absent from the references."""


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


def _mannequin_base_prompt(body_profile: dict[str, Any] | None) -> str:
    if not body_profile:
        return MANNEQUIN_BASE_PROMPT
    body_json = json.dumps(body_profile, ensure_ascii=False, sort_keys=True)
    return f"""{MANNEQUIN_BASE_PROMPT}

Target user's saved body data (measurements are cm, weight is kg):
{body_json}
Use the measurements to resolve proportions that clothing obscures, while keeping
Image 1 authoritative for pose and framing. Never expose these values as text."""


def _garment_prompt(prompt: str, garments: tuple[LoadedReferenceImage, ...]) -> str:
    if not garments:
        return prompt
    manifest = "\n".join(
        f"- Image {index}: {reference.item.slot} garment reference"
        for index, reference in enumerate(garments, start=2)
    )
    prompt = prompt.replace(
        "Image 1 is the target person. Image 2 is the outfit reference.",
        "Image 1 is the target person or mannequin.",
    )
    return f"""{prompt}

Images 2 onward are the original individual garment references, not a styled
person reference:
{manifest}
Use every referenced garment in its natural body region. Treat each garment image
as the authority for its exact color, pattern, logo, material, seams, fasteners,
and proportions. Do not copy a reference image's background or display model."""


def load_composition_garments(composition: Any) -> tuple[LoadedReferenceImage, ...]:
    """추천 카드에 저장된 원본 상품 이미지를 최대 5장 읽는다."""
    loader = ReferenceImageLoader()
    references = []
    for item in composition.items.order_by("position", "created_at")[:5]:
        snapshot = item.item_snapshot if isinstance(item.item_snapshot, dict) else {}
        source_bucket = next(
            (
                str(snapshot[key]).strip()
                for key in ("image_bucket", "s3_bucket", "source_bucket")
                if snapshot.get(key)
            ),
            "",
        )
        reference = RenderItemReference(
            item_id=str(item.source_id),
            position=item.position,
            slot=item.slot,
            source_type=RenderSource(item.source_type),
            image_ref=item.image_ref,
            source_bucket=source_bucket,
        )
        references.append(loader.load(reference))
    return tuple(references)


def load_daily_garments(result: dict[str, Any]) -> tuple[LoadedReferenceImage, ...]:
    """오늘의 룩 스냅샷에서 원본 골든셋 의류 이미지를 최대 5장 읽는다."""
    loader = ReferenceImageLoader()
    references = []
    for position, item in enumerate((result.get("items") or [])[:5], start=1):
        image_ref = str(item.get("s3_key") or "").strip()
        if not image_ref:
            continue
        reference = RenderItemReference(
            item_id=str(item.get("item_key") or position),
            position=position,
            slot=str(item.get("category") or f"garment-{position}"),
            source_type=RenderSource.GOLDENSET_ITEM,
            image_ref=image_ref,
            source_bucket=str(item.get("s3_bucket") or ""),
        )
        references.append(loader.load(reference))
    return tuple(references)


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
        profile: str = "fast",
        seed: int | None = None,
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
                    "profile": profile,
                    "seed": seed,
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


def reference_from_bytes(label: str, content: bytes) -> LoadedReferenceImage:
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
    def __init__(
        self,
        *,
        provider: GpuQwenImageProvider | None = None,
        profile: str = "fast",
        seed: int | None = None,
    ) -> None:
        self.provider = provider or GpuQwenImageProvider()
        self.profile = profile
        self.seed = seed

    def _generate(
        self, prompt: str, references: tuple[LoadedReferenceImage, ...]
    ) -> GeneratedTryOnImage:
        content, media_type, usage = self.provider.generate(
            prompt=prompt,
            references=references,
            profile=self.profile,
            seed=self.seed,
        )
        return GeneratedTryOnImage(content, media_type, usage)

    def fit_person(
        self,
        person: bytes,
        outfit: bytes,
        *,
        garments: tuple[LoadedReferenceImage, ...] = (),
    ) -> GeneratedTryOnImage:
        references = garments or (reference_from_bytes("outfit", outfit),)
        return self._generate(
            _garment_prompt(DIRECT_PROMPT, garments),
            (reference_from_bytes("target_person", person), *references),
        )

    def fit_mannequin(
        self,
        person: bytes,
        outfit: bytes,
        *,
        body_profile: dict[str, Any] | None = None,
        garments: tuple[LoadedReferenceImage, ...] = (),
    ) -> GeneratedTryOnImage:
        references = garments or (reference_from_bytes("outfit", outfit),)
        return self._generate(
            _garment_prompt(_mannequin_prompt(body_profile), garments),
            (reference_from_bytes("target_person", person), *references),
        )

    def build_mannequin(
        self,
        person: bytes,
        *,
        body_profile: dict[str, Any] | None = None,
    ) -> GeneratedTryOnImage:
        return self._generate(
            _mannequin_base_prompt(body_profile),
            (reference_from_bytes("target_person", person),),
        )

    def dress_mannequin(
        self,
        mannequin: bytes,
        outfit: bytes,
        *,
        garments: tuple[LoadedReferenceImage, ...] = (),
    ) -> GeneratedTryOnImage:
        references = garments or (reference_from_bytes("outfit", outfit),)
        return self._generate(
            _garment_prompt(MANNEQUIN_DRESS_PROMPT, garments),
            (reference_from_bytes("target_mannequin", mannequin), *references),
        )
