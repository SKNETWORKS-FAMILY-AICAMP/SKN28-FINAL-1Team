import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    OutfitAnalysisRequestSerializer,
    OutfitAnalysisResponseSerializer,
)
from .services import gemini
from .services.outfit_context import build_analysis_context

logger = logging.getLogger(__name__)


class OutfitAnalysisView(APIView):
    """익명 또는 로그인 사용자의 코디 사진을 Gemini로 평가한다."""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="outfit_analysis_create",
        tags=["Outfit Analysis"],
        summary="AI 코디 사진 평가",
        description=(
            "코디 사진과 선택적인 위치를 multipart/form-data로 받아 Gemini가 긍정적으로 평가합니다. "
            "인증 없이 호출할 수 있으며, 유효한 JWT를 보내면 저장된 추구미·체형·성별을 평가에 반영합니다."
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
        context = build_analysis_context(
            request.user,
            lat=data.get("lat"),
            lon=data.get("lon"),
        )

        try:
            evaluation = gemini.evaluate_outfit(data["image"], context=context)
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
