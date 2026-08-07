# 퍼스널컬러 4시즌 × 4 카테고리

> **참고용 reference**: 퍼스널컬러는 추천의 **anchor 가이드**이지 hard rule이 아님.
> 사용자가 "나는 봄웜"이라 입력하면 그 시즌의 메인컬러에 가중치를 줄 뿐, 다른 시즌 색상을 막지 않는다.

---

## 1. 4시즌 개요

| 시즌 | 한글 | 베이스 | 무드 | 대표색 |
|------|------|--------|------|--------|
| **Spring** | 🌸 봄웜 | Yellow 베이스 | 상쾌, 활기 | 코랄, 크림옐로, 연두, 민트 |
| **Summer** | ☁️ 여름쿨 | Blue 베이스 | 차분, 맑음 | 미스트블루, 로즈베이지, 라벤더 |
| **Autumn** | 🍂 가을웜 | Gold 베이스 | 깊이, 빈티지 | 카라멜브라운, 벽돌, 올리브 |
| **Winter** | ❄️ 겨울쿨 | Blue-Purple 베이스 | 시크, 럭셔리 | 트루레드, 로열블루, 순백 |

---

## 2. 16 Sub-types

| Season | Sub-types |
|--------|-----------|
| Spring | Bright / Light / Warm / Clear |
| Summer | Light / Bright / Muted / Cool |
| Autumn | Soft / Warm / Deep / Muted |
| Winter | Bright / Cool / Deep / Clear |

각 sub-type은 같은 시즌 안에서 채도·명도·온도 중 하나가 강한 변형. `rules/personal_color_palettes.json`에 16 sub-type × hex 4~5개 = 68색 매핑.

---

## 3. 4시즌 메인컬러 (v6 chart 기반 추출)

차트 `combination_charts/chart_{warm,cool,neutral,muted}.png`의 season 태그에서 직접 추출한 hex.

### 🌸 봄웜 (Spring Warm) — WARM 차트 spring + NEUTRAL spring/autumn

| 색상 | hex | 출처 |
|------|-----|------|
| Coral | #FF6F61 | WARM·spring |
| Light Coral | #FF8F7A | WARM·spring |
| Peach | #F8838A | WARM·spring |
| Marigold | #F4A51C | WARM·spring |
| Pure White | #FFFFFF | NEUTRAL (봄도 OK) |
| Ivory | #F2E8D5 | NEUTRAL·spring/autumn |
| Beige | #D9C3A5 | NEUTRAL·spring/autumn |
| Brown | #6B4F3A | NEUTRAL·spring/autumn |

### ☁️ 여름쿨 (Summer Cool) — MUTED 차트 soft summer + NEUTRAL summer/winter

| 색상 | hex | 출처 |
|------|-----|------|
| Dusty Rose | #C9809A | MUTED·soft summer |
| Mauve | #B57B9A | MUTED·soft summer |
| Soft Rose | #C894AD | MUTED·soft summer |
| Sage | #9CB3A0 | MUTED·soft summer |
| Eucalyptus | #789486 | MUTED·soft summer |
| Stone | #B8A99A | MUTED·soft summer |
| Mushroom | #B8A99A | MUTED·soft summer |
| Soft Plum | #6F4E73 | MUTED·soft summer |
| Lavender Gray | #A99AC4 | MUTED·soft summer |
| Medium Gray | #808080 | NEUTRAL·summer/winter |
| Pure White | #FFFFFF | NEUTRAL·summer/winter |

### 🍂 가을웜 (Autumn Warm) — WARM 차트 autumn + MUTED soft autumn + NEUTRAL spring/autumn

| 색상 | hex | 출처 |
|------|-----|------|
| Mustard | #D4A017 | WARM·autumn |
| Burnt Orange | #D96C4F | WARM·autumn |
| Terracotta | #C2684E | WARM·autumn |
| Rust | #B5523A | WARM·autumn |
| Olive | #6B6B45 | WARM·autumn |
| Honey Brown | #C68642 | WARM·autumn |
| Taupe | #8F8577 | MUTED·soft autumn |
| Ivory | #F2E8D5 | NEUTRAL·spring/autumn |
| Beige | #D9C3A5 | NEUTRAL·spring/autumn |
| Brown | #6B4F3A | NEUTRAL·spring/autumn |

