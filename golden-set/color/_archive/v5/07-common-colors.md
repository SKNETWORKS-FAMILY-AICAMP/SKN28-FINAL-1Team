# 07-common-colors.md — 데이터 기반 자주 쓰는 색상 (v6)

## 1. v5 → v6 핵심 변화

| | v5 | v6 |
|---|---|---|
| 팬츠 팔레트 | 8-10개 메인 (이론) | **8 필수 + 4 추가 = 12 pants** (실사용) |
| 상의 팔레트 | 시즌 무관 동일 | **시즌별 undertone 분리** |
| 임계값 | (없음) | **5% 등장 또는 사용자 필수** |
| 검증 | 이론만 | **CJ Logistics + 지그재그 데이터** |

## 2. 최종 12 Pants 팔레트

### 필수 8 (사용자 지정)
| # | 색 | hex | 비고 |
|---|----|-----|------|
| 1 | Denim | #4A6FA5 | 청바지, 60%+ jeans 시장 |
| 2 | White | #FFFFFF | 15% 의류, 2위 |
| 3 | Black | #1E1E2E | 32-38% 1위 |
| 4 | Beige | #D9C3A5 | 23% 지그재그 2위 |
| 5 | Ivory | #F2E8D5 | Beige 변형 |
| 6 | Brown | #6B4F3A | Brown 패밀리 |
| 7 | Khaki | #8B7355 | 카고 팬츠 |
| 8 | Navy | #1B2444 | 남성 정장 |

### 추가 4 (10%+ 등장 + 트렌드)
| # | 색 | hex | 비고 |
|---|----|-----|------|
| 9 | Medium Gray | #808080 | 무신사 베스트 1위 Gray Sweats |
| 10 | Light Denim | #A0BCD8 | 여름 청바지 |
| 11 | Dark Denim | #2C3E50 | 겨울 청바지 |
| 12 | Olive | #6B6B45 | 545%↑ 검색량 (매경) |

## 3. Tops (시즌별)

### 3.1. All-Season (Universal)
- **Black** (#1E1E2E) — 32-38%
- **Navy** (#1B2444) — 5-10%
- **Pure White** (#FFFFFF) — summer/winter, 15-30%
- **Ivory** (#F2E8D5) — spring/autumn, 10-15%
- **Medium Gray** (#808080) — summer/winter, 9%
- **Beige** (#D9C3A5) — spring/autumn, 23%

### 3.2. Spring/Autumn 추가
- **Camel** (#C19A6B) — autumn
- **Mustard** (#D4A017) — 양 시즌
- **Olive** (#6B6B45) — autumn
- **Tobacco Brown** (#A78867) — autumn
- **Burgundy** (#7A1F4F) — autumn/winter
- **Rust** (#B5523A) — autumn
- **Coral** (#FF6F61) — spring

### 3.3. Summer/Winter 추가
- **Charcoal** (#36454F) — winter
- **Light Blue** (#ADD8E6) — summer
- **Lavender** (#B57EDC) — summer
- **Blush Pink** (#FFB6C1) — summer
- **Cobalt** (#2451B8) — winter
- **Royal Blue** (#3F4F8B) — winter
- **Fuchsia** (#C71F7E) — winter
- **Forest Green** (#2E5E4E) — winter
- **True Red** (#C71F37) — winter

## 4. 매칭 우선순위

상위 카테고리 메인 → 5 complementary 우선순위:
1. **8 필수 pants** (Denim/White/Black/Beige/Ivory/Brown/Khaki/Navy)
2. **추가 4 pants** (Gray/Light Denim/Dark Denim/Olive)
3. **카테고리 cross-over** (warm 메인 → cool/neutral complementary)

## 5. 데이터 출처 명시

- CJ Logistics 2021 Everyday Life Report (배송 데이터)
- 지그재그 2023 결산 (판매 데이터)
- 무신사 베스트 랭킹 (1위 색상)
- 매경 2024 패션 색상 검색량 추이
- 한국 표준 15색 선호도 조사 (KS)

상세: `rules/real_world_palette.json`
