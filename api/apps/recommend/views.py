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


class OutfitAnalysisView(APIView):
    """인증 없이 코디 사진을 접수한다."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        operation_id="outfit_analysis_create",
        tags=["Outfit Analysis"],
        summary="코디 사진 분석 요청",
        description=(
            "인증이나 사용자 정보 없이 코디 사진 한 장을 multipart/form-data로 접수합니다. "
            "현재는 사진 검증과 접수만 수행하며, 실제 코디 평가 결과는 후속 기능에서 제공됩니다."
        ),
        request=OutfitAnalysisRequestSerializer,
        responses={
            202: OutfitAnalysisResponseSerializer,
            400: OpenApiResponse(description="파일 누락 또는 유효하지 않은 이미지"),
            415: OpenApiResponse(description="multipart/form-data가 아닌 요청"),
        },
        auth=[],
    )
    def post(self, request: Request) -> Response:
        serializer = OutfitAnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]

        return Response(
            {
                "detail": "코디 사진이 접수되었습니다. 평가 기능은 준비 중입니다.",
                "status": "pending_evaluation",
                "received": {
                    "name": image.name,
                    "size": image.size,
                    "content_type": image.content_type,
                },
                "result": None,
            },
            status=status.HTTP_202_ACCEPTED,
        )
