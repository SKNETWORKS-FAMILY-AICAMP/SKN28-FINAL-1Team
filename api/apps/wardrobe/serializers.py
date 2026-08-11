"""옷장 등록 API 시리얼라이저.

태그 값 검증은 taxonomy.py 상수를 기준으로 한다.
콜백은 이미지 프로세서가 보내는 페이로드(캡션 + 벡터 + S3 키)를 받는다.
"""
from __future__ import annotations

import os

from rest_framework import serializers

from . import taxonomy as T
from .models import WardrobeItem, WardrobeUploadJob
from .services import storage

MAX_UPLOAD_MB = 15
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_BATCH_ITEMS = int(os.getenv("WARDROBE_BATCH_MAX_ITEMS", "30"))
MAX_BATCH_TOTAL_MB = int(os.getenv("WARDROBE_BATCH_MAX_TOTAL_MB", "100"))


# ── 업로드 ────────────────────────────────────────────────
class WardrobeUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

    def validate_image(self, image):
        if image.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise serializers.ValidationError(
                f"이미지는 {MAX_UPLOAD_MB}MB 이하여야 합니다."
            )
        if image.content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                "지원하지 않는 이미지 형식입니다 (jpeg/png/webp/heic)."
            )
        return image


class WardrobeBatchItemSerializer(serializers.Serializer):
    image_link = serializers.URLField(max_length=2048)
    item_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    category_large = serializers.ChoiceField(
        choices=[""] + T.CATEGORY_LARGE, required=False, allow_blank=True, default="",
    )
    category_small = serializers.ChoiceField(
        choices=[""] + T.ALL_SMALL, required=False, allow_blank=True, default="",
    )
    season = serializers.ListField(
        child=serializers.ChoiceField(choices=T.SEASONS), required=False, default=list,
    )
    style = serializers.ListField(
        child=serializers.ChoiceField(choices=T.STYLES), required=False, default=list,
    )
    color = serializers.ChoiceField(choices=[""] + T.COLORS, required=False, allow_blank=True, default="")
    pattern = serializers.ChoiceField(choices=[""] + T.PATTERNS, required=False, allow_blank=True, default="")
    fit = serializers.ChoiceField(choices=[""] + T.FITS, required=False, allow_blank=True, default="")
    material = serializers.ChoiceField(choices=[""] + T.MATERIALS, required=False, allow_blank=True, default="")
    sleeve = serializers.ChoiceField(choices=[""] + T.SLEEVES, required=False, allow_blank=True, default="")
    length = serializers.ChoiceField(choices=[""] + T.LENGTHS, required=False, allow_blank=True, default="")
    usage = serializers.ListField(child=serializers.CharField(max_length=20), required=False, default=list)
    layer_role = serializers.ChoiceField(
        choices=[""] + T.LAYER_ROLES, required=False, allow_blank=True, default="",
    )
    layer_order = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=3)
    confirmed = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        large, small = attrs.get("category_large", ""), attrs.get("category_small", "")
        if small and (not large or not T.is_valid_pair(large, small)):
            raise serializers.ValidationError({"category_small": "대분류와 맞지 않는 소분류입니다."})
        return attrs


class WardrobeBatchCreateSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=WardrobeBatchItemSerializer(), allow_empty=False, max_length=MAX_BATCH_ITEMS,
    )
    source = serializers.RegexField(
        r"^[a-z][a-z0-9_-]{0,19}$", required=False, default="in_app_browser",
    )


# ── 아이템 조회/수정 ──────────────────────────────────────
class WardrobeItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = WardrobeItem
        fields = [
            "id", "job", "s3_key", "image_url", "item_name",
            "category_large", "category_small", "season", "style", "color",
            "pattern", "fit", "material", "sleeve", "length", "usage",
            "layer_role", "layer_order", "seg_meta", "confirmed", "created_at",
        ]
        read_only_fields = ["id", "job", "s3_key", "seg_meta", "created_at"]

    def get_image_url(self, obj) -> str:
        return storage.presigned_get(obj.s3_key)


