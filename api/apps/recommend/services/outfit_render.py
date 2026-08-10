"""골든 코디의 '정면 착용 이미지'를 만들어 둔다.

골든 원본 사진은 대개 노출 불가(exposable=False)라 사용자 화면에 쓸 수 없다.
그래서 파이프라인이 만든 아이템 이미지(흰 배경 파생물)를 참조로 넘겨, 정면을
보는 사람이 그 옷을 입은 이미지를 새로 만든다.

**코디당 한 번만 만든다.** 같은 골든 코디는 여러 사용자에게, 여러 날에 걸쳐
추천되므로 사용자마다 다시 만들 이유가 없다. 결과를 골든셋 산출물과 같은
위치에 두고, 이미 있으면 생성 없이 그 키를 그대로 쓴다. 키가 코디마다
결정적이라 별도의 캐시 테이블이 필요 없다.

    {derived}/{golden_id}/item_000.png     ← 참조 (파이프라인 산출물)
    {derived}/{golden_id}/render_frontal.png  ← 여기에 저장

경로를 아이템 키에서 유도하는 이유가 있다. derived prefix와 dataset version은
golden_set 패키지의 설정이라 api 쪽에는 없다. 아이템 키에 이미 그 경로가
들어 있으므로, 같은 설정을 두 곳에 두는 대신 키에서 디렉터리만 떼어 쓴다.
"""

from __future__ import annotations

import base64
import binascii
import logging
import posixpath
import re
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings

from apps.recommend.services import storage

logger = logging.getLogger(__name__)

RENDER_OBJECT_NAME = "render_frontal.png"

#: 응답에서 이미지 데이터를 찾을 때 쓰는 data URL 형식
_DATA_URL = re.compile(r"^data:image/(?P<ext>[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$", re.S)

PROMPT = (
    "첨부한 이미지들은 한 벌의 코디를 구성하는 개별 의상 아이템입니다.\n"
    "이 옷들을 모두 착용하고 정면을 바라보는 사람의 전신 사진을 만들어 주세요.\n"
    "요구사항:\n"
    "- 각 아이템의 색상·핏·기장·소재감·디테일을 원본 그대로 유지합니다.\n"
    "- 배경은 단색 흰색, 조명은 균일한 스튜디오 촬영처럼.\n"
    "- 전신이 잘리지 않게 머리끝부터 발끝까지 담습니다.\n"
    "- 특정 실존 인물을 닮게 만들지 않습니다.\n"
    "- 사진에 텍스트나 워터마크를 넣지 않습니다."
)


class RenderError(RuntimeError):
    """착용 이미지 생성 실패. 추천 자체를 되돌리지는 않는다."""


@dataclass(frozen=True)
class RenderRef:
    s3_bucket: str
    s3_key: str

    def as_dict(self) -> dict[str, str]:
        return {"s3_bucket": self.s3_bucket, "s3_key": self.s3_key}


def render_key_for(item_s3_key: str) -> str:
    """아이템 이미지 키에서 착용 이미지 키를 유도한다."""
    return posixpath.join(posixpath.dirname(item_s3_key), RENDER_OBJECT_NAME)


def _reference_keys(items: list[dict[str, Any]]) -> list[str]:
    keys = [str(item.get("s3_key")) for item in items if item.get("s3_key")]
    # 참조 수가 늘면 입력 토큰과 요금이 함께 오른다. 상한을 둔다.
    return keys[: settings.DAILY_LOOK_RENDER_MAX_REFERENCES]


def ensure_render(*, bucket: str, items: list[dict[str, Any]]) -> RenderRef | None:
    """착용 이미지를 보장한다. 이미 있으면 만들지 않고 그 참조만 돌려준다.

    Returns: 참조. 만들 수 없으면(참조 이미지 없음·기능 끔) None.
    Raises: RenderError — 생성을 시도했는데 실패한 경우.
    """
    reference_keys = _reference_keys(items)
    if not bucket or not reference_keys:
        logger.info("착용 이미지 생략: 버킷 또는 참조 아이템 이미지가 없습니다")
        return None

    key = render_key_for(reference_keys[0])

    # ── 재사용 ──
    if storage.exists_for(bucket, key):
        logger.info("착용 이미지 재사용: s3://%s/%s", bucket, key)
        return RenderRef(bucket, key)

    if not settings.DAILY_LOOK_RENDER_ENABLED:
        logger.info("착용 이미지 생성이 꺼져 있습니다 (DAILY_LOOK_RENDER_ENABLED=0)")
        return None

    image = _generate(bucket=bucket, reference_keys=reference_keys)
    storage.put_bytes_for(bucket, key, image, "image/png")
    logger.info(
        "착용 이미지 생성: s3://%s/%s (참조 %d장, %d bytes)",
        bucket, key, len(reference_keys), len(image),
    )
    return RenderRef(bucket, key)


def _generate(*, bucket: str, reference_keys: list[str]) -> bytes:
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise RenderError("OPENROUTER_API_KEY가 설정되지 않았습니다.")

    parts: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    for reference in reference_keys:
        raw = storage.download_for(bucket, reference)
        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(raw).decode()
                },
            }
        )

    try:
        response = requests.post(
            settings.DAILY_LOOK_RENDER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.DAILY_LOOK_RENDER_MODEL,
                "messages": [{"role": "user", "content": parts}],
                "modalities": ["image", "text"],
            },
            timeout=settings.DAILY_LOOK_RENDER_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise RenderError(f"이미지 생성 요청 실패: {exc}") from exc

    if response.status_code >= 400:
        # 모델명 오류·잔액 부족 등 실제 사유는 본문에만 담긴다.
        raise RenderError(
            f"이미지 생성 실패 {response.status_code}: {response.text[:500]}"
        )

    payload = response.json()
    image = _extract_image(payload)
    if image is None:
        raise RenderError(
            "응답에서 이미지를 찾지 못했습니다. 모델이 이미지 출력을 지원하는지 "
            f"확인하세요 (model={settings.DAILY_LOOK_RENDER_MODEL})"
        )
    return image


def _extract_image(payload: dict[str, Any]) -> bytes | None:
    """OpenRouter 응답에서 첫 이미지를 꺼낸다.

    제공자마다 담는 위치가 달라 두 자리를 모두 본다 — 메시지의 images 배열과
    content 안의 data URL. 한쪽만 보면 제공자가 바뀔 때 조용히 실패한다.
    """
    for choice in payload.get("choices") or []:
        message = choice.get("message") or {}

        for image in message.get("images") or []:
            url = (image.get("image_url") or {}).get("url") or image.get("url")
            if decoded := _decode_data_url(str(url or "")):
                return decoded

        content = message.get("content")
        if isinstance(content, str):
            if decoded := _decode_data_url(content.strip()):
                return decoded
        elif isinstance(content, list):
            for part in content:
                url = (part.get("image_url") or {}).get("url", "")
                if decoded := _decode_data_url(str(url)):
                    return decoded
    return None


def _decode_data_url(value: str) -> bytes | None:
    matched = _DATA_URL.match(value)
    if not matched:
        return None
    try:
        return base64.b64decode(matched.group("data"), validate=True)
    except (binascii.Error, ValueError):
        logger.warning("착용 이미지 base64 디코딩 실패")
        return None
