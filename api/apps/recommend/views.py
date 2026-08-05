import logging
from datetime import timedelta

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
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
from .services import analysis as analysis_service
from .services import claim as claim_service

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 100


def _positive_int(raw: str | None, *, default: int) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


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
            "체형·추구미 스냅샷과 LLM 요청·응답 원본까지 함께 내려갑니다."
        ),
        responses={
            200: OutfitAnalysisPublicSerializer,
            404: OpenApiResponse(description="존재하지 않거나, 본인 기록이 아니거나, 조회 기간이 지남"),
        },
    )
    def get(self, request: Request, analysis_id) -> Response:
        analysis = OutfitAnalysis.objects.filter(pk=analysis_id).first()
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
