from rest_framework import serializers

from apps.users.constants import PREFERENCE_CATEGORIES, category_keys
from apps.users.models import (
    BodyMeasurement,
    BodyPhotoTransaction,
    PreferenceOption,
    Pursuit,
    SocialAccount,
    User,
)


class SocialLoginSerializer(serializers.Serializer):
    """POST /auth/{provider}/login 요청 바디.

    code(인가 코드 방식) 또는 access_token(토큰 방식, 카카오 네이티브 앱 SDK 전용)
    중 하나는 반드시 있어야 한다.
    """

    code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="인가 코드 (code 방식). naver/google/kakao 웹 로그인에서 필수.",
    )
    # token 방식: 네이티브 앱 SDK는 인가 코드를 노출하지 않고 access_token을
    # 직접 반환하므로, 앱은 이 값을 백엔드로 전달한다.
    # 주의: naver는 발급 앱 검증이 불가해 토큰 유효성·사용자 식별만 수행한다.
    access_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="token 방식 전용. 네이티브 앱 SDK가 발급한 제공사 access token.",
    )
    # 카카오/구글은 토큰 교환 시 인가 요청과 동일한 redirect_uri가 필요하다.
    redirect_uri = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="kakao(code 방식)/google 필수. 인가 요청 시 사용한 값과 동일해야 함.",
    )
    # 네이버는 state 검증을 사용한다.
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="naver 필수. 인가 요청 시 보낸 CSRF 방지용 state 값.",
    )
    # 애플 전용: 최초 로그인 시 Apple SDK가 전달하는 사용자 이름 (이후 로그인엔 빈값).
    user_name = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="apple 전용 (구현 보류). 최초 로그인 시 Apple이 전달하는 사용자 이름.",
    )

    def validate(self, attrs):
        if not attrs.get("code") and not attrs.get("access_token"):
            raise serializers.ValidationError("code 또는 access_token 중 하나가 필요합니다.")
        return attrs


class SocialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ["provider", "email", "connected_at"]


class UserSerializer(serializers.ModelSerializer):
    social_accounts = SocialAccountSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "nickname", "profile_image", "social_accounts"]
        read_only_fields = ["id", "username", "email", "social_accounts"]


BODY_BASIC_FIELDS = ["height", "weight"]
BODY_DETAIL_FIELDS = ["chest", "waist", "hip", "thigh", "calf", "arm", "shoulder"]


class BodyMeasurementSerializer(serializers.ModelSerializer):
    """신체치수 조회/저장 결과 응답 (기본 + 상세 전체)."""

    class Meta:
        model = BodyMeasurement
        fields = [*BODY_BASIC_FIELDS, *BODY_DETAIL_FIELDS, "updated_at"]
        read_only_fields = ["updated_at"]


class BodyBasicInputSerializer(serializers.ModelSerializer):
    """PUT /users/me/body/basic — 키·몸무게. 둘 다 필수."""

    class Meta:
        model = BodyMeasurement
        fields = BODY_BASIC_FIELDS
        extra_kwargs = {
            field: {"required": True, "allow_null": False} for field in BODY_BASIC_FIELDS
        }


class BodyDetailInputSerializer(serializers.ModelSerializer):
    """PATCH /users/me/body/detail — 상세 둘레 수치. 전부 선택 입력.

    보낸 필드만 갱신하며(partial), null을 보내면 해당 값을 지운다.
    """

    class Meta:
        model = BodyMeasurement
        fields = BODY_DETAIL_FIELDS


class BodyPhotoUploadSerializer(serializers.Serializer):
    """POST /users/me/body/photos — 정면/측면 사진 (multipart/form-data).

    사진은 저장하지 않고 접수만 한다. 추후 상세 수치 추론에 사용될 예정.
    """

    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

    front_image = serializers.ImageField(help_text="정면 전신 사진 (10MB 이하)")
    side_image = serializers.ImageField(help_text="측면 전신 사진 (10MB 이하)")

    def _validate_size(self, image):
        if image.size > self.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError("사진은 10MB 이하여야 합니다.")
        return image

    def validate_front_image(self, image):
        return self._validate_size(image)

    def validate_side_image(self, image):
        return self._validate_size(image)


