"""채팅 추천 운영 배포 시 필수 환경변수 검사."""

from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Tags, register


def _missing(value) -> bool:
    return value in (None, "", (), [])


@register(Tags.security, deploy=True)
def chat_recommend_deployment_checks(_app_configs, **_kwargs):
    errors: list[Error] = []
    required = (
        ("REDIS_PASSWORD", settings.REDIS_PASSWORD, "recommend.E001"),
        ("QDRANT_API_KEY", settings.QDRANT_API_KEY, "recommend.E002"),
        ("OPENAI_API_KEY", settings.OPENAI_API_KEY, "recommend.E003"),
        (
            "CHAT_GOLDENSET_DATASET_VERSION",
            settings.CHAT_GOLDENSET_DATASET_VERSION,
            "recommend.E004",
        ),
        (
            "CHAT_GOLDENSET_DATASET_STATUSES",
            settings.CHAT_GOLDENSET_DATASET_STATUSES,
            "recommend.E005",
        ),
    )
    for name, value, error_id in required:
        if _missing(value):
            errors.append(
                Error(
                    f"운영 채팅 추천에 필요한 {name} 환경변수가 비어 있습니다.",
                    hint="Infisical/AWS Secrets Manager 또는 배포 환경변수로 주입하세요.",
                    id=error_id,
                )
            )

    if settings.OUTFIT_RENDER_ENABLED:
        render_required = (
            ("OPENROUTER_API_KEY", settings.OPENROUTER_API_KEY, "recommend.E006"),
            (
                "OUTFIT_RENDER_RESULT_BUCKET",
                settings.OUTFIT_RENDER_RESULT_BUCKET,
                "recommend.E007",
            ),
        )
        for name, value, error_id in render_required:
            if _missing(value):
                errors.append(
                    Error(
                        f"코디 이미지 생성이 활성화됐지만 {name}이 비어 있습니다.",
                        hint="기능을 끄거나 운영용 시크릿·비공개 S3 버킷을 설정하세요.",
                        id=error_id,
                    )
                )
    if settings.VIRTUAL_TRY_ON_ENABLED:
        vton_required = (
            ("VTON_GPU_URL", settings.VTON_GPU_URL, "recommend.E008"),
            ("VTON_GPU_TOKEN", settings.VTON_GPU_TOKEN, "recommend.E009"),
            (
                "OUTFIT_RENDER_RESULT_BUCKET",
                settings.OUTFIT_RENDER_RESULT_BUCKET,
                "recommend.E010",
            ),
        )
        for name, value, error_id in vton_required:
            if _missing(value):
                errors.append(
                    Error(
                        f"가상 착장이 활성화됐지만 {name}이 비어 있습니다.",
                        hint="기능을 끄거나 운영용 시크릿·비공개 S3 버킷을 설정하세요.",
                        id=error_id,
                    )
                )
    return errors
