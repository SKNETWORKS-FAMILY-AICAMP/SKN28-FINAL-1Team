# 05-use-cases.md — 활용 시나리오

## 1. 추천 API 입력값

```json
{
  "user_id": 123,
  "personal_color_season": "autumn",   // spring/summer/autumn/winter (선택)
  "body_type": "apple",                  // apple/pear/hourglass/rectangle/inverted_triangle
  "tpo": "casual",                       // casual/business/formal/sport
  "preferred_categories": ["warm", "neutral"],  // 사용자가 선호하는 카테고리
  "occasion": "weekend brunch"           // 자유 입력
}
```

## 2. 추천 결과 (Top-K)

```json
{
  "user_id": 123,
  "recommendations": [
    {
      "rank": 1,
      "top": {"name": "Terracotta", "hex": "#C26B4E", "category": "warm"},
      "bottom": {"name": "Cream", "hex": "#F5E6CC", "category": "neutral"},
      "score": 0.92,
      "reasons": [
        "autumn season affinity (warm × warm-leaning)",
        "terracotta + cream: high lightness contrast (L:45 vs L:91)",
        "neutral cream balances warm terracotta"
      ]
    },
    {
      "rank": 2,
      "top": {"name": "Olive", "hex": "#6B6B45", "category": "warm"},
      "bottom": {"name": "Black", "hex": "#1E1E2E", "category": "neutral"},
      "score": 0.88,
      ...
    }
  ]
}
```

## 3. UI 활용

### 3.1. 차트 미리보기
- 카테고리별 Michael 84 차트 표시
- "이 색과 어울리는 8가지" 한눈에

### 3.2. outfit 이미지 갤러리
- 사용자 시즌 × 추천 조합 → flat-lay 이미지
- "이렇게 매치해보세요" 시각 가이드

### 3.3. 색상 팔레트
- 사용자 시즌에 맞는 4 카테고리별 메인컬러 팔레트
- "당신의 WARM 팔레트는 8가지입니다"

## 4. 활용처

| 활용처 | 입력 | 출력 |
|--------|------|------|
| **추천 API** | user context | top-10 코디 추천 |
| **카탈로그 UI** | 상품 ID | "이 상품과 어울리는 5가지" |
| **스타일 가이드 PDF** | 시즌 | 차트 + outfit 갤러리 |
| **옷장 정리 도우미** | 보유 옷 리스트 | "이 옷이 안 어울려요" |

## 5. 확장 가능성

- **체형 매핑**: `body_shape_thresholds.json` + `body_fit_rules.json` (v2에서 작성)
- **TPO 필터**: 비즈니스/캐주얼별 톤 규칙
- **시즌성**: 봄/여름/가을/겨울 옷장 분리 추천
- **가격대**: 예산별 추천 (저가/중가/고가)
