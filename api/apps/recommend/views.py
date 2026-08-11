import logging
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OutfitAnalysis
from .serializers import (
    OutfitAnalysisAcceptedSerializer,
    OutfitAnalysisClaimRequestSerializer,
    OutfitAnalysisClaimResponseSerializer,
    OutfitAnalysisDetailSerializer,
    OutfitAnalysisListItemSerializer,
    OutfitAnalysisListResponseSerializer,
    OutfitAnalysisPublicSerializer,
    OutfitAnalysisRequestSerializer,
)
from .serializers import DailyLookSerializer
from .services import analysis as analysis_service
from .services import claim as claim_service
from .services import daily_look as daily_look_service

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 100


def _positive_int(raw: str | None, *, default: int) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


# ──────────────────────────────────────────────────────────────
# 조회 응답 예시 (Swagger)
#
# 이 엔드포인트는 인증 여부에 따라 응답 모양이 둘로 갈린다. 스키마에 한쪽만
# 적어두면 나머지 한쪽의 필드(사진 URL·체형 스냅샷·옷장 연계)가 문서에 아예
# 드러나지 않으므로 oneOf로 둘 다 노출하고, 예시로 구분한다.
# ──────────────────────────────────────────────────────────────

_EVALUATION_EXAMPLE = {
    "overall_score": 88,
    "summary": "색상 조화가 안정적이고 계절감에 맞는 코디입니다.",
    "strengths": ["상하의 명도 대비가 좋습니다.", "실루엣이 깔끔합니다."],
    "weather_comment": "현재 기온 24도에 적당한 두께입니다.",
    "personalization_comment": "선호하시는 미니멀 무드와 잘 맞습니다.",
    "styling_tips": ["밝은 색 가방을 더하면 포인트가 생깁니다."],
}
_WEATHER_EXAMPLE = {
    "region": "서울특별시 종로구",
    "temperature": 24.0,
    "sky_state": "맑음",
    "is_stale": False,
    "observed_at": "2026-08-06T14:00:00+09:00",
}

ANONYMOUS_RESULT_EXAMPLE = OpenApiExample(
    name="비로그인 조회 (축소 응답)",
    description=(
        "UUID만 알면 볼 수 있는 응답이라 사진 URL·체형 스냅샷·LLM 원본은 빠진다. "
        "옷장은 사용자 소유 데이터라 `wardrobe` 키 자체가 없다."
    ),
    value={
        "analysis_id": "9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f",
        "status": "SUCCEEDED",
        "evaluation": _EVALUATION_EXAMPLE,
        "context": {
            "weather": _WEATHER_EXAMPLE,
            "personalized": False,
            "used_pursuit": False,
            "used_body": False,
        },
        "poll_after_ms": None,
        "detail": None,
        "created_at": "2026-08-06T14:58:02+09:00",
        "finished_at": "2026-08-06T14:58:29+09:00",
    },
    response_only=True,
)