### ❄️ 겨울쿨 (Winter Cool) — COOL 차트 winter + NEUTRAL all/summer/winter/winter

| 색상 | hex | 출처 |
|------|-----|------|
| Royal Blue | #3F4F88 | COOL·winter |
| Cobalt | #2451B8 | COOL·winter |
| Sapphire | #185FB8 | COOL·winter |
| Ice Blue | #46A0AC | COOL·winter |
| Teal | #008080 | COOL·winter |
| Fuchsia | #C71F7E | COOL·winter |
| Magenta | #E63D63 | COOL·winter |
| True Red | #C71F37 | COOL·winter |
| Emerald | #008F5C | COOL·winter |
| Violet | #5C3A88 | COOL·winter |
| Black | #1E1E2E | NEUTRAL·all |
| Charcoal | #36454F | NEUTRAL·winter |
| Navy | #1B2444 | NEUTRAL·all |
| Denim | #4A6FA5 | NEUTRAL·all |
| Medium Gray | #808080 | NEUTRAL·summer/winter |
| Pure White | #FFFFFF | NEUTRAL·summer/winter |

---

## 4. 4시즌 × 4 카테고리 매핑

| 카테고리 | 🌸 봄웜 | ☁️ 여름쿨 | 🍂 가을웜 | ❄️ 겨울쿨 |
|----------|---------|-----------|-----------|-----------|
| **WARM** | ● Coral, Peach, Marigold | | ● Terracotta, Rust, Honey Brown | |
| **COOL** | | | | ● Royal Blue, Cobalt, Fuchsia |
| **NEUTRAL** | ● White, Cream | ● Gray, Beige | ● Brown, Beige | ● Black, Pure White, Charcoal |
| **MUTED** | | ● Dusty Rose, Mauve, Sage | ● Taupe, Stone | ● Lavender Gray, Soft Plum |

→ **4 시즌은 "어떤 카테고리에서 메인컬러를 가져올지" 가이드.**

---

## 5. 활용 시나리오

### 5.1. 채팅 에이전트
```
사용자: "나는 봄웜이야. 면접 코디 추천해줘"
에이전트: → season_bonus = spring 활성화
        → 봄웜 anchor: Coral, Peach, Marigold + Ivory, Beige, Brown
        → 면접 TPO → 무채색 베이스 + 봄웜 accent 1개
        → 추천: "Ivory 블라우스 + Brown 슬랙스 + Marigold 스카프/립"
        → 이유: "봄웜 anchor 3색 + NEUTRAL 2색, 룩 룰 L1~L5 통과"
```

### 5.2. 추구미 (PursuitMe) 시즌 선택
```
[사용자] 추구미 진입 → "내 퍼스널컬러는?" → 봄웜 선택
   → 봄웜 anchor 팔레트 8색 + 보색 풀 (WARM 카테고리 8색)
   → 17 tops × 12 pants 매트릭스에서 WARM 카테고리 가중치 +20%
   → top-K 추출
```

### 5.3. 옷장 RAG
```
[사용자] 옷장 사진 → 색상 추출
   → Wardrobe에서 Ivory, Brown, Black, Burgundy 추출됨
   → "이 옷장과 어울리는 봄웜 accent: Marigold, Coral 추천"
   → "이미 가진 Brown + 새 Coral 상의 = 가을웜 톤온톤, 봄웜에도 OK"
```

---

## 6. 주의사항

- **4시즌 ≠ hard rule**: 여름쿨이어도 Burgundy + Cream 룩은 가능. 카테고리 가중치일 뿐.
- **같은 시즌 내에서도 다름**: 봄웜 Bright vs Light는 명도 차이. 16 sub-type까지 세분화하면 더 정밀.
- **데이터 입력 우선**: 시즌 정보가 없으면 universal 룰로 폴백.
- **취향 우선**: `style_preferences.avoided_colors`가 시즌 anchor보다 우선.
