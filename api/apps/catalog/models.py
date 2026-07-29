"""네이버 수집 상품 카탈로그 모델.

스키마 소유권은 Django migration에 있다. collector/naver는 이 테이블에
raw SQL(psycopg2)로 upsert만 하므로, 모델 변경 시 collector의
db.PRODUCT_COLUMNS도 함께 갱신해야 한다.

collector가 INSERT 시 생략하는 컬럼(created_at/updated_at 등)은
db_default로 DB 기본값을 유지한다 (기존 DDL의 DEFAULT NOW()와 동일 동작).

테이블·컬럼 comment는 db_table_comment/db_comment로 모델이 소유한다
(DB 툴에서 스키마만 봐도 의미가 읽히도록 — 새 필드 추가 시 반드시 db_comment 지정).
"""

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.functions import Now


class NaverProduct(models.Model):
    # 네이버 원본 필드
    naver_product_id = models.CharField(
        max_length=40, unique=True, db_comment="네이버 상품 고유 ID (productId)"
    )
    product_type = models.SmallIntegerField(
        null=True, blank=True, db_comment="네이버 productType 코드 (1~12: 일반/중고/단종/판매예정 × 상품구분)"
    )
    title = models.CharField(max_length=500, db_comment="상품명 (HTML 태그 제거 후)")
    title_raw = models.CharField(
        max_length=500, null=True, blank=True, db_comment="상품명 원본 (네이버 응답 그대로, <b> 태그 포함)"
    )
    link = models.TextField(null=True, blank=True, db_comment="상품 상세 페이지 URL")
    image_url = models.TextField(null=True, blank=True, db_comment="상품 대표 이미지 URL (네이버 CDN)")
    lprice = models.IntegerField(null=True, blank=True, db_comment="최저가 (원)")
    hprice = models.IntegerField(null=True, blank=True, db_comment="최고가 (원, 대부분 미제공)")
    mall_name = models.CharField(
        max_length=200, null=True, blank=True, db_comment="판매 쇼핑몰 이름"
    )
    brand = models.CharField(max_length=200, null=True, blank=True, db_comment="브랜드명")
    maker = models.CharField(max_length=200, null=True, blank=True, db_comment="제조사명")
    naver_category1 = models.CharField(
        max_length=100, null=True, blank=True, db_comment="네이버 카테고리 대분류 (category1)"
    )
    naver_category2 = models.CharField(
        max_length=100, null=True, blank=True, db_comment="네이버 카테고리 중분류 (category2)"
    )
    naver_category3 = models.CharField(
        max_length=100, null=True, blank=True, db_comment="네이버 카테고리 소분류 (category3)"
    )
    naver_category4 = models.CharField(
        max_length=100, null=True, blank=True, db_comment="네이버 카테고리 세분류 (category4)"
    )

    # 컨플루언스 문서 분류
    category_large = models.CharField(
        max_length=30, db_comment="서비스 대분류 (컨플루언스 태그 체계: 상의/하의/아우터/신발/가방/모자/액세서리 등)"
    )
    category_small = models.CharField(
        max_length=50, db_comment="서비스 소분류 (컨플루언스 태그 체계: 티셔츠/청바지 등)"
    )
    category_source = models.CharField(
        max_length=20,
        default="keyword",
        db_default="keyword",
        db_comment="분류 출처 (keyword: 검색 키워드 규칙 / llm: LLM 태깅)",
    )

    # 문서 태그 체계
    season = ArrayField(
        models.TextField(), default=list, blank=True, db_comment="계절 태그 배열 (봄/여름/가을/겨울)"
    )
    style = ArrayField(
        models.TextField(), default=list, blank=True, db_comment="스타일 태그 배열 (캐주얼/미니멀/스트릿 등)"
    )
    color = ArrayField(
        models.TextField(), default=list, blank=True, db_comment="색상 태그 배열 (블랙/화이트 등)"
    )
    pattern = ArrayField(
        models.TextField(), default=list, blank=True, db_comment="패턴 태그 배열 (무지/스트라이프/체크 등)"
    )
    fit = models.CharField(
        max_length=30, null=True, blank=True, db_comment="핏 태그 (오버사이즈/슬림/와이드 등)"
    )
    material = ArrayField(
        models.TextField(), default=list, blank=True, db_comment="소재 태그 배열 (면/데님/니트 등)"
    )
    sleeve = models.CharField(
        max_length=20, null=True, blank=True, db_comment="소매 길이 태그 (긴팔/반팔/민소매 등)"
    )
    length = models.CharField(
        max_length=20, null=True, blank=True, db_comment="기장 태그 (크롭/롱/미디 등)"
    )
    usage = ArrayField(
        models.TextField(), default=list, blank=True, db_comment="용도(TPO) 태그 배열 (데일리/출근/운동 등)"
    )
    layer_role = models.CharField(
        max_length=30, null=True, blank=True, db_comment="레이어링 역할 (이너/미드/아우터 등)"
    )
    layer_order = models.SmallIntegerField(
        null=True, blank=True, db_comment="레이어링 착용 순서 (안쪽부터 1)"
    )

    # 태깅 메타
    tag_source = models.JSONField(
        default=dict, blank=True, db_comment="태그별 출처 기록 JSON ({태그명: keyword|llm})"
    )
    tagging_status = models.CharField(
        max_length=20,
        default="pending",
        db_default="pending",
        db_comment="LLM 태깅 상태 (pending → queued → tagged | failed)",
    )
    tagging_model = models.CharField(
        max_length=60, null=True, blank=True, db_comment="태깅에 사용한 LLM 모델명"
    )
    tagging_used_image = models.BooleanField(
        default=False, db_default=False, db_comment="태깅 시 상품 이미지 입력 사용 여부"
    )
    tagged_at = models.DateTimeField(null=True, blank=True, db_comment="태깅 완료 시각")

    # 수집 메타
    search_keyword = models.CharField(
        max_length=100, null=True, blank=True, db_comment="수집에 사용한 네이버 검색 키워드"
    )
    raw_data = models.JSONField(
        default=dict, blank=True, db_comment="네이버 API 원본 응답 JSON (디버깅/재처리용)"
    )
    collected_at = models.DateTimeField(db_comment="수집(크롤링) 시각")
    created_at = models.DateTimeField(db_default=Now(), db_comment="행 생성 시각")
    updated_at = models.DateTimeField(db_default=Now(), db_comment="행 수정 시각")

    class Meta:
        db_table = "naver_product"
        db_table_comment = "네이버 쇼핑 수집 상품 카탈로그 (collector/naver가 upsert, 추천 후보 원천)"
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

    batch_id = models.CharField(
        max_length=100, unique=True, db_comment="OpenAI Batch API 배치 ID"
    )
    # submitted | validating | in_progress | finalizing | completed | failed | expired | cancelled
    status = models.CharField(
        max_length=30,
        default="submitted",
        db_default="submitted",
        db_comment="배치 상태 (submitted/validating/in_progress/finalizing/completed/failed/expired/cancelled)",
    )
    model = models.CharField(
        max_length=60, null=True, blank=True, db_comment="배치에 사용한 LLM 모델명"
    )
    request_count = models.IntegerField(
        default=0, db_default=0, db_comment="배치에 포함된 태깅 요청(상품) 수"
    )
    include_image = models.BooleanField(
        default=False, db_default=False, db_comment="요청에 상품 이미지 포함 여부"
    )
    input_file_id = models.CharField(
        max_length=100, null=True, blank=True, db_comment="OpenAI 입력 파일 ID"
    )
    output_file_id = models.CharField(
        max_length=100, null=True, blank=True, db_comment="OpenAI 출력(결과) 파일 ID"
    )
    error_file_id = models.CharField(
        max_length=100, null=True, blank=True, db_comment="OpenAI 오류 파일 ID"
    )
    error = models.TextField(null=True, blank=True, db_comment="배치 실패 시 오류 내용")
    completed_at = models.DateTimeField(null=True, blank=True, db_comment="배치 완료 시각")
    created_at = models.DateTimeField(db_default=Now(), db_comment="행 생성 시각")
    updated_at = models.DateTimeField(db_default=Now(), db_comment="행 수정 시각")

    class Meta:
        db_table = "naver_tagging_batch"
        db_table_comment = "OpenAI Batch API 상품 태깅 작업 추적 (collector/naver batch_tagger가 기록)"
        verbose_name = "태깅 배치"
        verbose_name_plural = "태깅 배치"

    def __str__(self) -> str:
        return f"{self.batch_id} ({self.status})"