OWNER_WARDROBE_DONE_EXAMPLE = OpenApiExample(
    name="본인 조회 · 옷장 등록까지 완료(DONE)",
    description=(
        "`save_to_wardrobe=true`로 접수한 건을 본인 토큰으로 조회한 경우. "
        "`wardrobe.status`가 DONE이라 `wardrobe.items`에 생성된 아이템 요약이 채워진다."
    ),
    value={
        "id": "9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f",
        "status": "SUCCEEDED",
        "image_url": "https://s3.ap-northeast-2.amazonaws.com/…/original.jpg?X-Amz-Signature=…",
        "image_content_type": "image/jpeg",
        "image_bytes": 2481920,
        "requested_lat": 37.5729,
        "requested_lon": 126.9794,
        "resolved_lat": 37.5729,
        "resolved_lon": 126.9794,
        "weather": _WEATHER_EXAMPLE,
        "body": {"gender": "female", "height": 165, "weight": 52},
        "pursuit": {
            "preferred": {"styles": ["미니멀", "캐주얼"]},
            "avoided": {"styles": ["스포티"]},
        },
        "personalized": True,
        "save_to_wardrobe": True,
        "wardrobe_job": "3f2a7c81-2b44-4a90-9c1e-77d0f5a1b2c3",
        "wardrobe": {
            "job_id": "3f2a7c81-2b44-4a90-9c1e-77d0f5a1b2c3",
            "status": "DONE",
            "error_message": "",
            "created_at": "2026-08-06T14:58:03+09:00",
            "finished_at": "2026-08-06T14:59:41+09:00",
            "items": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "item_name": "화이트 옥스포드 셔츠",
                    "category_large": "상의",
                    "category_small": "셔츠",
                    "color": "화이트",
                    "image_url": "https://s3.ap-northeast-2.amazonaws.com/…/item_01.png?X-Amz-Signature=…",
                    "confirmed": False,
                },
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "item_name": "연청 슬림 진",
                    "category_large": "하의",
                    "category_small": "청바지",
                    "color": "블루",
                    "image_url": "https://s3.ap-northeast-2.amazonaws.com/…/item_02.png?X-Amz-Signature=…",
                    "confirmed": False,
                },
            ],
        },
        "llm_model": "gemini-3.5-flash",
        "request_payload": {
            "systemInstruction": {"parts": [{"text": "당신은 패션 스타일리스트입니다…"}]},
            "contents": [
                {
                    "parts": [
                        {"text": "날씨: 서울특별시 종로구 24도 맑음…"},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": "<image omitted: 184320 bytes>",
                            }
                        },
                    ]
                }
            ],
        },
        "response_payload": {
            "candidates": [{"content": {"parts": [{"text": "{\"overall_score\": 88, …}"}]}}],
            "usageMetadata": {"totalTokenCount": 1234},
        },
        "evaluation": _EVALUATION_EXAMPLE,
        "llm_image_bytes": 184320,
        "latency_ms": 8452,
        "attempts": 1,
        "error_message": "",
        "created_at": "2026-08-06T14:58:02+09:00",
        "started_at": "2026-08-06T14:58:05+09:00",
        "finished_at": "2026-08-06T14:58:29+09:00",
    },
    response_only=True,
)

OWNER_WARDROBE_PENDING_EXAMPLE = OpenApiExample(
    name="본인 조회 · 평가는 끝났지만 옷장은 진행 중",
    description=(
        "**프론트가 가장 주의해야 할 상태.** 옷장 등록은 GPU 서버 → 콜백이라 "
        "평가가 SUCCEEDED가 된 뒤에도 진행 중일 수 있다. `evaluation`만 보고 폴링을 "
        "멈추면 옷장 아이템을 끝내 받지 못한다 — `wardrobe.status`가 DONE/FAILED가 "
        "될 때까지 이어가야 한다. 지면 관계상 일부 필드는 생략했다."
    ),
    value={
        "id": "9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f",
        "status": "SUCCEEDED",
        "personalized": True,
        "save_to_wardrobe": True,
        "wardrobe_job": "3f2a7c81-2b44-4a90-9c1e-77d0f5a1b2c3",
        "wardrobe": {
            "job_id": "3f2a7c81-2b44-4a90-9c1e-77d0f5a1b2c3",
            "status": "PROCESSING",
            "error_message": "",
            "created_at": "2026-08-06T14:58:03+09:00",
            "finished_at": None,
            "items": [],
        },
        "evaluation": _EVALUATION_EXAMPLE,
        "error_message": "",
        "created_at": "2026-08-06T14:58:02+09:00",
        "finished_at": "2026-08-06T14:58:29+09:00",
    },
    response_only=True,
)

OWNER_NO_WARDROBE_EXAMPLE = OpenApiExample(
    name="본인 조회 · 옷장 미연계",
    description="`save_to_wardrobe`를 요청하지 않으면 `wardrobe`는 null이다. 일부 필드 생략.",
    value={
        "id": "9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f",
        "status": "SUCCEEDED",
        "personalized": True,
        "save_to_wardrobe": False,
        "wardrobe_job": None,
        "wardrobe": None,
        "evaluation": _EVALUATION_EXAMPLE,
        "error_message": "",
        "created_at": "2026-08-06T14:58:02+09:00",
        "finished_at": "2026-08-06T14:58:29+09:00",
    },
    response_only=True,
)


