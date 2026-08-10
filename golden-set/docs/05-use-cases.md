# 활용 시나리오 — 추구미 · 채팅 · 옷장 RAG · 퍼스널컬러

> **누가, 어디서, 어떻게 골든셋을 쓰나** — 4가지 핵심 시나리오 + API 입출력 + UI 가이드

---

## 1. 시나리오 4가지

### 1.1. 추구미 (PursuitMe) — 색상 선택 UI

**사용자 동선**:
```
[진입] → [카테고리 선택 1~2개] → [Michael 84 차트 보기] → [top-K 코디 보기] → [저장/공유]
```

**입력**:
- `user_id`
- `preferred_categories`: ["warm", "neutral"] (선택)
- `personal_color_season`: "spring" (선택, 4 시즌)
- `body_type`: "hourglass" (선택, 사이즈코리아 6체형)

**출력**:
- 4 카테고리 메인컬러 30개 (8개씩)
- 사용자가 선택한 카테고리 기준 보색 풀
- top-10 코디 (top × pants, hex + reason)

**UI 흐름**:
1. **카테고리 카드 4개** (Warm/Cool/Neutral/Muted) — 클릭 가능
2. **Michael 84 차트** — 메인 1 + 보색 5 + 뮤트 2 = 8개 스왓치
3. **outfit 그리드** — 선택한 top 1개 × 12 pants = 12 코디 (Pinterest 스타일)
4. **필터**: 시즌 / 체형 / TPO / 취향 (기피 색)

### 1.2. 채팅 에이전트 — 시스템 프롬프트 주입

**시스템 프롬프트 발췌 (예시)**:
```
너는 패션 어시스턴트야. 색상 추천 시 다음 골든셋을 따른다:
- 4 카테고리: Warm(따뜻한 노랑/주황/갈색), Cool(차가운 파랑/보라/녹색), Neutral(무채색+아이보리), Muted(저채도)
- 17색 팔레트: Black, White, Charcoal, Navy, Beige, Olive, Brown, Burgundy, Mustard, Teal, Gray, Cream, Rust, Forest Green, Lavender, Light Blue, Blush Pink
- 4시즌 anchor: 봄웜=Coral/Peach/Marigold, 여름쿨=Dusty Rose/Sage, 가을웜=Terracotta/Rust, 겨울쿨=Royal Blue/Cobalt
- 60-30-10 법칙 (레이어드): 바깥 60% + 중간 30% + 안쪽 10%
- 룩 룰: 한 룩에 색 3개 이하, 뉴트럴 1+ 필수, 고채도(chroma≥45) 1개까지
- 패턴 매칭: 큰+작은 패턴, 톤 맞추기, 무지 1+패턴 1로 시작

추천 형식:
1. 코디 이름 (예: "Autumn Tonal")
2. 아이템별 색상 + hex
3. 추천 이유 (시즌 anchor / 카테고리 보색 / 룩 룰)
4. 대안 1~2개
```

**대화 예시**:
```
사용자: 내일 면접인데 봄웜이야. 뭐 입지?
에이전트:
  추천: "Ivory 블라우스 + Brown 슬랙스 + Camel 코트"
  이유:
    - 봄웜 anchor: Ivory/Brown이 NEUTRAL·spring/autumn 매칭
    - 룩 룰 L1: 색 3개, L2: 뉴트럴 1+, L3: chroma 모두 <45 ✓
    - TPO: 면접 → 무채색+earth tone으로 진중함
  대안:
    - "Cream 셔츠 + Navy 슬랙스 + Camel 코트" (winter/cool anchor)
    - "Beige 니트 + Brown 슬랙스 + Ivory 코트" (모두 NEUTRAL 봄웜)
```

### 1.3. 옷장 RAG — 사진 → 색상 → 매칭

