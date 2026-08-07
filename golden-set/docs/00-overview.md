# 골든셋 — 색상 추천 규칙 통합 가이드

> **색 조합, 퍼스널컬러, 4 카테고리, 레이어드, 패턴까지 한 곳에서**
> 작성: 2026-08-07 / 갱신: 추구미(PursuitMe) · 채팅 에이전트 · 옷장 RAG 통합

---

## 1. 골든셋이 뭔가 (1분 요약)

**골든셋**은 "이 조합이면 실패하지 않는다"는 **자동 판정 가능한 색 조합 규칙 모음**이다.
사람의 눈이 아니라 데이터(CIELCh 색상 속성 + 실사용 통계 + 퍼스널컬러 시즌)로 추천을 거절하거나 가산점을 준다.

| 구성 | 데이터 원천 | 역할 |
|------|------------|------|
| 17색 팔레트 (Black, White, Charcoal, Navy, Beige, Olive, Brown, Burgundy, Mustard, Teal, Gray, Cream, Rust, Forest Green, Lavender, Light Blue, Blush Pink) | CIELCh 변환 + Pinterest 레퍼런스 | 모든 색 조합의 기준점 |
| 4 카테고리 (Warm / Cool / Neutral / Muted) | Michael 84 차트 + 카테고리 팔레트 | 17색 묶음 — 어떤 카테고리에서 보색/토널을 가져올지 결정 |
| 4 시즌 (봄웜 / 여름쿨 / 가을웜 / 겨울쿨) | chart_warm/cool/neutral/muted.png의 season 태그 | 사용자가 "나는 봄웜" 식으로 입력하면 메인컬러 가이드 |
| 12 Pants (8 필수 + 4 추가) | CJ Logistics 2021 + 지그재그 2023 + 무신사 베스트 | 실제로 가지고 있는 바지 팔레트 |
| 17 Tops | v2 영문 17색 + 시즌별 undertone 분리 | 상의 색상 풀 |
| 레이어드 룩 매트릭스 | 재킷 60-30-10 법칙 + 5대 재킷 매칭표 | 이너/아우터 2~3겹 매칭 |
| 패턴/무늬 매칭 | 9가지 런웨이 룰 + doverman 정장 룰 | 스트라이프/체크/플로럴/도트 |
| 독특한/화려한 색상 | 2024 F/W 네온 + Sage Green + Olive Green + Bold Leopard | 무난한 베스트셀러 외 |
| 드레스/치마 색상 | Tagwalk 2024 F/W + Vogue Korea | 스커트/원피스 확장 |

---

## 2. 활용 시나리오 4가지 (핵심)

### 2.1. 추구미(PursuitMe) — 색상 선택 UI

```
[사용자] 추구미 진입
   → 우리 4 카테고리(Warm/Cool/Neutral/Muted) 중 선호 1~2개 선택
   → Michael 84 차트 표시 (메인 1 + 보색 5 + 뮤트/토널 2 = 8가지)
   → 17 tops × 12 pants = 204 조합 중 카테고리 매칭 우선 노출
   → 결과: top 10 코디 추천
```

**골든셋이 제공**: 4 카테고리 메인컬러 30개 + 보색 풀 + 4시즌 anchor 매핑
**골든셋이 안 함**: 실시간 의류 검색 (catalog API 담당), 사이즈 필터 (filter_rules.py 담당)

### 2.2. 채팅 에이전트 — 색상 규칙 전달

```
[사용자] "내일 비 오는 날에 면접 보러 가는데 뭐 입지?"
   [에이전트] → 시스템 프롬프트에 골든셋 요약 주입
              → 추천: "차콜 재킷 + 네이비 슬랙스 + 화이트 셔츠"
              → 이유: "60-30-10 법칙으로 차콜(60) + 네이비(30) + 화이트(10),
                     봄웜/가을웜 베이스 4 카테고리 무채색 universal 룩"
   [에이전트] → 추가: "혹시 봄웜이시면 이 컬러 추천드릴게 있어요"
```

**골든셋이 제공**: 
- 시스템 프롬프트용 압축 룰북 (60-30-10, 4 카테고리, 시즌 anchor)
- 추구미로 deep-link 가능

**에이전트가 활용**:
- `personal_color_season` 컨텍스트 (있으면 시즌 룰 적용)
- `style_preferences` 컨텍스트 (있으면 취향 우선)
- 없으면 universal 룰

### 2.3. 옷장 RAG — 사진 → 색상 추출 → 규칙 적용

