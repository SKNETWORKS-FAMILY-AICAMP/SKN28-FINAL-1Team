"""네이버 수집 상품 카탈로그 모델.

스키마 소유권은 Django migration에 있다. collector/naver는 이 테이블에
raw SQL(psycopg2)로 upsert만 하므로, 모델 변경 시 collector의
db.PRODUCT_COLUMNS도 함께 갱신해야 한다.

collector가 INSERT 시 생략하는 컬럼(created_at/updated_at 등)은
db_default로 DB 기본값을 유지한다 (기존 DDL의 DEFAULT NOW()와 동일 동작).
"""

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.functions import Now


class NaverProduct(models.Model):
    # 네이버 원본 필드
    naver_product_id = models.CharField(max_length=40, unique=True)
    product_type = models.SmallIntegerField(null=True, blank=True)
    title = models.CharField(max_length=500)
    title_raw = models.CharField(max_length=500, null=True, blank=True)
    link = models.TextField(null=True, blank=True)
    image_url = models.TextField(null=True, blank=True)
    lprice = models.IntegerField(null=True, blank=True)
    hprice = models.IntegerField(null=True, blank=True)
    mall_name = models.CharField(max_length=200, null=True, blank=True)
    brand = models.CharField(max_length=200, null=True, blank=True)
    maker = models.CharField(max_length=200, null=True, blank=True)
    naver_category1 = models.CharField(max_length=100, null=True, blank=True)
    naver_category2 = models.CharField(max_length=100, null=True, blank=True)
    naver_category3 = models.CharField(max_length=100, null=True, blank=True)
    naver_category4 = models.CharField(max_length=100, null=True, blank=True)

    # 컨플루언스 문서 분류
    category_large = models.CharField(max_length=30)
    category_small = models.CharField(max_length=50)
    category_source = models.CharField(max_length=20, default="keyword", db_default="keyword")

    # 문서 태그 체계
    season = ArrayField(models.TextField(), default=list, blank=True)
    style = ArrayField(models.TextField(), default=list, blank=True)
    color = ArrayField(models.TextField(), default=list, blank=True)
    pattern = ArrayField(models.TextField(), default=list, blank=True)
    fit = models.CharField(max_length=30, null=True, blank=True)
    material = ArrayField(models.TextField(), default=list, blank=True)
    sleeve = models.CharField(max_length=20, null=True, blank=True)
    length = models.CharField(max_length=20, null=True, blank=True)
    usage = ArrayField(models.TextField(), default=list, blank=True)
    layer_role = models.CharField(max_length=30, null=True, blank=True)
    layer_order = models.SmallIntegerField(null=True, blank=True)

    # 태깅 메타
    tag_source = models.JSONField(default=dict, blank=True)
    tagging_status = models.CharField(max_length=20, default="pending", db_default="pending")
    tagging_model = models.CharField(max_length=60, null=True, blank=True)
    tagging_used_image = models.BooleanField(default=False, db_default=False)
    tagged_at = models.DateTimeField(null=True, blank=True)

    # 수집 메타
    search_keyword = models.CharField(max_length=100, null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    collected_at = models.DateTimeField()
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "naver_product"
        verbose_name = "네이버 상품"
        verbose_name_plural = "네이버 상품"
        indexes = [
            models.Index(fields=["category_large", "category_small"], name="ix_naver_product_category"),
            models.Index(fields=["tagging_status"], name="ix_naver_product_tag_status"),
            GinIndex(fields=["season"], name="ix_naver_product_season"),
            GinIndex(fields=["style"], name="ix_naver_product_style"),
        ]

    def __str__(self) -> str:
        return f"[{self.category_large}>{self.category_small}] {self.title}"


class NaverTaggingBatch(models.Model):
    """OpenAI Batch API 태깅 작업 추적.

    collector/naver의 batch_tagger가 raw SQL로 기록/갱신한다.
    tagging_status 흐름: pending → queued(배치 제출됨) → tagged | failed
    """

    batch_id = models.CharField(max_length=100, unique=True)  # OpenAI batch id
    # submitted | validating | in_progress | finalizing | completed | failed | expired | cancelled
    status = models.CharField(max_length=30, default="submitted", db_default="submitted")
    model = models.CharField(max_length=60, null=True, blank=True)
    request_count = models.IntegerField(default=0, db_default=0)
    include_image = models.BooleanField(default=False, db_default=False)
    input_file_id = models.CharField(max_length=100, null=True, blank=True)
    output_file_id = models.CharField(max_length=100, null=True, blank=True)
    error_file_id = models.CharField(max_length=100, null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "naver_tagging_batch"
        verbose_name = "태깅 배치"
        verbose_name_plural = "태깅 배치"

    def __str__(self) -> str:
        return f"{self.batch_id} ({self.status})"


class NaverProductSize(models.Model):
    """상품 사이즈별 치수/측정값 (하위 종속 테이블).

    네이버 검색 API는 치수를 제공하지 않으므로 별도 수집/수동 입력으로 채운다.
    """

    product = models.ForeignKey(
        NaverProduct, on_delete=models.CASCADE, related_name="sizes"
    )
    size_label = models.CharField(max_length=30)   # S/M/L, 90~110, 230~290, FREE 등
    size_system = models.CharField(max_length=20, null=True, blank=True)  # KR/US/EU/UK

    # 공통 측정값 (cm)
    total_length = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    shoulder_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    chest_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    sleeve_length = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    waist_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    hip_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    rise = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    thigh_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    hem_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    foot_length_mm = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

    extra_measurements = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=30, default="manual", db_default="manual")
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "naver_product_size"
        verbose_name = "상품 사이즈"
        verbose_name_plural = "상품 사이즈"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size_label"], name="uq_naver_product_size_label"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product_id} / {self.size_label}"


class ElevenApiResponse(models.Model):
    """11번가 API 호출 단위의 원본 XML과 오류 기록."""

    api_name = models.CharField(max_length=30)
    endpoint = models.TextField()
    http_method = models.CharField(max_length=10, default="GET", db_default="GET")
    request_params = models.JSONField(default=dict, blank=True)
    response_status = models.IntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    raw_body = models.TextField(default="", blank=True)
    response_hash = models.CharField(max_length=64, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    fetched_at = models.DateTimeField()
    created_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "eleven_api_response"
        verbose_name = "11번가 API 응답"
        verbose_name_plural = "11번가 API 응답"
        indexes = [
            models.Index(
                fields=["api_name", "fetched_at"],
                name="ix_eleven_response_api_time",
            )
        ]

    def __str__(self) -> str:
        return f"{self.api_name} ({self.response_status})"


class ElevenCategory(models.Model):
    """11번가 카테고리조회 API의 전체 카테고리 트리."""

    disp_no = models.CharField(max_length=30, unique=True)
    disp_nm = models.CharField(max_length=200)
    parent_disp_no = models.CharField(max_length=30, null=True, blank=True)
    depth = models.SmallIntegerField()
    leaf_yn = models.BooleanField(default=False, db_default=False)
    gbl_dlv_yn = models.BooleanField(null=True, blank=True)
    eng_disp_yn = models.BooleanField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_default=True)
    # 전체 동기화에서 연속으로 보이지 않은 횟수. 임계값 도달 시 비활성화한다.
    missing_count = models.PositiveIntegerField(default=0, db_default=0)
    raw_data = models.JSONField(default=dict, blank=True)
    api_response = models.ForeignKey(
        ElevenApiResponse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categories",
    )
    collected_at = models.DateTimeField()
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "eleven_category"
        verbose_name = "11번가 카테고리"
        verbose_name_plural = "11번가 카테고리"
        indexes = [
            models.Index(fields=["parent_disp_no"], name="ix_eleven_category_parent"),
            models.Index(
                fields=["depth", "leaf_yn"], name="ix_eleven_category_depth_leaf"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.disp_no} {self.disp_nm}"


class ElevenProduct(models.Model):
    """11번가 ProductSearch 상품과 추천용 공통 태그."""

    eleven_product_id = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=500)
    title_raw = models.CharField(max_length=500)
    link = models.TextField(null=True, blank=True)
    image_url = models.TextField(null=True, blank=True)
    product_price = models.IntegerField(null=True, blank=True)
    sale_price = models.IntegerField(null=True, blank=True)
    mall_name = models.CharField(max_length=200, null=True, blank=True)
    rating = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    review_count = models.IntegerField(null=True, blank=True)
    buy_satisfy = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    delivery = models.CharField(max_length=200, null=True, blank=True)
    benefit = models.JSONField(default=dict, blank=True)

    eleven_category1 = models.CharField(max_length=100, null=True, blank=True)
    eleven_category2 = models.CharField(max_length=100, null=True, blank=True)
    eleven_category3 = models.CharField(max_length=100, null=True, blank=True)
    eleven_category4 = models.CharField(max_length=100, null=True, blank=True)
    eleven_category_disp_no = models.CharField(max_length=30, null=True, blank=True)

    category_large = models.CharField(max_length=30)
    category_small = models.CharField(max_length=50)
    category_source = models.CharField(
        max_length=20, default="keyword", db_default="keyword"
    )
    category_mapping_version = models.CharField(max_length=30, null=True, blank=True)

    season = ArrayField(models.TextField(), default=list, blank=True)
    style = ArrayField(models.TextField(), default=list, blank=True)
    color = ArrayField(models.TextField(), default=list, blank=True)
    pattern = ArrayField(models.TextField(), default=list, blank=True)
    fit = models.CharField(max_length=30, null=True, blank=True)
    material = ArrayField(models.TextField(), default=list, blank=True)
    sleeve = models.CharField(max_length=20, null=True, blank=True)
    length = models.CharField(max_length=20, null=True, blank=True)
    usage = ArrayField(models.TextField(), default=list, blank=True)
    layer_role = models.CharField(max_length=30, null=True, blank=True)
    layer_order = models.SmallIntegerField(null=True, blank=True)

    tag_source = models.JSONField(default=dict, blank=True)
    tagging_status = models.CharField(
        max_length=20, default="pending", db_default="pending"
    )
    tagging_model = models.CharField(max_length=60, null=True, blank=True)
    tagging_used_image = models.BooleanField(default=False, db_default=False)
    tagged_at = models.DateTimeField(null=True, blank=True)

    search_keyword = models.CharField(max_length=100, null=True, blank=True)
    search_sort = models.CharField(max_length=20, null=True, blank=True)
    search_rank = models.IntegerField(null=True, blank=True)
    page_num = models.IntegerField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    api_response = models.ForeignKey(
        ElevenApiResponse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    collected_at = models.DateTimeField()
    created_at = models.DateTimeField(db_default=Now())
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "eleven_product"
        verbose_name = "11번가 상품"
        verbose_name_plural = "11번가 상품"
        indexes = [
            models.Index(
                fields=["category_large", "category_small"],
                name="ix_eleven_product_category",
            ),
            models.Index(
                fields=["tagging_status"], name="ix_eleven_product_tag_status"
            ),
            models.Index(fields=["collected_at"], name="ix_eleven_product_collected"),
            models.Index(fields=["search_keyword"], name="ix_eleven_product_keyword"),
            models.Index(
                fields=["eleven_category_disp_no"],
                name="ix_eleven_product_disp_no",
            ),
            GinIndex(fields=["season"], name="ix_eleven_product_season"),
            GinIndex(fields=["style"], name="ix_eleven_product_style"),
        ]

    @property
    def representative_price(self) -> int | None:
        return self.sale_price or self.product_price

    def __str__(self) -> str:
        return f"[{self.category_large}>{self.category_small}] {self.title}"