class OutfitAnalysisView(APIView):
    """코디 사진을 접수하고 분석은 워커에 넘긴다 (Gemini를 여기서 호출하지 않는다)."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="outfit_analysis_create",
        tags=["Outfit Analysis"],
        summary="AI 코디 사진 평가 접수 (비동기)",
        description=(
            "코디 사진과 선택적인 위치를 multipart/form-data로 받아 **접수만 하고 202를 반환**합니다. "
            "분석은 백그라운드 워커가 처리하므로, 응답의 `poll_url`을 `poll_after_ms` 간격으로 "
            "조회해 결과를 받아가세요 (보통 30초 내외).\n\n"
            "인증 없이 호출할 수 있으며, 유효한 JWT를 보내면 저장된 추구미·체형·성별을 평가에 반영합니다. "
            "평가에 사용한 날씨·체형·추구미는 **접수 시점 값으로 고정**되어, 대기 중 날씨가 바뀌어도 "
            "사진을 올린 순간의 조건으로 평가합니다.\n\n"
            "`save_to_wardrobe=true`(로그인 전용)로 보내면 같은 사진을 옷장 아이템 등록 "
            "파이프라인에도 넘기고, 응답의 `wardrobe_job_id`로 등록 진행 상황을 따로 조회할 수 있습니다. "
            "옷장 등록이 실패해도 코디 평가 접수는 그대로 진행됩니다.\n\n"
            "비로그인으로 접수하면 응답에 `claim_token`이 함께 옵니다. **이 응답에서만 받을 수 있으니** "
            "앱이 보관했다가 로그인 직후 `POST /api/v1/outfits/analyses/claim/` 으로 보내면 "
            "그 평가 기록의 소유권을 계정으로 가져올 수 있습니다 (유효 시간이 짧습니다)."
        ),
        request=OutfitAnalysisRequestSerializer,
        responses={
            202: OutfitAnalysisAcceptedSerializer,
            400: OpenApiResponse(description="파일 또는 좌표가 유효하지 않음"),
            415: OpenApiResponse(description="multipart/form-data가 아닌 요청"),
            503: OpenApiResponse(description="사진 저장소 또는 처리 대기열 장애"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = OutfitAnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            analysis = analysis_service.accept_analysis(
                request.user,
                data["image"],
                lat=data.get("lat"),
                lon=data.get("lon"),
                save_to_wardrobe=data.get("save_to_wardrobe", False),
            )
        except analysis_service.AnalysisAcceptError as exc:
            return Response(
                {"detail": exc.detail}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        response_serializer = OutfitAnalysisAcceptedSerializer(
            data={
                "analysis_id": str(analysis.pk),
                "status": analysis.status,
                "poll_url": reverse(
                    "recommend:outfit-analysis-detail", args=[analysis.pk]
                ),
                "poll_after_ms": settings.OUTFIT_POLL_AFTER_MS,
                "estimated_seconds": settings.OUTFIT_ESTIMATED_SECONDS,
                "claim_token": claim_service.issue_token(analysis),
                "wardrobe_job_id": (
                    str(analysis.wardrobe_job_id) if analysis.wardrobe_job_id else None
                ),
            }
        )
        response_serializer.is_valid(raise_exception=True)
        return Response(
            response_serializer.validated_data, status=status.HTTP_202_ACCEPTED
        )


class OutfitAnalysisHistoryView(APIView):
    """GET /api/v1/outfits/analyses/ — 내 코디 평가 이력 목록.

    익명 요청 기록(user=NULL)은 소유자를 특정할 수 없어 조회 대상이 아니다.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="outfit_analysis_list",
        tags=["Outfit Analysis"],
        summary="내 코디 평가 이력 목록",
        parameters=[
            OpenApiParameter(
                "status",
                description="상태 필터 (QUEUED/PROCESSING/SUCCEEDED/FAILED)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                "limit",
                description=(
                    f"페이지 크기 (기본 {DEFAULT_HISTORY_LIMIT}, 최대 {MAX_HISTORY_LIMIT})"
                ),
                required=False,
                type=int,
            ),
            OpenApiParameter(
                "offset", description="건너뛸 개수", required=False, type=int
            ),
        ],
        responses={200: OutfitAnalysisListResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        queryset = OutfitAnalysis.objects.filter(user=request.user)
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        limit = min(
            _positive_int(request.query_params.get("limit"), default=DEFAULT_HISTORY_LIMIT),
            MAX_HISTORY_LIMIT,
        )
        offset = _positive_int(request.query_params.get("offset"), default=0)

        total = queryset.count()
        page = queryset[offset : offset + limit]
        return Response(
            {
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": OutfitAnalysisListItemSerializer(page, many=True).data,
            }
        )


class OutfitAnalysisDetailView(APIView):
    """GET /api/v1/outfits/analyses/{analysis_id}/ — 진행 상태 겸 결과 조회.

    프론트가 폴링하는 엔드포인트이자 최종 결과를 받는 엔드포인트다. 미완료 응답이
    수십 바이트라 별도 status 엔드포인트를 두지 않았다.

    권한:
    - 익명 접수 기록(user=NULL) → UUID를 아는 사람이면 조회 가능. UUID4는 122비트
      랜덤이라 사실상 추측할 수 없다. 다만 URL은 로그·Referer로 샐 수 있으므로
      응답에서 사진 URL·체형·LLM 원본을 빼고, 접수 후 일정 시간이 지나면 닫는다.
    - 로그인 사용자 기록 → 본인 토큰이 있어야 한다.

    없는 기록과 권한 없는 기록을 모두 404로 처리한다 (403은 "그 UUID는 존재한다"를
    알려주는 셈이라 익명 기록의 존재 여부를 캐볼 수 있게 된다).
    """

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="outfit_analysis_retrieve",
        tags=["Outfit Analysis"],
        summary="코디 평가 상태·결과 조회 (폴링용)",
        description=(
            "접수 응답의 `analysis_id`로 진행 상태와 결과를 조회합니다. "
            "`status`가 QUEUED/PROCESSING이면 `poll_after_ms` 뒤에 다시 호출하세요.\n\n"
            "비로그인 접수 건은 토큰 없이 조회할 수 있으며 접수 후 일정 시간이 지나면 닫힙니다"
            " (OUTFIT_ANON_TTL_HOURS, 기본 24시간). "
            "로그인 상태로 접수한 건은 본인 토큰이 있어야 하고, 이 경우 질의에 쓴 "
            "체형·추구미 스냅샷과 LLM 요청·응답 원본까지 함께 내려갑니다.\n\n"
            "`save_to_wardrobe=true`로 접수한 건은 본인 조회 응답에 `wardrobe` 객체가 함께 옵니다 "
            "(연계하지 않았으면 null). 옷장 등록은 별도 파이프라인이라 평가가 SUCCEEDED가 된 뒤에도 "
            "`wardrobe.status`는 아직 PENDING/PROCESSING일 수 있으며, **DONE이 되면** "
            "`wardrobe.items`에 생성된 아이템 요약(이름·분류·색상·이미지 URL·확정 여부)이 채워집니다. "
            "전체 태그가 필요하면 GET /api/v1/wardrobe/uploads/{job_id}/ 를 쓰세요.\n\n"
            "아래 **Example** 드롭다운에서 비로그인·본인 응답과 옷장 상태별 샘플을 골라 볼 수 있습니다."
        ),
        responses={
            # 인증 여부에 따라 모양이 달라지므로 둘 다 싣는다. Public만 적어두면
            # 사진 URL·체형 스냅샷·wardrobe 같은 소유자 전용 필드가 문서에 안 나온다.
            200: PolymorphicProxySerializer(
                component_name="OutfitAnalysisResult",
                serializers=[
                    OutfitAnalysisPublicSerializer,
                    OutfitAnalysisDetailSerializer,
                ],
                resource_type_field_name=None,
            ),
            404: OpenApiResponse(description="존재하지 않거나, 본인 기록이 아니거나, 조회 기간이 지남"),
        },
        examples=[
            OWNER_WARDROBE_DONE_EXAMPLE,
            OWNER_WARDROBE_PENDING_EXAMPLE,
            OWNER_NO_WARDROBE_EXAMPLE,
            ANONYMOUS_RESULT_EXAMPLE,
        ],
    )
    def get(self, request: Request, analysis_id) -> Response:
        # 상세 응답은 옷장 연계 job과 그 아이템까지 싣는다 — 미리 당기지 않으면 직렬화에서 쿼리가 더 난다.
        # 익명 응답에는 옷장이 없지만, 익명은 애초에 wardrobe_job이 NULL이라 빈 join 1번이 전부다.
        analysis = (
            OutfitAnalysis.objects.select_related("wardrobe_job")
            .prefetch_related("wardrobe_job__items")
            .filter(pk=analysis_id)
            .first()
        )
        if analysis is None:
            raise NotFound("평가 기록을 찾을 수 없습니다.")

        if analysis.user_id is None:
            deadline = timezone.now() - timedelta(
                hours=settings.OUTFIT_ANON_TTL_HOURS
            )
            if analysis.created_at < deadline:
                raise NotFound("조회 기간이 지난 평가 기록입니다.")
            return Response(OutfitAnalysisPublicSerializer(analysis).data)

        if not request.user.is_authenticated or analysis.user_id != request.user.pk:
            raise NotFound("평가 기록을 찾을 수 없습니다.")
        return Response(OutfitAnalysisDetailSerializer(analysis).data)