class WardrobeItemUpdateSerializer(serializers.ModelSerializer):
    """PATCH /wardrobe/items/{id}/ — 태깅 수정 + 확정."""

    class Meta:
        model = WardrobeItem
        fields = [
            "item_name", "category_large", "category_small", "season", "style",
            "color", "pattern", "fit", "material", "sleeve", "length", "usage",
            "layer_role", "layer_order", "confirmed",
        ]

    def validate(self, attrs):
        large = attrs.get("category_large", self.instance.category_large)
        small = attrs.get("category_small", self.instance.category_small)
        if large not in T.CATEGORY_LARGE:
            raise serializers.ValidationError({"category_large": "유효하지 않은 대분류입니다."})
        if small and not T.is_valid_pair(large, small):
            raise serializers.ValidationError(
                {"category_small": f"'{large}'에 속하지 않는 소분류입니다."}
            )
        return attrs


# ── job 상태 조회 ─────────────────────────────────────────
class WardrobeJobSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(source="id", read_only=True)
    file_name = serializers.CharField(source="original_file_name", read_only=True)
    items = WardrobeItemSerializer(many=True, read_only=True)

    class Meta:
        model = WardrobeUploadJob
        fields = ["id", "job_id", "file_name", "status", "error_message",
                  "created_at", "finished_at", "items"]


# ── 이미지 프로세서 콜백 ──────────────────────────────────
class CallbackItemSerializer(serializers.Serializer):
    """콜백 페이로드의 아이템 1건. 벡터는 DB가 아닌 Qdrant로만 간다."""

    s3_key = serializers.CharField(max_length=512)
    item_name = serializers.CharField(max_length=120, allow_blank=True, default="")
    category_large = serializers.ChoiceField(choices=T.CATEGORY_LARGE)
    category_small = serializers.CharField(allow_blank=True, default="")
    season = serializers.ListField(
        child=serializers.ChoiceField(choices=T.SEASONS), default=list
    )
    style = serializers.ListField(
        child=serializers.ChoiceField(choices=T.STYLES), default=list
    )
    color = serializers.CharField(allow_blank=True, default="")
    pattern = serializers.CharField(allow_blank=True, default="")
    fit = serializers.CharField(allow_blank=True, allow_null=True, default="")
    material = serializers.CharField(allow_blank=True, allow_null=True, default="")
    sleeve = serializers.CharField(allow_blank=True, allow_null=True, default="")
    length = serializers.CharField(allow_blank=True, allow_null=True, default="")
    usage = serializers.ListField(child=serializers.CharField(), default=list)
    layer_role = serializers.CharField(allow_blank=True, allow_null=True, default="")
    layer_order = serializers.IntegerField(allow_null=True, default=None)
    seg_meta = serializers.JSONField(default=dict)
    image_vector = serializers.ListField(
        child=serializers.FloatField(), allow_empty=True, default=list
    )
    text_vector = serializers.ListField(
        child=serializers.FloatField(), allow_empty=True, default=list
    )

    def validate(self, attrs):
        # 소분류가 오면 대분류와의 짝만 검사 (미지정은 허용 — 사용자 확인 단계에서 보정)
        small = attrs.get("category_small") or ""
        if small and not T.is_valid_pair(attrs["category_large"], small):
            raise serializers.ValidationError(
                {"category_small": f"'{attrs['category_large']}'에 속하지 않는 소분류입니다."}
            )
        # null 허용 필드를 저장용 빈 문자열로 정규화
        for f in ("fit", "material", "sleeve", "length", "layer_role"):
            if attrs.get(f) is None:
                attrs[f] = ""
        return attrs


class CallbackSerializer(serializers.Serializer):
    job_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["processing", "success", "failed"])
    error = serializers.CharField(allow_blank=True, default="")
    items = CallbackItemSerializer(many=True, default=list)


# ── 공유 옷장 (Shared Wardrobe) 시리얼라이저 ─────────────────
from django.contrib.auth import get_user_model
from .models import SharedWardrobeRoom, SharedWardrobeMember, SharedWardrobeItem

