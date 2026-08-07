# 02-personal-color.md — 퍼스널컬러 4시즌 (참고용)

> ⚠️ **중요**: 퍼스널컬러는 **참고용 reference**임. v5의 주축은 **4 카테고리 (Warm/Cool/Neutral/Muted)**. 같은 시즌이라고만 매칭하지 않음.

## 1. 4시즌 개요

| 시즌 | 한글 | 베이스 | 무드 | 대표색 |
|------|------|--------|------|--------|
| Spring | 🌸 봄웜 | Yellow 베이스 | 상쾌, 활기 | 코랄, 크림옐로, 연두, 민트 |
| Summer | ☁️ 여름쿨 | Blue 베이스 | 차분, 맑음 | 미스트블루, 로즈베이지, 라벤더 |
| Autumn | 🍂 가을웜 | Gold 베이스 | 깊이, 빈티지 | 카라멜브라운, 벽돌, 올리브 |
| Winter | ❄️ 겨울쿨 | Blue-Purple 베이스 | 시크, 럭셔리 | 트루레드, 로열블루, 순백 |

## 2. 16 Sub-types (확장)

각 시즌은 4개 sub-type으로 나뉨 (총 16):

| Season | Sub-types |
|--------|-----------|
| Spring | Bright / Light / Warm / Clear |
| Summer | Light / Bright / Muted / Cool |
| Autumn | Soft / Warm / Deep / Muted |
| Winter | Bright / Cool / Deep / Clear |

자세한 hex 코드는 `rules/personal_color_palettes.json` 참조.

## 3. v5에서 퍼스널컬러 활용 방식

- **매칭 강제 아님**: "봄웜 사용자 → 봄웜 색상만" 같은 hard rule 없음
- **참고용**: `season_bonus` 가중치 계산에 활용
- **메인컬러 매핑**: 시즌별 anchor 색은 4 카테고리 어디에 속하는지 참고

예시:
- 봄웜 Coral (#FF6F61) → WARM 카테고리 메인
- 여름쿨 Dusty Rose (#C9869A) → MUTED 카테고리 메인
- 가을웜 Terracotta (#C26B4E) → WARM 카테고리 메인
- 겨울쿨 Royal Blue (#3F4F8B) → COOL 카테고리 메인

## 4. 4 시즌 × 4 카테고리 매핑

| 카테고리 | 봄웜 | 여름쿨 | 가을웜 | 겨울쿨 |
|----------|------|--------|--------|--------|
| WARM | ● Coral, Peach, Marigold | | ● Terracotta, Rust, Honey Brown | |
| COOL | | | | ● Royal Blue, Cobalt, Fuchsia |
| NEUTRAL | ● White, Cream | ● Gray, Beige | ● Brown, Beige | ● Black, Pure White, Charcoal |
| MUTED | | ● Dusty Rose, Mauve, Sage | ● Taupe, Stone | ● Lavender Gray, Soft Plum |

→ 4 시즌은 **"어떤 카테고리에서 메인컬러를 가져올지"** 가이드.
