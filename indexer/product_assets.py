"""외부 쇼핑 이미지를 검증·정규화하고 S3에 보존한다."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import quote

import requests
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidProductImage(ValueError):
    """재시도해도 해결되지 않는 이미지 입력 오류."""


@dataclass(frozen=True)
class PreparedImage:
    image: Image.Image
    checksum: str
    s3_key: str


def _download_bytes(
    session: requests.Session,
    url: str,
    *,
    timeout: int,
    max_bytes: int,
) -> bytes:
    if not url:
        raise InvalidProductImage("상품 image_url이 비어 있습니다.")
    response = session.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            parsed_content_length = int(content_length)
        except ValueError:
            parsed_content_length = None
        if parsed_content_length is not None and parsed_content_length > max_bytes:
            raise InvalidProductImage(
                f"상품 이미지가 최대 허용 크기를 초과합니다: {content_length} bytes"
            )

    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        size += len(chunk)
        if size > max_bytes:
            raise InvalidProductImage(
                f"상품 이미지가 최대 허용 크기를 초과합니다: > {max_bytes} bytes"
            )
        chunks.append(chunk)
    if not chunks:
        raise InvalidProductImage("상품 이미지 응답이 비어 있습니다.")
    return b"".join(chunks)


def _normalize_jpeg(raw: bytes) -> tuple[Image.Image, bytes]:
    try:
        opened = Image.open(BytesIO(raw))
        opened.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidProductImage(
            "다운로드한 파일이 유효한 이미지가 아닙니다."
        ) from exc

    image = ImageOps.exif_transpose(opened)
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        image = background.convert("RGB")
    else:
        image = image.convert("RGB")

    output = BytesIO()
    image.save(output, format="JPEG", quality=95, optimize=True)
    return image, output.getvalue()


def download_and_store_image(
    *,
    session: requests.Session,
    s3_client,
    source: str,
    external_product_id: str,
    image_url: str,
    bucket: str,
    prefix: str,
    timeout: int,
    max_bytes: int,
) -> PreparedImage:
    raw = _download_bytes(
        session,
        image_url,
        timeout=timeout,
        max_bytes=max_bytes,
    )
    image, normalized = _normalize_jpeg(raw)
    checksum = hashlib.sha256(normalized).hexdigest()
    safe_product_id = quote(external_product_id, safe="")
    key_parts = [part for part in (prefix, source, safe_product_id) if part]
    s3_key = "/".join(key_parts + [f"{checksum}.jpg"])
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=normalized,
        ContentType="image/jpeg",
        Metadata={
            "sha256": checksum,
            "source": source,
            "product-id": safe_product_id[:200],
        },
    )
    return PreparedImage(image=image, checksum=checksum, s3_key=s3_key)