class NaverProductSize(models.Model):
    """상품 사이즈별 치수/측정값 (하위 종속 테이블).

    네이버 검색 API는 치수를 제공하지 않으므로 별도 수집/수동 입력으로 채운다.
    """

    product = models.ForeignKey(
        NaverProduct,
        on_delete=models.CASCADE,
        related_name="sizes",
        db_comment="대상 상품 FK (naver_product.id)",
    )
    size_label = models.CharField(
        max_length=30, db_comment="사이즈 표기 (S/M/L, 90~110, 230~290, FREE 등)"
    )
    size_system = models.CharField(
        max_length=20, null=True, blank=True, db_comment="사이즈 체계 (KR/US/EU/UK)"
    )

    # 공통 측정값 (cm)
    total_length = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="총장 (cm)"
    )
    shoulder_width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="어깨너비 (cm)"
    )
    chest_width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="가슴단면 (cm)"
    )
    sleeve_length = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="소매길이 (cm)"
    )
    waist_width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="허리단면 (cm)"
    )
    hip_width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="엉덩이단면 (cm)"
    )
    rise = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="밑위 (cm)"
    )
    thigh_width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="허벅지단면 (cm)"
    )
    hem_width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, db_comment="밑단단면 (cm)"
    )
    foot_length_mm = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, db_comment="발길이 (mm, 신발 전용)"
    )

    extra_measurements = models.JSONField(
        default=dict, blank=True, db_comment="기타 측정값 JSON (표준 컬럼 외 항목)"
    )
    source = models.CharField(
        max_length=30,
        default="manual",
        db_default="manual",
        db_comment="치수 출처 (manual: 수동 입력 / crawl: 별도 수집)",
    )
    created_at = models.DateTimeField(db_default=Now(), db_comment="행 생성 시각")
    updated_at = models.DateTimeField(db_default=Now(), db_comment="행 수정 시각")

    class Meta:
        db_table = "naver_product_size"
        db_table_comment = "상품 사이즈별 실측 치수 (naver_product 하위 종속, 사이즈 적합성 판단용)"
        verbose_name = "상품 사이즈"
        verbose_name_plural = "상품 사이즈"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size_label"], name="uq_naver_product_size_label"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product_id} / {self.size_label}"