**파이프라인**:
```
[사진 업로드] (옷장 30장)
   ↓
[FashionSigLIP 임베딩] (ml/indexer/util/fashion_siglip.py)
   ↓
[색상 평균 추출] (mean RGB → hex)
   ↓
[17색 분류] (apps/wardrobe/services/color_classifier.py)
   - 17색 centroid와 cosine similarity → 가장 가까운 1개
   - 보조색 secondary_color도 추출 (패턴/배색 대응)
   ↓
[wardrobe_item 저장] (color, color_v2, category, season_affinity)
   ↓
[골든셋 매처] (apps/recommend/services/golden_set_matcher.py)
   - 17 tops × 12 pants = 204 조합 × R1~R6 룰 × L1~L5 룩 룰
   - 점수 = 카테고리 보색 매칭 + 시즌 anchor 보너스 + RAG 보유 매칭
   - top-10 추출
   ↓
[추천 결과]
   - "보유 Olive pants와 어울리는 상의 5가지:
      1. Cream (Warm/Neutral) — 카테고리 보색 + 봄웜 anchor
      2. Beige (Neutral) — 톤온톤 + 가을웜 anchor
      3. Burgundy (Muted/Tonal) — Brown family tonal
      4. Charcoal (Cool) — 명도 대비 + universal
      5. Mustard (Warm 톤온톤) — autumn anchor"
```

**핵심 로직**:
- `wardrobe_item.color`는 한국어 17색 (`taxonomy.py::COLORS`)
- v2 조회 시 `color_taxonomy_map.json`을 거쳐 17색 영문으로 변환
- 이후 R1~R6 룰 적용

### 1.4. 퍼스널컬러 직접 입력

**입력**: `personal_color_season: "spring"`

**시스템 처리**:
```python
def apply_season_bonus(season, color_v2):
    season_anchors = {
        "spring": ["Coral", "Light Coral", "Peach", "Marigold", "Ivory", "Beige", "Brown"],
        "summer": ["Dusty Rose", "Mauve", "Sage", "Eucalyptus", "Medium Gray", "Pure White"],
        "autumn": ["Mustard", "Burnt Orange", "Terracotta", "Rust", "Olive", "Taupe", "Brown"],
        "winter": ["Royal Blue", "Cobalt", "Fuchsia", "True Red", "Black", "Charcoal", "Pure White"]
    }
    bonus = 0.2 if color_v2 in season_anchors[season] else 0.0
    return bonus
```

**출력**:
- 봄웜 메인컬러 8색 + 보색 풀
- WARM 카테고리 가중치 +20%
- 추천 결과 정렬 시 시즌 매칭 점수 반영

---

## 2. API 입출력

### 2.1. 추천 API (`POST /api/v1/recommend/`)

**Request**:
```json
{
  "user_id": 123,
  "personal_color_season": "autumn",          // spring/summer/autumn/winter (선택)
  "body_type": "round",                       // round/inverted_triangle/triangle/hourglass/rectangle/standard (선택)
  "tpo": "casual",                            // casual/business/formal/sport (선택)
  "preferred_categories": ["warm", "neutral"], // 사용자가 선호하는 카테고리 (선택)
  "occasion": "weekend brunch",               // 자유 입력 (선택)
  "wardrobe_rag_enabled": true,               // 옷장 RAG 모드 (선택)
  "style_preferences": {                      // 개인 취향
    "preferred_colors": ["burgundy", "olive"],
    "avoided_colors": ["neon yellow"]
  }
}
```

**Response**:
```json
{
  "user_id": 123,
  "applied_season": "autumn",
  "applied_categories": ["warm", "neutral"],
  "recommendations": [
    {
      "rank": 1,
      "top": {"name": "Terracotta", "hex": "#C2684E", "category": "warm"},
      "bottom": {"name": "Cream", "hex": "#F5E6CC", "category": "neutral"},
      "score": 0.92,
      "reasons": [
        "autumn season affinity (warm × warm-leaning)",
        "terracotta + cream: high lightness contrast (L:45 vs L:91)",
        "neutral cream balances warm terracotta",
        "R2 (one side neutral) → 권장",
        "L1 (3색 룰) / L2 (뉴트럴 1+) / L3 (chroma<45) 모두 통과"
      ]
    },
    {
      "rank": 2,
      "top": {"name": "Olive", "hex": "#6B6B45", "category": "warm"},
      "bottom": {"name": "Black", "hex": "#1E1E2E", "category": "neutral"},
      "score": 0.88,
      "reasons": [
        "autumn anchor match (Olive = WARM·autumn)",
        "Black universal match",
        "R2 + L2 통과"
      ]
    }
  ]
}
```