```
[사용자] 옷장에 있는 옷 사진 업로드 (예: 30장)
   [RAG] → 이미지에서 색상 추출 (FashionSigLIP 또는 hex 평균)
         → wardrobe_item.color = 17색 중 1개로 매핑
         → items[i] = [{name, color_hex, color_v2, category}, ...]
   [추천] → 골든셋 4 카테고리 룰 적용
         → "지금 옷장에 있는 Olive pants와 어울리는 상의 5가지:
            Cream (Warm/Neutral), Beige (Neutral), Burgundy (Muted/Tonal),
            Charcoal (Cool), Mustard (Warm 톤온톤)"
```

**골든셋이 제공**:
- 17색 ↔ wardrobe_item.color 매핑표
- 카테고리 자동 분류 (color → category)
- 매칭 점수 산출 (R1~R6 룰 + L1~L5 룩 룰)

**RAG 파이프라인**:
- `indexer/util/fashion_siglip.py`로 임베딩 + 색상 평균 추출
- `apps/wardrobe/services/color_classifier.py`로 17색 분류
- `apps/recommend/services/golden_set_matcher.py`로 점수 산출

### 2.4. 퍼스널컬러 직접 입력 — 시즌 앵커

```
[사용자] "나는 봄웜이야"
   [시스템] → season_bonus 활성화
            → 봄웜 anchor: Coral, Light Coral, Peach, Marigold
            → 봄웜 neutral: Pure White, Ivory, Beige, Brown
            → 4 카테고리: Coral(● WARM), Beige(● NEUTRAL), Brown(● NEUTRAL)
            → 추천 시 WARM 카테고리 가중치 +20%
```

**4 시즌 × 4 카테고리 매핑 표**:

| 카테고리 | 🌸 봄웜 (Spring) | ☁️ 여름쿨 (Summer) | 🍂 가을웜 (Autumn) | ❄️ 겨울쿨 (Winter) |
|----------|------------------|-------------------|-------------------|-------------------|
| **WARM** | ● Coral, Peach, Marigold | | ● Terracotta, Rust, Honey Brown | |
| **COOL** | | | | ● Royal Blue, Cobalt, Fuchsia |
| **NEUTRAL** | ● White, Cream | ● Gray, Beige | ● Brown, Beige | ● Black, Pure White, Charcoal |
| **MUTED** | | ● Dusty Rose, Mauve, Sage | ● Taupe, Stone | ● Lavender Gray, Soft Plum |

→ **4 시즌은 "어떤 카테고리에서 메인컬러를 가져올지" 가이드일 뿐, hard rule 아님.**

---

## 3. 다른 카테고리 확장 (Top/Pants 외)

