import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OutfitAnalysis
from .serializers import (
    OutfitAnalysisDetailSerializer,
    OutfitAnalysisListItemSerializer,
    OutfitAnalysisListResponseSerializer,
    OutfitAnalysisRequestSerializer,
    OutfitAnalysisResponseSerializer,
)
from .services import analysis as analysis_service
from .services import gemini

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
    """익명 또는 로그인 사용자의 코디 사진을 Gemini로 평가하고 결과를 기록한다."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="outfit_analysis_create",
        tags=["Outfit Analysis"],
        summary="AI 코디 사진 평가",
        description=(
            "코디 사진과 선택적인 위치를 multipart/form-data로 받아 Gemini가 긍정적으로 평가합니다. "
            "인증 없이 호출할 수 있으며, 유효한 JWT를 보내면 저장된 추구미·체형·성별을 평가에 반영합니다.\n\n"
            "요청마다 질의에 사용한 날씨·체형·추구미 스냅샷과 LLM 요청·응답 원본이 저장되며, "
            "응답의 analysis_id로 이력을 조회할 수 있습니다 (로그인 사용자에 한함)."
        ),
        request=OutfitAnalysisRequestSerializer,
        responses={
            200: OutfitAnalysisResponseSerializer,
            400: OpenApiResponse(description="파일 또는 좌표가 유효하지 않음"),
            415: OpenApiResponse(description="multipart/form-data가 아닌 요청"),
            503: OpenApiResponse(description="Gemini 설정 누락 또는 일시적인 호출 실패"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = OutfitAnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            analysis, evaluation, context = analysis_service.analyze_outfit(
                request.user,
                data["image"],
                lat=data.get("lat"),
                lon=data.get("lon"),
            )
        except gemini.GeminiConfigurationError:
            logger.exception("Gemini API 설정 누락")
            return Response(
                {"detail": "코디 평가 서비스가 설정되지 않았습니다."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except gemini.GeminiServiceError:
            logger.exception("Gemini 코디 평가 실패")
            return Response(
                {"detail": "코디 평가를 완료하지 못했습니다. 잠시 후 다시 시도해주세요."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_serializer = OutfitAnalysisResponseSerializer(
            data={
                "status": "completed",
                "analysis_id": str(analysis.pk) if analysis is not None else None,
                "evaluation": evaluation,
                "context": {
                    "weather": context["weather"],
                    "personalized": context["personalized"],
                    "used_pursuit": context["pursuit"] is not None,
                    "used_body": context["body"] is not None,
                },
            }
        )
        if not response_serializer.is_valid():
            logger.error("Gemini 코디 평가 응답 형식 오류: %s", response_serializer.errors)
            return Response(
                {"detail": "코디 평가 결과 형식이 올바르지 않습니다."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(response_serializer.validated_data, status=status.HTTP_200_OK)


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
                description="상태 필터 (PENDING/SUCCEEDED/FAILED)",
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
    """GET /api/v1/outfits/analyses/{analysis_id}/ — 평가 1건 상세 (본인 것만)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="outfit_analysis_retrieve",
        tags=["Outfit Analysis"],
        summary="코디 평가 상세",
        description="질의에 사용한 날씨·체형·추구미 스냅샷과 LLM 요청·응답 원본을 포함합니다.",
        responses={
            200: OutfitAnalysisDetailSerializer,
            404: OpenApiResponse(description="존재하지 않거나 본인의 기록이 아님"),
        },
    )
    def get(self, request: Request, analysis_id) -> Response:
        analysis = get_object_or_404(OutfitAnalysis, pk=analysis_id, user=request.user)
        return Response(OutfitAnalysisDetailSerializer(analysis).data)