### 2.2. 색상 선택 API (`GET /api/v1/golden-set/palette/{category}/`)

**Response**:
```json
{
  "category": "warm",
  "main_colors": [
    {"name": "Coral", "hex": "#FF6F61", "season_anchors": ["spring"]},
    {"name": "Terracotta", "hex": "#C2684E", "season_anchors": ["autumn"]},
    {"name": "Mustard", "hex": "#D4A017", "season_anchors": ["autumn"]},
    {"name": "Rust", "hex": "#B5523A", "season_anchors": ["autumn"]}
  ],
  "complementary": {
    "cool": ["Royal Blue", "Cobalt"],
    "neutral": ["Black", "Beige", "Charcoal"]
  },
  "muted_tonal": {
    "warm": ["Honey Brown", "Burnt Orange"],
    "muted": ["Taupe", "Stone"]
  }
}
```

---

## 3. UI 활용 가이드

### 3.1. 차트 미리보기
- `combination_charts/chart_*.png` 4장 (Warm/Cool/Neutral/Muted)
- Michael 84 패턴: 메인 1 + 보색 5 + 뮤트 2 = 8가지
- "이 색과 어울리는 8가지" 한눈에

### 3.2. outfit 이미지 갤러리
- `outfits/v6_grids/outfit_v6_*.png` 17장 (top별)
- 각 3×4 그리드 (12 pants × 1 top)
- "이렇게 매치해보세요" 시각 가이드

### 3.3. 색상 팔레트 (사용자 시즌 기반)
- 4 카테고리 × 8 메인컬러 = 32개 hex
- 시즌 anchor 강조 표시
- "당신의 WARM 팔레트는 8가지입니다"

### 3.4. 레이어드 룩 미리보기
- `06-layered-look.md` 5대 재킷 매칭표
- 60-30-10 비율 시각화
- 재킷-이너-팬츠 3-tier 추천

### 3.5. 패턴 매칭 미리보기
- `08-pattern-mixing.md` 9가지 룰
- 패턴별 추천 조합 시각화 (스트라이프+체크 등)

---

## 4. 활용처 매트릭스

| 활용처 | 입력 | 출력 | 핵심 기능 |
|--------|------|------|----------|
| **추구미 (PursuitMe)** | 카테고리 선택 | top-10 코디 | 4 카테고리 + 4 시즌 + RAG |
| **채팅 에이전트** | 자연어 + 컨텍스트 | 코디 + 이유 | 시스템 프롬프트 주입 |
| **옷장 RAG** | 사진 → 색상 | 어울리는 옷 추천 | 17색 분류 + 매처 |
| **카탈로그 UI** | 상품 ID | "이 상품과 어울리는 5가지" | R1~R6 룰 조회 |
| **스타일 가이드 PDF** | 시즌 | 차트 + outfit 갤러리 | 정적 출력 |
| **옷장 정리 도우미** | 보유 옷 리스트 | "이 옷이 안 어울려요" | RAG + 룩 룰 L1~L5 |

---

## 5. 확장 가능성

- **체형 매핑**: `body_shape_thresholds.json` + `body_fit_rules.json` — 사이즈코리아 6체형 × 4차원
- **TPO 필터**: 비즈니스/캐주얼/포멀/스포츠별 톤 규칙
- **시즌성**: 봄/여름/가을/겨울 옷장 분리 추천
- **가격대**: 예산별 추천 (저가/중가/고가)
- **드레스/치마**: `09-dress-skirt.md` 확장 팔레트
- **레이어드**: `06-layered-look.md` 5대 재킷 룰
- **패턴**: `08-pattern-mixing.md` 9가지 룰
- **화려한 색**: `07-bold-unique.md` 네온/호피/Sage/Olive