### 3.1. 드레스 / 원피스
- 2024 F/W: **레드 드레스 +1,659%** (Tagwalk 통계)
- 인기 색상: Black, Red, 핑크, 피스타치오 그린, 아이스크림 파스텔, 안개빛 보라, 옐로
- 실루엣: H자 슬림, 셔츠 원피스, 슬릿 스커트
- **드레스 팔레트 (확장)**: 위 17색 + 4 accent (Red #C71F37, Pistachio #BCD299, Icy Blue #B0E0E6, Heather Purple #B8A9C9)

### 3.2. 치마 / 스커트
- 2024 F/W: 하프스커트 +7%, 미니/미디/롱맥시 모두
- 17색 pants 팔레트 그대로 사용 가능 (치마도 같은 색상)
- + 화려한/특이한 색상 확장 (Pattern Mixing 섹션 참조)

### 3.3. 레이어드 룩 (아우터 + 이너)
- **60-30-10 법칙**: 바깥 60% → 중간 30% → 안쪽 10%
- 5대 재킷 매칭표:
  - 네이비 재킷 → 안감 Gray/Ivory, 바지 Charcoal/Beige
  - 올리브 재킷 → 안감 Oat/Light Gray, 바지 Indigo/Brown
  - 베이지 트렌치 → 안감 Stripe/White, 바지 Stone/Dark Gray
  - 차콜 재킷 → 안감 Black/Burgundy, 바지 Medium Gray
  - 브라운/헤링본 → 안감 Cream/Navy, 바지 Black/Ecru

### 3.4. 패턴/무늬
- **9가지 규칙**: 큰+작은 패턴, 톤 맞추기, 같은 계열, Black/Neutral과 믹스, 무지 1+패턴 1로 시작
- 조합 예시: 스트라이프+체크, 밀리터리+플로럴, 도트+플로럴
- v2에 `멀티` 태그 추가 (보조색 표현) — `secondary_color` 필드 검토

### 3.5. 독특한/화려한
- 2024 F/W 메인 트렌드: **"Color Clash"** (네온+파스텔), **"Bold Leopard"** (호피), **"Sage/Olive Green"**
- 네온: 핫 핑크, 바이올렛, 샛노랑, 스카이블루
- **화려한 팔레트 (확장)**: 위 17색 + 5 bold (Hot Pink #FF69B4, Lime #BFFF00, Leopard Print, Sage Green #9CAF88, Neon Yellow #DFFF00)

### 3.6. Drive 이미지 + 계절별 시장
- **Drive 골든셋 폴더** 5명 × 2-3 카테고리 = 12개 하위 폴더 (200+ 이미지)
  - 폴더 ID: `178wPfnaVOwRrOyKjOMvTSNE_wtFBCShy`
  - Drive API 인증 시 자동 색상 추출 → 17색 매핑
- **계절별 시장 데이터** (실제 의류 판매 통계)
  - 🌸 봄: Peach Fuzz (Pantone 2024), Olive 545%↑, Lavender, Mint
  - ☀️ 여름: White, Light Beige, Mint, Soft Blue, Light Khaki
  - 🍂 가을: Mocha Mousse (Pantone 2025), Burgundy, Brown 127%↑, Olive 120%↑
  - ❄️ 겨울: Black, Navy, Charcoal, Chocolate Brown, Camel
- **자세한 내용**: [10-drive-seasonal-palette.md](../color/docs/10-drive-seasonal-palette.md)

---

## 4. 어디서 읽나 (인덱스)

| 문서 | 내용 |
|------|------|
| [00-selection-criteria.md](00-selection-criteria.md) | 골든셋 통과 5축 (C1~C5) + 제외 조건 |
| [01-color-combination-rules.md](01-color-combination-rules.md) | 17색 CIELCh + 6개 규칙 R1~R6 + 룩 룰 L1~L5 |
| [02-personal-color.md](../color/docs/02-personal-color.md) | 4시즌 × 4 카테고리 매핑 + 16 sub-type |
| [03-color-categories.md](../color/docs/03-color-categories.md) | 4 카테고리 정의 + 30+ 메인컬러 |
| [04-combination-rules.md](../color/docs/04-combination-rules.md) | Michael 84 차트 + R1~R4 매칭 룰 |
| [05-use-cases.md](05-use-cases.md) | 4가지 활용 시나리오 상세 + API 입출력 |
| [06-layered-look.md](06-layered-look.md) | 60-30-10 + 5대 재킷 매칭 + 3단계 레이어드 |
| [07-bold-unique.md](07-bold-unique.md) | 2024 네온/호피/Sage/Olive + 화려한 팔레트 |
| [08-pattern-mixing.md](08-pattern-mixing.md) | 9가지 패턴 매칭 룰 + 4가지 조합 예시 |
| [09-dress-skirt.md](09-dress-skirt.md) | 드레스/치마 색상 통계 + 확장 팔레트 |
| [data-research.md](data-research.md) | CJ Logistics 2021 + 지그재그 2023 데이터 |
| [common-colors.md](../color/docs/common-colors.md) | 12 Pants + 17 Tops 데이터 기반 팔레트 |
| [pinterest-color-combos.md](../color/docs/pinterest-color-combos.md) | Pinterest 인기 색조합 cross-reference |
| `rules/category_palettes.json` | 4 카테고리 × 30+ 메인컬러 hex |
| `rules/combination_matches.json` | 카테고리 간 보색 + 토널 매칭 |
| `rules/real_world_palette.json` | 실사용 통계 기반 팔레트 |
| `rules/season_color_mapping.json` | 4시즌 × 17색 매핑 |
| `outfits/v6_grids/outfit_v6_*.png` | 17장 outfit grid (top별 × 12 pants) |
| `outfits/combination_charts/chart_*.png` | 4 카테고리 Michael 84 차트 |

---

## 5. 빠른 사용법

**추천 받고 싶을 때**:
1. 사용자 컨텍스트 수집: 퍼스널컬러, 체형, 취향, 보유 옷장
2. 카테고리(Warm/Cool/Neutral/Muted) 1~2개 선택 or 자동 분류
3. 17 tops × 12 pants 매트릭스에서 카테고리 보색 우선 → top-K 추출
4. 룩 룰 L1~L5 적용 (3색 이하, 뉴트럴 1+, chroma ≥45 1개까지)
5. RAG로 옷장 색상 매칭 보강
6. 결과 + 이유 출력 (시즌 anchor, 카테고리, 룰 근거)

**색상 정하고 싶을 때**:
1. 4 카테고리 차트(`combination_charts/chart_*.png`) 참고
2. 메인 1 + 보색 5 + 뮤트/토널 2 = 8가지 중 선택
3. 17색 hex는 `rules/category_palettes.json`에서 인용