User = get_user_model()

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class SharedWardrobeRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = SharedWardrobeRoom
        fields = ["id", "title", "invite_code", "code_expires_at", "created_at"]
        read_only_fields = ["id", "invite_code", "code_expires_at", "created_at"]


class SharedWardrobeMemberSerializer(serializers.ModelSerializer):
    user = UserSimpleSerializer(read_only=True)

    class Meta:
        model = SharedWardrobeMember
        fields = ["id", "user", "role", "joined_at"]


class SharedWardrobeItemSerializer(serializers.ModelSerializer):
    wardrobe_item = WardrobeItemSerializer(read_only=True)
    registered_by = UserSimpleSerializer(read_only=True)

    class Meta:
        model = SharedWardrobeItem
        fields = ["id", "registered_by", "wardrobe_item", "status", "created_at"]


class SharedWardrobeJoinSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=6, min_length=6, write_only=True)


class SharedWardrobeLeaveSerializer(serializers.Serializer):
    delete_my_items = serializers.BooleanField(default=True)


class SharedWardrobeItemRegisterSerializer(serializers.Serializer):
    wardrobe_item_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=SharedWardrobeItem.Status.choices,
        default=SharedWardrobeItem.Status.AVAILABLE
    )


# ── 비로그인 초대 미리보기 (구경 모드) ─────────────────────
#
# 초대 링크만 있으면 로그인 없이 방을 둘러볼 수 있다. 열람 전용이며 서버에
# 아무 레코드도 남기지 않는다 (익명 User·멤버십 생성 금지 — 정원 6명 카운트와
# 방장 위임 대상이 오염된다).
#
# 소유자는 실명 대신 가입 순서 기반 라벨로 치환해서 내린다. 인덱스가 프론트의
# MEMBER_COLORS와 1:1로 맞으므로(0=노랑 … 5=주황) 이름과 색이 같은 순서를
# 공유하게 되고, 로그인 화면과 구경 화면의 아바타가 어긋나지 않는다.
ANON_MEMBER_LABELS = ["다람쥐", "고래", "여우", "판다", "펭귄", "너구리"]


def anon_member_label(index: int) -> str:
    return ANON_MEMBER_LABELS[index % len(ANON_MEMBER_LABELS)]


class SharedWardrobePreviewMemberSerializer(serializers.Serializer):
    """비로그인용 멤버 표시. PK·실명·이메일을 의도적으로 제외한다."""

    index = serializers.IntegerField(help_text="가입 순서(0-base). 아바타 색상 인덱스")
    label = serializers.CharField(help_text="방 안에서만 쓰는 익명 라벨")
    role = serializers.CharField(help_text="owner / member")


class SharedWardrobePreviewItemSerializer(serializers.Serializer):
    """비로그인용 아이템 표시. 옷 UUID를 안 내려 쓰기 경로를 원천 차단한다."""

    image_url = serializers.CharField()
    item_name = serializers.CharField(allow_null=True)
    category_large = serializers.CharField(allow_null=True)
    color = serializers.CharField(allow_null=True)
    owner_index = serializers.IntegerField(allow_null=True)
    owner_label = serializers.CharField(allow_null=True)


class SharedWardrobePreviewSerializer(serializers.Serializer):
    """GET /shared-wardrobes/preview/?code= 응답 (문서화용).

    방 UUID를 내리지 않는다 — 익명 사용자가 멤버 전용 엔드포인트
    (/shared-wardrobes/{id}/items/ 등)의 주소를 알 이유가 없다.
    """

    title = serializers.CharField()
    member_count = serializers.IntegerField()
    capacity = serializers.IntegerField()
    can_join = serializers.BooleanField(help_text="정원이 남아 있고 만료되지 않았는가")
    expired = serializers.BooleanField()
    members = SharedWardrobePreviewMemberSerializer(many=True)
    items = SharedWardrobePreviewItemSerializer(many=True)
