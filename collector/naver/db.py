"""
네이버 상품 collector DB 계층.

테이블
- naver_product      : 수집 상품 원본 + 문서 분류/태그 (insert 전에 태깅 완료가 원칙)
- naver_product_size : 상품 사이즈별 치수/측정값 (하위 종속 테이블, 스키마만 정의)

주의
- weather collector와 동일하게, 운영 전환 시 이 DDL은 Django model/migration으로
  옮기는 것을 권장한다. --init-schema는 로컬/개발 PostgreSQL용이다.
"""

from __future__ import annotations

from typing import Any, Sequence, Tuple

from config import DATABASE_URL, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, logger

try:
    import psycopg2
    from psycopg2.extras import Json, execute_values
except ImportError:  # pragma: no cover - Docker/서버에서 설치 필요
    psycopg2 = None
    Json = None
    execute_values = None


def get_connection():
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2가 설치되어 있지 않습니다. requirements.naver.txt를 설치하세요."
        )
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )


DDL = """
CREATE TABLE IF NOT EXISTS naver_product (
    id BIGSERIAL PRIMARY KEY,

    -- 네이버 원본 필드
    naver_product_id VARCHAR(40) NOT NULL,
    product_type SMALLINT,                 -- 1~3 일반 / 4~6 중고 / 7~9 단종 / 10~12 판매예정
    title VARCHAR(500) NOT NULL,           -- <b> 태그 등 제거한 상품명
    title_raw VARCHAR(500),                -- API 원본 title
    link TEXT,
    image_url TEXT,
    lprice INTEGER,                        -- 최저가 (원)
    hprice INTEGER,                        -- 최고가 (원, 없으면 NULL)
    mall_name VARCHAR(200),
    brand VARCHAR(200),
    maker VARCHAR(200),
    naver_category1 VARCHAR(100),
    naver_category2 VARCHAR(100),
    naver_category3 VARCHAR(100),
    naver_category4 VARCHAR(100),

    -- 컨플루언스 문서 분류 (카테고리-태그 매핑 문서 기준)
    category_large VARCHAR(30) NOT NULL,
    category_small VARCHAR(50) NOT NULL,
    category_source VARCHAR(20) NOT NULL DEFAULT 'keyword',  -- naver_category | keyword

    -- 문서 태그 체계 (규칙 추출 + LLM 태깅)
    season TEXT[] NOT NULL DEFAULT '{}',       -- 봄/여름/가을/겨울/간절기
    style TEXT[] NOT NULL DEFAULT '{}',        -- 캐주얼/포멀/미니멀 등 후보군
    color TEXT[] NOT NULL DEFAULT '{}',
    pattern TEXT[] NOT NULL DEFAULT '{}',
    fit VARCHAR(30),
    material TEXT[] NOT NULL DEFAULT '{}',
    sleeve VARCHAR(20),
    length VARCHAR(20),
    usage TEXT[] NOT NULL DEFAULT '{}',
    layer_role VARCHAR(30),
    layer_order SMALLINT,

    -- 태깅 메타
    tag_source JSONB NOT NULL DEFAULT '{}'::jsonb,  -- 필드별 출처 {"color": "rule", "style": "llm", ...}
    tagging_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | tagged | failed
    tagging_model VARCHAR(60),
    tagging_used_image BOOLEAN NOT NULL DEFAULT FALSE,
    tagged_at TIMESTAMPTZ,

    -- 수집 메타
    search_keyword VARCHAR(100),           -- 이 상품을 발견한 검색어
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    collected_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (naver_product_id)
);

CREATE INDEX IF NOT EXISTS ix_naver_product_category
    ON naver_product (category_large, category_small);
CREATE INDEX IF NOT EXISTS ix_naver_product_tagging_status
    ON naver_product (tagging_status);
CREATE INDEX IF NOT EXISTS ix_naver_product_season
    ON naver_product USING GIN (season);
CREATE INDEX IF NOT EXISTS ix_naver_product_style
    ON naver_product USING GIN (style);

-- 사이즈별 치수/측정값 하위 테이블.
-- 네이버 검색 API는 치수 정보를 제공하지 않으므로 별도 수집(상세페이지, 수동 입력 등)으로
-- 채우는 것을 전제로 스키마만 정의한다.
CREATE TABLE IF NOT EXISTS naver_product_size (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES naver_product(id) ON DELETE CASCADE,

    size_label VARCHAR(30) NOT NULL,       -- S/M/L/XL, 90~110, 26~34, 230~290, FREE 등
    size_system VARCHAR(20),               -- KR/US/EU/UK 등 표기 체계

    -- 공통 측정값 (cm 단위, 해당 없는 항목은 NULL)
    total_length NUMERIC(6, 2),            -- 총장
    shoulder_width NUMERIC(6, 2),          -- 어깨너비
    chest_width NUMERIC(6, 2),             -- 가슴단면
    sleeve_length NUMERIC(6, 2),           -- 소매길이
    waist_width NUMERIC(6, 2),             -- 허리단면
    hip_width NUMERIC(6, 2),               -- 힙단면
    rise NUMERIC(6, 2),                    -- 밑위
    thigh_width NUMERIC(6, 2),             -- 허벅지단면
    hem_width NUMERIC(6, 2),               -- 밑단단면
    foot_length_mm NUMERIC(6, 1),          -- 신발 발길이 (mm)

    -- 위 공통 컬럼으로 표현 안 되는 측정값 {"스트랩길이": 120.0, ...}
    extra_measurements JSONB NOT NULL DEFAULT '{}'::jsonb,

    source VARCHAR(30) NOT NULL DEFAULT 'manual',  -- manual | csv | detail_page | llm
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (product_id, size_label)
);

CREATE INDEX IF NOT EXISTS ix_naver_product_size_product
    ON naver_product_size (product_id);
"""


