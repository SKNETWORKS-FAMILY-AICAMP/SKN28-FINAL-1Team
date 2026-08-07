# 08. Pinterest 색조합 참고 (Real-world Color Combinations)

> 작성일: 2026-08-07
> 출처: Pinterest 검색 "옷 색 조합" (https://kr.pinterest.com/search/pins/?q=옷 색 조합)
> 목적: v6 데이터 기반 12 pants × 17 tops 시스템에 Pinterest에서 자주 등장하는 색조합을 cross-reference로 추가

---

## 1. Pinterest 검색 결과 Top 7 색조합

검색어 "옷 색 조합"으로 Pinterest를 조회했을 때, 1페이지에 노출된 7개 핀에서 추출한 색조합 인사이트입니다.

| # | 핀 제목 키워드 | 메인 조합 | 카테고리 | 우리 시스템 매핑 |
|---|----------------|-----------|----------|------------------|
| 1 | **Tie Colour Guide** (Korean Capsule Wardrobe) | Navy + Burgundy + Forest + Olive + Brown | Classic | Navy + Burgundy (Cool/Neutral) |
| 2 | **Teal Color Match Clothes** (Chocomint) | Teal + Brown | Cool/Warm bridge | Teal + Brown (Cool) |
| 3 | **Universal Wear Matching Formula** | 7×7 universal grid | Theory | 4 카테고리 (Warm/Cool/Neutral/Muted) |
| 4 | **Korean Color Combos** (Romwe aesthetic) | Pink + White + Brown + Beige | Soft aesthetic | Blush + Cream + Brown (Muted) |
| 5 | **Red White Brown Outfit** (Aesthetic) | Red + White + Brown | Warm/Classic | Burgundy + White + Brown (Warm) |
| 6 | **Best Color Combo (Blue + Khaki)** | Blue + Khaki + Beige | Universal | Denim + Khaki + Beige (Neutral) |
| 7 | **Brown Matching Colors** (Maroon) | Brown + Maroon + Mahogany | Tonal | Brown + Burgundy (Muted) |

---

## 2. 6대 핵심 색조합 인사이트

### 2.1 Tonal (Brown family) — 가장 많이 등장
- **Brown + Maroon + Mahogany** + Cream
- **Brown + Beige + Ivory** (한 톤 안에서 단계별)
- 우리 시스템: Brown t-shirt → Brown/Beige/Ivory pants (모두 tonal OK)
- 4 카테고리 매핑: **Muted** (Brown 베이스)

### 2.2 Universal Classic (Blue + Earth)
- **Denim + Khaki + Beige + White** (남녀노소 가능한 무난한 조합)
- 우리 시스템: Denim pants → 12 tops 중 8개 호환
- 4 카테고리 매핑: **Neutral** (모든 톤 OK)

### 2.3 Korean Aesthetic (Pink + Cream)
- **Blush Pink + Cream + White + Beige** (소녀 감성, Romwe 인기)
- 우리 시스템: Blush Pink t-shirt → Cream/Ivory/Beige pants (best)
- 4 카테고리 매핑: **Muted** (부드러운 톤)

### 2.4 Chocomint (Teal + Brown)
- **Teal + Brown** + Cream (2024-2025 SNS 핫 트렌드)
- 우리 시스템: Teal t-shirt → Brown/Beige/Khaki pants
- 4 카테고리 매핑: **Cool → Warm bridge** (Teal은 cool이지만 brown이 warm이라 양쪽 다 OK)

### 2.5 Red Aesthetic (Burgundy + Brown)
- **Burgundy + White + Brown** (Red/White/Brown Romwe)
- 우리 시스템: Burgundy t-shirt → Beige/Brown/Cream pants
- 4 카테고리 매핑: **Warm → Muted** (Burgundy는 warm deep, brown이 muted)

### 2.6 Tie Formal (Navy + Burgundy)
- **Navy + Burgundy + Forest + Olive + Brown** (정장/넥타이 매칭)
- 우리 시스템: Navy t-shirt → Burgundy/Forest/Olive/Brown pants
- 4 카테고리 매핑: **Cool/Warm bridge** (정통 매칭)

---

## 3. v6 시스템과의 교차 검증

Pinterest 인기 색조합을 우리 12 pants × 17 tops에 대입했을 때, **이미 대부분 커버**되고 있음이 확인됩니다.

| Pinterest 조합 | 우리 12 pants 중 best match | 우리 17 tops 중 best match | 카테고리 |
|----------------|----------------------------|---------------------------|----------|
| Teal + Brown | Brown, Khaki | Teal | Cool |
| Pink + Cream | Cream, Ivory | Blush Pink | Muted |
| Blue + Khaki | Denim, Khaki | Navy, Light Blue | Neutral |
| Brown + Maroon | Brown, Khaki | Burgundy, Rust | Warm/Muted |
| Red + White + Brown | White, Brown, Beige | Burgundy, Mustard, Rust | Warm |
| Navy + Burgundy | Navy, Charcoal | Burgundy | Cool |
| Olive + Brown | Olive, Khaki | Olive, Brown | Muted |

→ **데이터 + Pinterest 모두에서 같은 결론**: Brown family tonal, Universal Blue/Khaki, Korean Pink/Cream이 가장 안전.

---

## 4. v6 outfit 그리드와의 관계

`outfits/v6_grids/outfit_v6_*.png` 17장은 다음 Pinterest 인사이트를 prompt에 반영했습니다:

1. **"Pinterest minimal fashion catalog"** 스타일 (검색 결과의 미니멀 톤)
2. **white background + soft natural light** (한국 Pinterest 미니멀 룩)
3. **flat-lay top-down view** (e-commerce catalog 스타일)
4. **12 pants 모두 cover** (universal formula의 7×7 매트릭스 정신 반영)
5. **t-shirt + chinos 조합** (Romwe/Korean aesthetic Pinterest의 일상적 조합)

### 향후 확장 아이디어 (v7 후보)
- v6: 17 tops × 12 pants = 204 조합 (현재 17장 = top별 시트)
- v7 후보: Pinterest가 강조한 6대 카테고리별 top3 outfit 추천 (총 18장)
- 추가 candidate: Brown family tonal 시리즈 (3가지 톤 Brown, Beige, Khaki) 별도 6장

---

## 5. 참고 자료

- **Pinterest 검색 URL**: https://kr.pinterest.com/search/pins/?q=옷 색 조합
- **로컬 Pinterest 이미지**: `assets/references/` 폴더 (0.jpg ~ 9.jpg + Pinterest ref1~3)
- **Michael 84 chart (Pinterest ref1)**: Main + 5 Comp + 2 Muted
- **Colorimetría (Pinterest ref2)**: Denim shade 가이드
- **Universal 7×7 (Pinterest ref3)**: 보편적 조합 매트릭스

---

_이 문서는 v6 데이터 기반 색조합 시스템에 Pinterest 시장 트렌드를 cross-reference로 추가한 자료입니다._
