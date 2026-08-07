# 골든셋 — 색상 추천 규칙 통합

> **색 조합, 퍼스널컬러, 4 카테고리, 레이어드, 패턴까지 한 곳에서**
> 추구미(PursuitMe) · 채팅 에이전트 · 옷장 RAG · 퍼스널컬러 4가지 시나리오 지원

---

## 0. 빠른 인덱스

| # | 문서 | 내용 |
|---|------|------|
| 0 | [00-overview.md](00-overview.md) | **골든셋 통합 가이드 + 4가지 활용 시나리오** |
| 0 | [00-selection-criteria.md](00-selection-criteria.md) | 통과 5축 (C1~C5) + 제외 조건 |
| 1 | [01-color-combination-rules.md](01-color-combination-rules.md) | 17색 CIELCh + 6개 규칙 R1~R6 |
| 2 | [02-personal-color.md](02-personal-color.md) | 4시즌 × 4 카테고리 + 16 sub-type |
| 3 | [03-color-categories.md](03-color-categories.md) | 4 카테고리 정의 + 30+ 메인컬러 |
| 4 | [04-combination-rules.md](04-combination-rules.md) | Michael 84 차트 + R1~R4 |
| 5 | [05-use-cases.md](05-use-cases.md) | 추구미·채팅·옷장RAG·퍼스널컬러 |
| 6 | [06-layered-look.md](06-layered-look.md) | 60-30-10 + 5대 재킷 매칭 |
| 7 | [07-bold-unique.md](07-bold-unique.md) | 2024 네온/호피/Sage/Olive |
| 8 | [08-pattern-mixing.md](08-pattern-mixing.md) | 9가지 패턴 매칭 룰 |
| 9 | [09-dress-skirt.md](09-dress-skirt.md) | 드레스/치마 색상 + 확장 팔레트 |
| 9 | [data-research.md](data-research.md) | CJ Logistics + 지그재그 실사용 데이터 |
| 7 | [common-colors.md](common-colors.md) | 12 Pants + 17 Tops 팔레트 |
| 8 | [pinterest-color-combos.md](pinterest-color-combos.md) | Pinterest 인기 색조합 |
| 2 | [body-proportion-rules.md](body-proportion-rules.md) | 체형·비율 4차원 처방 |
| 3 | [body-proportion-matrix.md](body-proportion-matrix.md) | 5체형 × 4차원 매트릭스 |

---

## 1. 골든셋이란

**골든셋 = "이 조합이면 실패하지 않는다"는 자동 판정 가능한 색 조합 규칙.**

사람의 눈이 아니라 데이터(CIELCh + 실사용 통계 + 퍼스널컬러 시즌)로 추천을 거절하거나 가산점을 준다.

| 구성 | 역할 |
|------|------|
| 17색 팔레트 (영문) | 모든 색 조합의 기준점 |
| 4 카테고리 (Warm/Cool/Neutral/Muted) | 17색 묶음 — 보색/토널 규칙 |
| 4 시즌 (봄웜/여름쿨/가을웜/겨울쿨) | 사용자 입력 시 anchor 가이드 |
| 12 Pants (8 필수 + 4 추가) | 실제 보유 바지 팔레트 |
| 17 Tops | 상의 색상 풀 |
| 6 규칙 (R1~R6) | 색 조합 등급 (권장/허용/주의/기피) |
| 5 룩 룰 (L1~L5) | 한 룩 전체에 적용 |
| 레이어드 매트릭스 | 아우터+이너 2~3겹 |
| 9 패턴 룰 | 스트라이프/체크/플로럴/도트 |
| 4 확장 카테고리 | 드레스/치마/레이어드/패턴/화려한 |

---

## 2. 활용 시나리오 4가지

1. **추구미 (PursuitMe)** — 4 카테고리 + Michael 84 차트 + outfit 그리드
2. **채팅 에이전트** — 시스템 프롬프트에 룰 요약 주입, 자연어 추천
3. **옷장 RAG** — 사진 → 17색 분류 → 4 카테고리 매칭
4. **퍼스널컬러** — "나는 봄웜" 입력 시 WARM 카테고리 가중치

자세한 내용: [00-overview.md §2](00-overview.md), [05-use-cases.md](05-use-cases.md)

