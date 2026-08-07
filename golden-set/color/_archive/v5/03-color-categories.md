# 03-color-categories.md — 4 카테고리 정의

## 1. 카테고리 분류 체계

```
                    ┌─ WARM (웜) ─────── 봄웜 + 가을웜
                    │                  Yellow/Orange 베이스
                    │
4 categories ──────┼─ COOL (쿨) ─────── 여름쿨 + 겨울쿨
                    │                  Blue/Violet 베이스
                    │
                    ├─ NEUTRAL (뉴트럴) ─ 무채색 + 어스톤
                    │                  모든 시즌 공통 베이스
                    │
                    └─ MUTED (뮤트) ──── 저채도 + 그레이시드
                                       Soft Summer/Autumn 계열
```

## 2. 카테고리별 특성

| 카테고리 | 언더톤 | 채도 | 명도 | 무드 |
|----------|--------|------|------|------|
| **WARM** | yellow/orange | 중-고 | 중 | 생기, 따뜻, 활기 |
| **COOL** | blue/violet | 중-고 | 중 | 시크, 차분, 럭셔리 |
| **NEUTRAL** | neutral | 저-중 | 다양 | 안정, 균형, 베이스 |
| **MUTED** | neutral-cool, low chroma | 저 | 중-저 | 차분, 부드러움, 로맨틱 |

## 3. 카테고리별 메인컬러 (8-10개씩)

### WARM (웜)
Coral, Light Coral, Peach, Marigold, Mustard, Burnt Orange, Terracotta, Rust, Olive, Honey Brown

### COOL (쿨)
Royal Blue, Cobalt, Sapphire, Ice Blue, Teal, Fuchsia, Magenta, True Red, Emerald, Violet

### NEUTRAL (뉴트럴)
Black, Charcoal, Navy, Gray, Pure White, Cream, Beige, Brown, Ivory, Denim

### MUTED (뮤트)
Dusty Rose, Mauve, Soft Rose, Sage, Eucalyptus, Taupe, Stone, Mushroom, Soft Plum, Lavender Gray

상세 hex: `rules/category_palettes.json`

## 4. 카테고리 간 보색 관계

```
        WARM ←→ COOL      (보색)
        WARM ←→ NEUTRAL   (보색 - 뉴트럴은 모든 카테고리의 앵커)
        WARM ←→ MUTED     (보색 - 채도 차이)
        COOL ←→ NEUTRAL   (보색)
        COOL ←→ MUTED     (유사색 - 같은 cool 베이스)
        NEUTRAL ←→ MUTED  (대비 - 무채색 vs 그레이시드)
```

→ 한 카테고리의 메인컬러는 **다른 카테고리에서 complementary**를 가져옴.
→ MUTED는 같은 카테고리 내에서 muted/tonal 변형으로 등장.
