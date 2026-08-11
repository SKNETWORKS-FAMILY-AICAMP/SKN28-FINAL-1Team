"""옷장·상품·골든셋 이미지가 섞인 최종 코디의 착용 이미지 생성.

이 모듈은 동기적인 핵심 렌더 함수만 소유한다. 실행 큐, 생성 결과 저장, 캐시와
사용자 접근 제어는 다음 단계의 이미지 작업 계층이 담당한다.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import logging
import re
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any
from urllib.parse import unquote, urlsplit

import requests
from django.conf import settings

from apps.recommend.models import OutfitComposition
from apps.recommend.services import storage

logger = logging.getLogger(__name__)

PROMPT_VERSION = "mixed-outfit-render-v2"
BASE_PROMPT = (
    "첨부한 참조 이미지들은 한 벌의 코디에 최종 선택된 개별 의상입니다.\n"
    "참조 이미지의 의상을 모두 착용하고 정면을 바라보는 한 사람의 전신 패션 사진을 "
    "생성해 주세요.\n"
    "요구사항:\n"
    "- 모든 참조 의상을 빠짐없이 한 코디에 사용합니다.\n"
    "- 각 의상의 색상, 패턴, 핏, 기장, 소재감과 디테일을 유지합니다.\n"
    "- 아이템을 임의로 다른 디자인이나 색상으로 교체하지 않습니다.\n"
    "- 배경은 단색 흰색이고 조명은 균일한 스튜디오 촬영 형태입니다.\n"
    "- 머리끝부터 발끝까지 잘리지 않은 정면 전신 구도입니다.\n"
    "- 특정 실존 인물을 닮게 만들지 않습니다.\n"
    "- 텍스트, 로고나 워터마크를 추가하지 않습니다."
)

_DATA_URL = re.compile(
    r"^data:image/(?P<subtype>[a-zA-Z0-9.+-]+);base64,(?P<data>.+)$",
    re.DOTALL,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OutfitRenderError(RuntimeError):
    """코디 이미지 생성 공통 오류."""


class RenderDisabled(OutfitRenderError):
    """환경 설정에서 이미지 생성이 비활성화됨."""


class RenderInputError(OutfitRenderError):
    """검증된 코디나 참조 이미지 계약이 올바르지 않음."""


class ReferenceImageError(OutfitRenderError):
    """S3 또는 외부 URL에서 참조 이미지를 안전하게 읽지 못함."""


class RenderProviderError(OutfitRenderError):
    """이미지 생성 제공자 호출 또는 응답 해석 실패."""


class RenderSource(StrEnum):
    WARDROBE = "WARDROBE"
    PRODUCT = "PRODUCT"
    GOLDENSET_ITEM = "GOLDENSET_ITEM"


@dataclass(frozen=True)
class RenderItemReference:
    item_id: str
    position: int
    slot: str
    source_type: RenderSource
    image_ref: str
    source_bucket: str = ""


@dataclass(frozen=True)
class OutfitRenderRequest:
    composition_id: str
    composition_fingerprint: str
    items: tuple[RenderItemReference, ...]
    subject_presentation: str = ""


@dataclass(frozen=True)
class LoadedReferenceImage:
    item: RenderItemReference
    content: bytes
    media_type: str

    def data_url(self) -> str:
        encoded = base64.b64encode(self.content).decode("ascii")
        return f"data:{self.media_type};base64,{encoded}"


@dataclass(frozen=True)
class RenderedOutfit:
    content: bytes
    media_type: str
    provider: str
    model: str
    prompt_version: str
    composition_fingerprint: str
    reference_count: int
    usage: dict[str, Any] = field(default_factory=dict)


def _detect_media_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ReferenceImageError("지원하는 JPEG, PNG, WebP 이미지가 아닙니다.")


def _snapshot_bucket(snapshot: object) -> str:
    if not isinstance(snapshot, dict):
        return ""
    for key in ("image_bucket", "s3_bucket", "source_bucket"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _default_bucket(source_type: RenderSource) -> str:
    return {
        RenderSource.WARDROBE: settings.OUTFIT_RENDER_WARDROBE_BUCKET,
        RenderSource.PRODUCT: settings.OUTFIT_RENDER_PRODUCT_BUCKET,
        RenderSource.GOLDENSET_ITEM: settings.OUTFIT_RENDER_GOLDENSET_BUCKET,
    }[source_type]


def _validate_public_image_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ReferenceImageError("외부 참조 이미지는 유효한 HTTPS URL이어야 합니다.")
    if parsed.username or parsed.password:
        raise ReferenceImageError(
            "인증정보가 포함된 외부 이미지 URL은 허용하지 않습니다."
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise ReferenceImageError(
            "외부 이미지 URL의 포트가 올바르지 않습니다."
        ) from exc
    if port not in (None, 443):
        raise ReferenceImageError("외부 이미지 URL은 HTTPS 기본 포트만 허용합니다.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise ReferenceImageError("로컬 네트워크 이미지 URL은 허용하지 않습니다.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ReferenceImageError("공개 IP가 아닌 이미지 URL은 허용하지 않습니다.")
    return value


class ReferenceImageLoader:
    """서로 다른 출처의 image_ref를 동일한 이미지 바이트 계약으로 변환한다."""

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def load(self, item: RenderItemReference) -> LoadedReferenceImage:
        image_ref = item.image_ref.strip()
        if not image_ref:
            raise ReferenceImageError(f"{item.slot} 슬롯의 이미지 참조가 없습니다.")

        if image_ref.startswith("s3://"):
            content = self._load_s3_uri(image_ref)
        elif image_ref.startswith(("https://", "http://")):
            content = self._load_https(image_ref)
        else:
            bucket = item.source_bucket or _default_bucket(item.source_type)
            if not bucket:
                raise ReferenceImageError(
                    f"{item.source_type.value} 이미지 버킷이 설정되지 않았습니다."
                )
            content = self._load_s3(bucket, image_ref)
        return LoadedReferenceImage(
            item=item,
            content=content,
            media_type=_detect_media_type(content),
        )

    @staticmethod
    def _load_s3_uri(image_ref: str) -> bytes:
        parsed = urlsplit(image_ref)
        bucket = parsed.netloc.strip()
        key = unquote(parsed.path.lstrip("/"))
        if not bucket or not key:
            raise ReferenceImageError("유효하지 않은 S3 이미지 참조입니다.")
        return ReferenceImageLoader._load_s3(bucket, key)

    @staticmethod
    def _load_s3(bucket: str, key: str) -> bytes:
        try:
            return storage.download_for(
                bucket,
                key,
                max_bytes=settings.OUTFIT_RENDER_MAX_REFERENCE_BYTES,
            )
        except Exception as exc:
            raise ReferenceImageError(
                f"S3 참조 이미지를 읽지 못했습니다: s3://{bucket}/{key}"
            ) from exc

    def _load_https(self, image_ref: str) -> bytes:
        url = _validate_public_image_url(image_ref)
        try:
            response = self.session.get(
                url,
                stream=True,
                allow_redirects=False,
                timeout=settings.OUTFIT_RENDER_REFERENCE_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ReferenceImageError(f"외부 참조 이미지 요청 실패: {exc}") from exc

        try:
            if 300 <= response.status_code < 400:
                raise ReferenceImageError(
                    "외부 이미지 URL의 리다이렉트는 안전을 위해 허용하지 않습니다."
                )
            if response.status_code >= 400:
                raise ReferenceImageError(
                    f"외부 참조 이미지 응답 오류: HTTP {response.status_code}"
                )
            raw_length = response.headers.get("Content-Length")
            try:
                content_length = int(raw_length) if raw_length else None
            except (TypeError, ValueError):
                content_length = None
            limit = settings.OUTFIT_RENDER_MAX_REFERENCE_BYTES
            if content_length is not None and content_length > limit:
                raise ReferenceImageError(
                    f"외부 참조 이미지가 허용 크기 {limit} bytes를 초과합니다."
                )

            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > limit:
                    raise ReferenceImageError(
                        f"외부 참조 이미지가 허용 크기 {limit} bytes를 초과합니다."
                    )
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            response.close()


class OpenRouterQwenImageProvider:
    provider_name = "openrouter"

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def generate(
        self,
        *,
        prompt: str,
        references: tuple[LoadedReferenceImage, ...],
    ) -> tuple[bytes, str, dict[str, Any]]:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise RenderProviderError("OPENROUTER_API_KEY가 설정되지 않았습니다.")

        body = {
            "model": settings.OUTFIT_RENDER_MODEL,
            "prompt": prompt,
            "input_references": [
                {
                    "type": "image_url",
                    "image_url": {"url": reference.data_url()},
                }
                for reference in references
            ],
            "aspect_ratio": settings.OUTFIT_RENDER_ASPECT_RATIO,
            "resolution": settings.OUTFIT_RENDER_RESOLUTION,
            "n": 1,
        }
        try:
            response = self.session.post(
                settings.OUTFIT_RENDER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=settings.OUTFIT_RENDER_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise RenderProviderError(f"이미지 생성 요청 실패: {exc}") from exc

        try:
            if response.status_code >= 400:
                raise RenderProviderError(
                    f"이미지 생성 실패 HTTP {response.status_code}: {response.text[:500]}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise RenderProviderError(
                    "이미지 생성 응답이 JSON이 아닙니다."
                ) from exc
        finally:
            response.close()
        if not isinstance(payload, dict):
            raise RenderProviderError("이미지 생성 응답 형식이 올바르지 않습니다.")

        image = _extract_generated_image(payload)
        if image is None:
            raise RenderProviderError(
                "이미지 생성 응답에서 이미지 데이터를 찾지 못했습니다. "
                f"(model={settings.OUTFIT_RENDER_MODEL})"
            )
        if len(image) > settings.OUTFIT_RENDER_MAX_OUTPUT_BYTES:
            raise RenderProviderError(
                "생성 이미지가 허용 크기를 초과합니다: "
                f"{len(image)} > {settings.OUTFIT_RENDER_MAX_OUTPUT_BYTES} bytes"
            )
        try:
            media_type = _detect_media_type(image)
        except ReferenceImageError as exc:
            raise RenderProviderError(
                "생성 결과가 지원하는 이미지 형식이 아닙니다."
            ) from exc
        usage = payload.get("usage")
        return image, media_type, usage if isinstance(usage, dict) else {}


class OutfitRenderService:
    """검증 완료 코디를 정확히 한 번의 혼합 참조 이미지 요청으로 변환한다."""

    def __init__(
        self,
        *,
        loader: ReferenceImageLoader | None = None,
        provider: OpenRouterQwenImageProvider | None = None,
    ) -> None:
        self.loader = loader or ReferenceImageLoader()
        self.provider = provider or OpenRouterQwenImageProvider()

    def build_request(self, composition: OutfitComposition) -> OutfitRenderRequest:
        if composition.status != OutfitComposition.Status.VALIDATED:
            raise RenderInputError("검증을 통과한 코디만 이미지로 생성할 수 있습니다.")
        fingerprint = composition.composition_fingerprint.strip().lower()
        if not _SHA256.fullmatch(fingerprint):
            raise RenderInputError("유효한 코디 조합 fingerprint가 필요합니다.")

        references: list[RenderItemReference] = []
        for item in composition.items.order_by("position", "created_at"):
            try:
                source_type = RenderSource(item.source_type)
            except ValueError as exc:
                raise RenderInputError(
                    f"지원하지 않는 아이템 출처입니다: {item.source_type}"
                ) from exc
            references.append(
                RenderItemReference(
                    item_id=str(item.id),
                    position=item.position,
                    slot=item.slot,
                    source_type=source_type,
                    image_ref=item.image_ref.strip(),
                    source_bucket=_snapshot_bucket(item.item_snapshot),
                )
            )
        return self._validate_request(
            OutfitRenderRequest(
                composition_id=str(composition.id),
                composition_fingerprint=fingerprint,
                items=tuple(references),
            )
        )

    def render(self, composition: OutfitComposition) -> RenderedOutfit:
        return self.render_request(self.build_request(composition))

    def render_request(self, request: OutfitRenderRequest) -> RenderedOutfit:
        if not settings.OUTFIT_RENDER_ENABLED:
            raise RenderDisabled("코디 이미지 생성 기능이 비활성화되어 있습니다.")
        request = self._validate_request(request)

        references = tuple(self.loader.load(item) for item in request.items)
        total_bytes = sum(len(reference.content) for reference in references)
        if total_bytes > settings.OUTFIT_RENDER_MAX_TOTAL_REFERENCE_BYTES:
            raise RenderInputError(
                "참조 이미지 전체 크기가 허용 한도를 초과합니다: "
                f"{total_bytes} > {settings.OUTFIT_RENDER_MAX_TOTAL_REFERENCE_BYTES} bytes"
            )

        content, media_type, usage = self.provider.generate(
            prompt=self._prompt(request),
            references=references,
        )
        return RenderedOutfit(
            content=content,
            media_type=media_type,
            provider=self.provider.provider_name,
            model=settings.OUTFIT_RENDER_MODEL,
            prompt_version=PROMPT_VERSION,
            composition_fingerprint=request.composition_fingerprint,
            reference_count=len(references),
            usage=usage,
        )

    @staticmethod
    def _validate_request(request: OutfitRenderRequest) -> OutfitRenderRequest:
        if not request.composition_id.strip():
            raise RenderInputError("composition_id가 필요합니다.")
        fingerprint = request.composition_fingerprint.strip().lower()
        if not _SHA256.fullmatch(fingerprint):
            raise RenderInputError("유효한 코디 조합 fingerprint가 필요합니다.")
        if fingerprint != request.composition_fingerprint:
            request = replace(request, composition_fingerprint=fingerprint)
        presentation = request.subject_presentation.strip().lower()
        if presentation not in {"", "man", "woman", "unisex"}:
            raise RenderInputError(
                "subject_presentation은 man/woman/unisex 중 하나여야 합니다."
            )
        if presentation != request.subject_presentation:
            request = replace(request, subject_presentation=presentation)
        if not request.items:
            raise RenderInputError("최소 하나의 코디 아이템 이미지가 필요합니다.")
        if len(request.items) > settings.OUTFIT_RENDER_MAX_REFERENCES:
            raise RenderInputError(
                "코디 아이템 이미지 수가 허용 한도를 초과합니다: "
                f"{len(request.items)} > {settings.OUTFIT_RENDER_MAX_REFERENCES}"
            )
        positions = [item.position for item in request.items]
        if positions != sorted(positions) or len(positions) != len(set(positions)):
            raise RenderInputError(
                "코디 아이템 position은 중복 없이 오름차순이어야 합니다."
            )
        slots = [item.slot for item in request.items]
        if len(slots) != len(set(slots)):
            raise RenderInputError("코디 아이템 slot은 중복될 수 없습니다.")
        for item in request.items:
            if not item.slot.strip() or not item.image_ref.strip():
                raise RenderInputError(
                    "모든 코디 아이템에 slot과 image_ref가 필요합니다."
                )
        return request

    @staticmethod
    def _prompt(request: OutfitRenderRequest) -> str:
        reference_map = "\n".join(
            f"{index}. slot={item.slot}, source={item.source_type.value}"
            for index, item in enumerate(request.items, start=1)
        )
        presentation = {
            "man": "남성 모델",
            "woman": "여성 모델",
            "unisex": "중성적인 모델",
        }.get(request.subject_presentation, "사용자 성별을 특정하지 않은 모델")
        return (
            f"{BASE_PROMPT}\n\n착용 모델 표현: {presentation}\n"
            f"참조 이미지 순서:\n{reference_map}"
        )


def _extract_generated_image(payload: dict[str, Any]) -> bytes | None:
    for row in payload.get("data") or []:
        if not isinstance(row, dict):
            continue
        if (encoded := row.get("b64_json")) and (
            decoded := _decode_base64(str(encoded))
        ):
            return decoded
        if (url := row.get("url")) and (decoded := _decode_data_url(str(url))):
            return decoded

    for choice in payload.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        if not isinstance(message, dict):
            continue
        for image in message.get("images") or []:
            if not isinstance(image, dict):
                continue
            nested = image.get("image_url") or {}
            url = nested.get("url") if isinstance(nested, dict) else None
            if decoded := _decode_data_url(str(url or image.get("url") or "")):
                return decoded
        content = message.get("content")
        if isinstance(content, str):
            if decoded := _decode_data_url(content.strip()):
                return decoded
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                nested = part.get("image_url") or {}
                url = nested.get("url") if isinstance(nested, dict) else ""
                if decoded := _decode_data_url(str(url)):
                    return decoded
    return None


def _decode_base64(value: str) -> bytes | None:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        logger.warning("생성 이미지 base64 디코딩 실패")
        return None


def _decode_data_url(value: str) -> bytes | None:
    matched = _DATA_URL.fullmatch(value)
    return _decode_base64(matched.group("data")) if matched else None