---

## 3. 데이터 원천

| 출처 | 용도 |
|------|------|
| **CJ Logistics 2021** | 의류 배송 색상 통계 (무채색 62%) |
| **지그재그 2023** | 판매 색상 통계 (Black 32%, Beige 23%) |
| **무신사 베스트** | 카테고리별 1위 색상 |
| **매경 2024** | 검색량 추이 (Olive 545%↑, Mint 380%↑, Violet 162%↑) |
| **KS 15색** | 선호도 설문 (Blue 36%, Black 29%) |
| **Pinterest** | 색조합 reference (Korean aesthetic, Chocomint, Color clash) |
| **Tagwalk 2024 F/W** | 런웨이 색상 통계 (Red dress +1,659%) |

---

## 4. 폴더 구조

```
docs/golden-set/
├── 00-overview.md                    # 통합 가이드
├── 00-selection-criteria.md         # 통과 5축
├── 01-color-combination-rules.md    # 17색 + R1~R6
├── 02-personal-color.md             # 4시즌 × 4 카테고리
├── 02-body-proportion-rules.md      # 체형 4차원
├── 03-color-categories.md           # 4 카테고리
├── 03-body-proportion-matrix.md     # 5체형 매트릭스
├── 04-combination-rules.md          # Michael 84
├── 05-use-cases.md                  # 4 시나리오 + API
├── 06-layered-look.md               # 60-30-10 + 5 재킷
├── 07-bold-unique.md                # 네온/호피/Sage/Olive
├── 08-pattern-mixing.md             # 9가지 패턴 룰
├── 09-dress-skirt.md                # 드레스/치마
├── README.md                        # 본 파일
├── recommendation-golden-set-guide.md
├── data-research.md                 # 실사용 데이터
├── common-colors.md                 # 12 pants + 17 tops
├── pinterest-color-combos.md        # Pinterest 인사이트
│
├── rules/                           # JSON 데이터
│   ├── category_palettes.json
│   ├── combination_matches.json
│   ├── real_world_palette.json
│   ├── season_color_mapping.json
│   ├── color_rules.json
│   ├── color_matrix.md
│   ├── personal_color_palettes.json
│   ├── body_fit_rules.json
│   └── body_shape_thresholds.json
│
├── tools/                           # 생성 스크립트
│   ├── compute_color_attributes.py
│   ├── build_color_rules.py
│   ├── gen_personal_color.py
│   ├── render_combination_chart.py
│   ├── gen_v6_grids.py
│   ├── gen_practical_grids.py
│   ├── extract_grade_map.py
│   ├── detect_grade_map_v2.py
│   ├── gen_batch_requests.py
│   ├── gen_grid_requests.py
│   ├── gen_curated_grids.py
│   ├── generate_outfit_grid.py
│   ├── derive_body_thresholds.py
│   └── derive_color_matrix.py
│
├── assets/
│   ├── pinterest_ref.jpg
│   └── references/                  # Pinterest 23장
│
└── outfits/
    ├── combination_charts/          # chart_*.png 4장
    ├── v6_grids/                    # outfit_v6_*.png 17장
    ├── practical/                   # outfit_practical_*.png 17장
    ├── personal_color/              # outfit_pc_*.png 4장
    ├── outfit_grid_*.png            # 17장
    └── _batches/                    # batch JSON
```

---

## 5. 빠른 시작

**추천 받고 싶을 때**:
1. [00-overview.md §5](00-overview.md) 빠른 사용법
2. [05-use-cases.md](05-use-cases.md) 시나리오 + API

**색상 정하고 싶을 때**:
1. [combination_charts/chart_*.png](outfits/combination_charts/) 4장 차트
2. [rules/category_palettes.json](rules/category_palettes.json) hex

**옷장 RAG 구현할 때**:
1. [01-color-combination-rules.md §6](01-color-combination-rules.md) 태그 매핑
2. [05-use-cases.md §1.3](05-use-cases.md) RAG 파이프라인

**퍼스널컬러 적용할 때**:
1. [02-personal-color.md](02-personal-color.md) 4시즌 × 4 카테고리
2. [rules/season_color_mapping.json](rules/season_color_mapping.json) 68색
