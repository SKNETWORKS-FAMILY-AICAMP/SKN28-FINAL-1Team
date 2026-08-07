# 04-combination-rules.md — 조합 룰 (Main + Complementary 5 + Muted/Tonal 2)

## 1. Michael 84 차트 패턴

```
행 = Main Color
열 = [Main | Complementary1 | Complementary2 | Complementary3 | Complementary4 | Complementary5 | Muted1 | Muted2]
    = 1 메인 + 5 보색 + 2 뮤트/토널 = 8 스왓치
```

## 2. 룰 정의

### R1: Complementary는 다른 카테고리에서 차용
- WARM 메인 → Complementary는 COOL, NEUTRAL에서
- COOL 메인 → Complementary는 WARM, NEUTRAL에서
- NEUTRAL 메인 → Complementary는 WARM, COOL에서
- MUTED 메인 → Complementary는 WARM, COOL, NEUTRAL에서 (보색 다양)

### R2: Muted/Tonal은 같은 카테고리 내
- WARM 메인 → Muted/Tonal은 다른 WARM 메인 (e.g., Coral → Mauve는 어색, → 다른 WARM 메인)
- MUTED 메인 → Muted/Tonal은 다른 MUTED 메인

### R3: 공통 룰 (5개)
- 모든 조합에 **Black** 또는 **Pure White** 또는 **Gray** 최소 1개 포함
- 같은 카테고리 메인끼리는 보색보다 단조로움 (WARM 메인 + WARM 보색 → 약함)
- 명도 차이 18+ 권장 (R1 from v2)
- 한쪽 채도 ≥ 45면 보색이라도 caution (R3 from v2)
- 웜·쿨 혼합은 뉴트럴로 분리 (R6 from v2)

### R4: 특별 케이스
- Black, Charcoal, Pure White → 모든 메인과 매칭 가능 (universal)
- Denim → COOL 메인이랑 특히 잘 맞음 (universal cool)

## 3. 매칭 예시

### WARM 메인: Coral
- **Complementary 5**: Black, Pure White, Gray, Beige, Navy
  - Black (NEUTRAL): 보색 대비
  - Pure White (NEUTRAL): 명도 대비
  - Gray (NEUTRAL): 채도 완충
  - Beige (NEUTRAL): 톤인톤
  - Navy (NEUTRAL): 컬러 휠 보색
- **Muted/Tonal 2**: Dusty Rose (MUTED), Mauve (MUTED)
  - Dusty Rose: 채도 낮춘 coral 변형
  - Mauve: 채도 낮춘 purple-pink

### NEUTRAL 메인: Black
- **Complementary 5**: Pure White, Gray, Charcoal, Beige, Coral
  - Pure White: 최고 명도 대비
  - Gray: 톤인톤
  - Charcoal: 톤인톤 (lighter)
  - Beige: 따뜻한 보색
  - Coral: 따뜻한 포인트
- **Muted/Tonal 2**: Charcoal, Dark Gray
  - Black의 muted 변형 없음 → 톤 변형만

## 4. 데이터 참조

- 카테고리 정의: `rules/category_palettes.json`
- 매칭 룰: `rules/combination_matches.json`
- v2 grade map (참고): `rules/color_rules.json`, `rules/color_matrix.md`