class OutfitAnalysisClaimView(APIView):
    """POST /api/v1/outfits/analyses/claim/ — 익명 접수 건의 소유권을 계정으로 가져온다.

    비로그인으로 평가하고 로그인한 사용자가, 앱에 보관해 둔 `claim_token`들을 한 번에
    넘긴다. 평가는 **다시 하지 않고** 주인만 바꾼다.

    조회와 달리 UUID만으로는 허용하지 않는다 — claim은 쓰기이고, 성공하면 소유자
    응답으로 바뀌어 사진 URL과 체형 스냅샷까지 열리는 권한 상승 경로다.
    자세한 근거는 services/claim.py 참고.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="outfit_analysis_claim",
        tags=["Outfit Analysis"],
        summary="비로그인 코디 평가 소유권 이전",
        description=(
            "로그인 직후, 비로그인 상태에서 접수했던 평가 기록을 계정으로 가져옵니다. "
            "접수 응답에서 받은 `claim_token`을 그대로 보내세요(토큰 안에 대상 식별자가 있습니다).\n\n"
            "평가 결과는 다시 계산하지 않습니다. 비로그인 접수 건은 추구미·체형이 반영되지 않은 "
            "상태로 평가가 끝나 있으므로, 이력에서도 개인화되지 않은 결과로 남습니다.\n\n"
            "**주의**: 이전이 끝나면 그 기록은 더 이상 익명 조회가 되지 않습니다. "
            "분석이 진행 중인 건을 넘겨받았다면 이후 폴링에는 반드시 Authorization 헤더를 실어야 "
            "하며, 그렇지 않으면 404가 납니다."
        ),
        request=OutfitAnalysisClaimRequestSerializer,
        responses={
            200: OutfitAnalysisClaimResponseSerializer,
            400: OpenApiResponse(description="토큰 목록이 비었거나 상한을 초과함"),
            401: OpenApiResponse(description="로그인 필요"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = OutfitAnalysisClaimRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = claim_service.claim_analyses(
            request.user, serializer.validated_data["claim_tokens"]
        )
        response_serializer = OutfitAnalysisClaimResponseSerializer(
            data={"claimed": result.claimed, "skipped": result.skipped}
        )
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.validated_data)


DAILY_LOOK_PENDING_EXAMPLE = OpenApiExample(
    "생성 중",
    description=(
        "그날 첫 조회라 방금 생성이 걸렸거나, 워커가 아직 처리 중이다.\n\n"
        "`poll_after_ms` 간격으로 같은 URL을 다시 호출한다. `result`는 아직 null이다."
    ),
    value={
        "look_id": "0c4d1d5a-2f3e-4b7a-9c1e-5a6b7c8d9e01",
        "look_date": "2026-08-09",
        "status": "QUEUED",
        "result": None,
        "context": {
            "weather": {"region": "서울", "temperature": 28.4, "sky_state": "맑음"},
            "used_body": True,
            "used_pursuit": True,
            "body_profile": "역삼각형 · 표준",
            "missing_measurements": ["thigh", "calf"],
            "candidate_count": 0,
        },
        "poll_after_ms": 1500,
        "detail": "오늘의 룩을 만들고 있어요. 잠시만 기다려주세요.",
    },
    response_only=True,
)

DAILY_LOOK_READY_EXAMPLE = OpenApiExample(
    "생성 완료",
    value={
        "look_id": "0c4d1d5a-2f3e-4b7a-9c1e-5a6b7c8d9e01",
        "look_date": "2026-08-09",
        "status": "SUCCEEDED",
        "result": {
            "headline": "더위엔 가볍게, 어깨는 부드럽게",
            "golden_id": "095",
            "rationale_ko": "어깨가 넓은 편이라 상의는 어깨선을 키우지 않는 레귤러핏으로 두고, 하의에 여유를 줘 전체 균형을 맞췄어요. 28도라 겉옷은 생략했습니다.",
            "styling_tips": ["소매를 한 번 접으면 팔 라인이 가벼워 보여요."],
            "generated_by": "llm",
            # 화면의 대표 이미지. 골든 아이템 이미지를 참조로 새로 만든 착용 컷이라
            # 사용권 제약이 없다. 아직 만들어지지 않았으면 null이고, 그때는
            # items[].image_url 카드로 화면을 그린다.
            "render_image_url": "https://skn28-cozy3.s3.ap-northeast-2.amazonaws.com/...render_frontal.png?...",
            # 원본 코디 사진은 사용권이 열린 코디에만 값이 있다 (대개 null).
            "outfit_image_url": None,
            "items": [
                {
                    "item_key": "095#000",
                    "name": "화이트 셔츠",
                    "category": "상의",
                    "sub_category": "셔츠/블라우스",
                    "layer_role": "기본 상의",
                    "color": "화이트",
                    "note": "어깨선을 덮지 않는 기본 기장",
                    # 조회할 때마다 새로 서명한다. 캐시하지 말 것.
                    "image_url": "https://skn28-cozy3.s3.ap-northeast-2.amazonaws.com/...",
                }
            ],
        },
        "context": {
            "weather": {"region": "서울", "temperature": 28.4, "sky_state": "맑음"},
            "used_body": True,
            "used_pursuit": True,
            "body_profile": "역삼각형 · 표준",
            "missing_measurements": [],
            "candidate_count": 5,
        },
        "poll_after_ms": None,
        "detail": None,
    },
    response_only=True,
)

DAILY_LOOK_EMPTY_EXAMPLE = OpenApiExample(
    "추천 후보 없음",
    description=(
        "실패가 아니다. 폴링해도 결과가 바뀌지 않으므로 프론트는 재시도 대신 "
        "프로필 입력을 안내해야 한다."
    ),
    value={
        "look_id": "0c4d1d5a-2f3e-4b7a-9c1e-5a6b7c8d9e01",
        "look_date": "2026-08-09",
        "status": "EMPTY",
        "result": None,
        "context": {
            "weather": {},
            "used_body": False,
            "used_pursuit": False,
            "body_profile": "미판정",
            "missing_measurements": ["height", "weight", "chest", "waist", "hip"],
            "candidate_count": 0,
        },
        "poll_after_ms": None,
        "detail": "조건에 맞는 추천을 찾지 못했어요. 신체치수나 추구미를 입력하면 더 잘 찾을 수 있어요.",
    },
    response_only=True,
)


class DailyLookTodayView(APIView):
    """오늘의 룩 조회 (없으면 생성을 걸고 '생성 중'으로 응답).

    사용자 입력이 없는 기능이라 별도의 생성 엔드포인트를 두지 않았다. 그날 첫
    호출이 곧 생성 트리거다. 홈 API(GET /api/v1/home/)에서 미리 걸어두면
    사용자가 추천 화면에 도착할 때쯤 이미 완성돼 있고, 그 호출이 실패했더라도
    이 조회가 다시 건다 —
    트리거가 한 곳뿐이면 그게 실패했을 때 사용자는 종일 룩을 못 본다.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="daily_look_today",
        summary="오늘의 룩 조회",
        description=(
            "그날의 추천을 돌려준다. 아직 만들어지지 않았으면 생성을 걸고 "
            "`status=QUEUED`로 응답한다.\n\n"
            "**상태별 프론트 동작**\n"
            "- `QUEUED` / `PROCESSING`: `poll_after_ms` 뒤에 다시 호출\n"
            "- `SUCCEEDED`: `result` 표시\n"
            "- `EMPTY`: 폴링하지 말 것. 프로필 입력 안내\n"
            "- `FAILED`: 다음 호출에서 자동 재시도되지 않는다. 사용자에게 알린다\n\n"
            "코디 선택은 검색 단계에서 결정적으로 끝난다. 문장 생성(LLM)이 실패해도 "
            "`SUCCEEDED`이며, 그때는 `result.generated_by`가 `template`이다.\n\n"
            "`image_url`·`render_image_url`은 매 조회마다 새로 서명한다. 클라이언트가 캐시하면 만료된다.\n\n"
            "대표 이미지는 `result.render_image_url`이다. 골든 코디당 한 번만 만들어 "
            "재사용하므로 같은 코디를 받은 사용자끼리 같은 이미지를 본다. 생성 전이거나 "
            "실패하면 null이며, 그때는 `result.items[].image_url` 카드로 화면을 구성한다.\n\n"
            "이 값이 비어 있으면 조회할 때마다 다시 확인한다. 생성이 한 번 실패해도 "
            "다음 시행에서 성공하는 일이 잦아, 그때 이미 만들어져 있으면 이 응답에서 "
            "바로 채워진다. 아직 없으면 재생성을 예약한다(쿨다운 있음). 즉 "
            "`SUCCEEDED`인데 `render_image_url`이 null이면, 잠시 뒤 다시 조회할 때 "
            "값이 생길 수 있다 — 폴링을 계속할 필요는 없고 다음 진입에서 채워진다.\n\n"
            "위경도를 주면 그 위치의 날씨로 추천한다. 생성은 하루 한 번뿐이라 "
            "이미 만들어진 뒤의 좌표는 반영되지 않는다."
        ),
        parameters=[
            OpenApiParameter(
                name="lat", type=float, required=False,
                description="위도. 미전달 시 서울 좌표로 대체한다.",
            ),
            OpenApiParameter(
                name="lon", type=float, required=False,
                description="경도. 미전달 시 서울 좌표로 대체한다.",
            ),
        ],
        responses={200: DailyLookSerializer},
        examples=[
            DAILY_LOOK_PENDING_EXAMPLE,
            DAILY_LOOK_READY_EXAMPLE,
            DAILY_LOOK_EMPTY_EXAMPLE,
        ],
    )
    def get(self, request: Request) -> Response:
        look, created = daily_look_service.ensure_today_look(
            request.user,
            lat=_float_or_none(request.query_params.get("lat")),
            lon=_float_or_none(request.query_params.get("lon")),
        )
        if created:
            logger.info("오늘의 룩 생성 접수: user=%s look=%s", request.user.pk, look.pk)

        # 착용 이미지는 생성 시점에 실패해도 다음 시행에서 성공하는 일이 잦다.
        # 결과 JSON은 생성이 끝날 때 한 번만 쓰이므로, 그 사이에 이미지가 생겨도
        # 행은 비어 있는 채로 남는다. 조회할 때마다 한 번 더 확인해 붙인다.
        # 생성은 하지 않는다 — 수십 초가 걸려 이 요청을 잡아둘 수 없다.
        daily_look_service.refresh_render(look)

        return Response(DailyLookSerializer(look).data)


def _float_or_none(raw: str | None) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        # 좌표가 깨졌다고 추천을 막을 이유는 없다. 서울 좌표로 폴백한다.
        return None