def init_schema(conn) -> None:
    """로컬/개발용 테이블 생성. 운영에서는 Django migration 사용 권장."""
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
    logger.info("naver_product / naver_product_size 스키마 생성/확인 완료")


PRODUCT_COLUMNS = [
    "naver_product_id", "product_type", "title", "title_raw", "link", "image_url",
    "lprice", "hprice", "mall_name", "brand", "maker",
    "naver_category1", "naver_category2", "naver_category3", "naver_category4",
    "category_large", "category_small", "category_source",
    "season", "style", "color", "pattern", "fit", "material", "sleeve", "length",
    "usage", "layer_role", "layer_order",
    "tag_source", "tagging_status", "tagging_model", "tagging_used_image", "tagged_at",
    "search_keyword", "raw_data", "collected_at",
]


def upsert_products(conn, rows: Sequence[Tuple[Any, ...]]) -> int:
    """
    naver_product upsert. naver_product_id 충돌 시 가격/태그/메타를 갱신한다.
    rows의 각 원소는 PRODUCT_COLUMNS 순서의 튜플이어야 한다.
    """
    if not rows:
        return 0
    columns = ", ".join(PRODUCT_COLUMNS)
    sql = f"""
    INSERT INTO naver_product ({columns}) VALUES %s
    ON CONFLICT (naver_product_id)
    DO UPDATE SET
        product_type = EXCLUDED.product_type,
        title = EXCLUDED.title,
        title_raw = EXCLUDED.title_raw,
        link = EXCLUDED.link,
        image_url = EXCLUDED.image_url,
        lprice = EXCLUDED.lprice,
        hprice = EXCLUDED.hprice,
        mall_name = EXCLUDED.mall_name,
        brand = EXCLUDED.brand,
        maker = EXCLUDED.maker,
        naver_category1 = EXCLUDED.naver_category1,
        naver_category2 = EXCLUDED.naver_category2,
        naver_category3 = EXCLUDED.naver_category3,
        naver_category4 = EXCLUDED.naver_category4,
        category_large = EXCLUDED.category_large,
        category_small = EXCLUDED.category_small,
        category_source = EXCLUDED.category_source,
        season = EXCLUDED.season,
        style = EXCLUDED.style,
        color = EXCLUDED.color,
        pattern = EXCLUDED.pattern,
        fit = EXCLUDED.fit,
        material = EXCLUDED.material,
        sleeve = EXCLUDED.sleeve,
        length = EXCLUDED.length,
        usage = EXCLUDED.usage,
        layer_role = EXCLUDED.layer_role,
        layer_order = EXCLUDED.layer_order,
        tag_source = EXCLUDED.tag_source,
        tagging_status = EXCLUDED.tagging_status,
        tagging_model = EXCLUDED.tagging_model,
        tagging_used_image = EXCLUDED.tagging_used_image,
        tagged_at = EXCLUDED.tagged_at,
        search_keyword = EXCLUDED.search_keyword,
        raw_data = EXCLUDED.raw_data,
        collected_at = EXCLUDED.collected_at,
        updated_at = NOW()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    return len(rows)


def fetch_products_for_retag(conn, limit: int = 500) -> list[dict]:
    """태깅 실패/미완료 상품 조회 (--job retag 용)."""
    sql = """
    SELECT id, naver_product_id, title, image_url,
           naver_category1, naver_category2, naver_category3, naver_category4,
           category_large, category_small
    FROM naver_product
    WHERE tagging_status IN ('pending', 'failed')
    ORDER BY id
    LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        col_names = [desc[0] for desc in cur.description]
        return [dict(zip(col_names, row)) for row in cur.fetchall()]


def update_product_tags(conn, product_id: int, tags: dict, meta: dict) -> None:
    """retag 결과 반영."""
    sql = """
    UPDATE naver_product SET
        season = %s, style = %s, color = %s, pattern = %s,
        fit = %s, material = %s, sleeve = %s, length = %s,
        usage = %s, layer_role = %s, layer_order = %s,
        tag_source = %s, tagging_status = %s, tagging_model = %s,
        tagging_used_image = %s, tagged_at = NOW(), updated_at = NOW()
    WHERE id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            tags.get("season", []), tags.get("style", []),
            tags.get("color", []), tags.get("pattern", []),
            tags.get("fit"), tags.get("material", []),
            tags.get("sleeve"), tags.get("length"),
            tags.get("usage", []), tags.get("layer_role"), tags.get("layer_order"),
            Json(meta.get("tag_source", {})), meta.get("tagging_status", "tagged"),
            meta.get("tagging_model"), meta.get("tagging_used_image", False),
            product_id,
        ))
    conn.commit()