class BodyPhotoTransactionSerializer(serializers.ModelSerializer):
    """사진 측정 트랜잭션 상태 응답 (GET /users/me/body/photos/{transaction_id})."""

    transaction_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = BodyPhotoTransaction
        fields = ["transaction_id", "status", "created_at", "updated_at"]
        read_only_fields = fields



# 추구미 (Pursuit) — 옵션 마스터 / 사용자 선택

class PreferenceOptionItemSerializer(serializers.Serializer):
    """개별 옵션 1개. DB 모델과 1:1 매핑되지 않는 가벼운 serializer."""

    code = serializers.CharField()
    label = serializers.CharField()
    meta = serializers.JSONField(required=False, default=dict)


class PreferenceCategorySerializer(serializers.Serializer):
    """카테고리 1개 — key/label/options 묶음.

    GET /api/v1/preference-options/ 응답에 들어가는 한 카테고리 단위.
    """

    key = serializers.CharField()
    label = serializers.CharField()
    options = PreferenceOptionItemSerializer(many=True)


def _build_pursuit_payload_field(*, required: bool) -> serializers.DictField:
    """preferred/avoided 페이로드 필드 빌더.

    PREFERENCE_CATEGORIES 11개 키에 대해 각 키가 ListField(str, allow_empty=True).
    required 인자에 따라 입력 검증(required) 또는 응답(read_only) 형태로 사용.
    """
    child = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        allow_empty=True,
    )
    fields = {key: child for key, _ in PREFERENCE_CATEGORIES}
    # DRF는 `required=True` + `default=...` 동시 지정 불가.
    # → required 케이스에서 default 키워드 자체를 넘기지 말아야 함.
    if required:
        return serializers.DictField(child=child, required=True)
    return serializers.DictField(child=child, required=False, default=dict)


class PursuitPayloadInputSerializer(serializers.Serializer):
    """PUT /api/v1/users/me/pursuit/ 요청 바디.

    preferred/avoided 두 그룹.
    각 그룹은 PREFERENCE_CATEGORIES 11개 키 모두 가져야 함.
    각 값은 선택된 옵션 code 배열 (빈 배열 허용).
    """

    preferred = _build_pursuit_payload_field(required=True)
    avoided = _build_pursuit_payload_field(required=True)

    def validate_preferred(self, value):
        # 11개 카테고리 키 모두 있어야 함
        return self._validate_payload_group(value, "preferred")

    def validate_avoided(self, value):
        return self._validate_payload_group(value, "avoided")

    @staticmethod
    def _validate_payload_group(value: dict, group_name: str) -> dict:
        expected = set(category_keys())
        given = set(value.keys() if isinstance(value, dict) else [])
        missing = expected - given
        extra = given - expected
        if missing:
            raise serializers.ValidationError(
                f"{group_name}에 누락된 카테고리: {sorted(missing)}"
            )
        if extra:
            # 알 수 없는 카테고리는 무시보다 명시적 에러가 안전
            raise serializers.ValidationError(
                f"{group_name}에 알 수 없는 카테고리: {sorted(extra)}"
            )
        # 각 카테고리는 배열 + 문자열만
        cleaned: dict = {}
        for key in category_keys():
            arr = value.get(key, [])
            if not isinstance(arr, list):
                raise serializers.ValidationError(
                    f"{group_name}.{key} 은(는) 배열이어야 합니다."
                )
            for v in arr:
                if not isinstance(v, str):
                    raise serializers.ValidationError(
                        f"{group_name}.{key} 의 원소는 문자열이어야 합니다: {v!r}"
                    )
            # 중복 제거 + 입력 순서 유지
            cleaned[key] = list(dict.fromkeys(arr))
        return cleaned


class PursuitPayloadResponseSerializer(serializers.Serializer):
    """GET /api/v1/users/me/style-preferences/ 응답.

    preferred/avoided 두 그룹. 
    각 그룹은 PREFERENCE_CATEGORIES 11개 키 모두 포함
    (없는 카테고리는 빈 배열로 채워짐 — 응답 일관성).
    """

    preferred = _build_pursuit_payload_field(required=False)
    avoided = _build_pursuit_payload_field(required=False)
