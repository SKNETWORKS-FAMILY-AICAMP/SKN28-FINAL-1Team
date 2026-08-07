# 실사용 색상 데이터 리서치

## 1. 리서치 목적

이론적 색상 분류(퍼스널컬러 4시즌, 4 카테고리)만으로는 실제 시장에서 통하는 팔레트를 만들 수 없다. **실제 한국 소비자가 자주 구매하는 색상**을 데이터로 검증해서 팔레트를 구성한다.

## 2. 데이터 소스

| 소스 | 유형 | 핵심 결과 |
|------|------|-----------|
| **CJ Logistics 2021 Everyday Life Report** | 배송 데이터 (전체 의류) | Black 38%, White 15%, Gray 9% = 무채색 62% |
| **지그재그 2023 결산** | 판매 데이터 (1년) | Black 32%, Beige 23%, Gray 7%, White 7%, Blue 5% |
| **KS 표준 15색 선호도 조사** | 선호도 설문 | Blue 36%, Black 29%, Yellow 28%, Green 28% |
| **아이스타일24 2024 무채색 트렌드** | 판매 데이터 | 무채색 +43%, Black 티셔츠 +103% |
| **무신사 베스트 1위 아이템** | 랭킹 1위 색상 | Gray Sweats Pants 1위, Gray Crop T-Shirt 베스트 |
| **매경 (2024)** | 검색량 추이 | Olive 545%↑, Mint 380%↑, Violet 162%↑ |

## 3. 핵심 발견

### 3.1. 무채색 압도
- 의류 전체의 **62%+가 무채색** (Black + White + Gray)
- Black이 모든 카테고리에서 1위 (30-38%)
- White가 2위 (15-30%)
- Gray가 3위 (9%)

### 3.2. Beige/Sand 류 강세
- 지그재그 23% = 2위
- 슬랙스(베이지 계열) 판매 1위
- Beige + Ivory + Khaki = "earth tone" 카테고리 30%+

### 3.3. Denim 별도 카테고리
- 의류 전체에선 5%지만
- **팬츠 한정으론 60%+가 청바지**
- 옅은/중간/진한 3가지 shade 모두

### 3.4. 70% 임계값 비현실적
- 실제 데이터 최고치: **Black 38%**
- 70% 넘는 색상 = **0개**
- → 임계값을 **5% 이상 등장 또는 사용자 필수**로 완화

## 4. 8 필수 pants (사용자 지정)

옷장 기본 베이스로 무조건 포함:
1. **Denim** (청바지) — #4A6FA5
2. **White** (흰색) — #FFFFFF
3. **Black** (검정) — #1E1E2E
4. **Beige** (베이지) — #D9C3A5
5. **Ivory** (아이보리) — #F2E8D5
6. **Brown** (브라운) — #6B4F3A
7. **Khaki** (카키) — #8B7355
8. **Navy** (네이비) — #1B2444

이 8개는 빈도 무관하게 모든 매칭 룰에서 우선순위.

## 5. 시즌별 색상 처리 (Top)

같은 색이라도 시즌에 따라 다른 undertone:

| 색 | Summer/Winter (쿨) | Spring/Autumn (웜) |
|----|---------------------|---------------------|
| White | Pure White #FFFFFF | Ivory #F2E8D5 |
| Gray | Light/Charcoal (cool) | Taupe/Mushroom (warm) |
| Beige | Taupe #8F8377 | Beige #D9C3A5 |
| Cream | Soft White #F2F3F5 | Cream #F5E6CC |
| Brown | Taupe | Brown/Camel |
| Light Blue | #ADD8E6 | Light Sky #A8D8EA |
| Pink | Dusty Rose / Blush | Coral / Warm Pink |
| Olive | Sage / Eucalyptus | Olive #6B6B45 |
| Burgundy | #7A1F4F (cool) | Wine Red #7A2E2E (warm) |

→ **8 필수 pants는 시즌 무관하게 동일, tops는 시즌별 undertone 분리**

## 6. 데이터 → 팔레트 매핑

주요 변경:
- 필수 pants 8 (사용자 지정) 추가
- 70% 임계값 → 5% 등장 또는 필수
- Tops에 시즌별 undertone 분리 적용
- Denim = 별도 카테고리 (LIGHT/MEDIUM/DARK 3 shade)

## 7. 한계

- **배송 데이터**: 색상 분류가 판매자 라벨에 의존 → 부정확 가능
- **결산 보고서**: 카테고리별 분리 미흡 (전체 vs pants vs tops)
- **KS 15색**: 15색 한정 → 세분류 부족
- **검색량 vs 판매량**: 검색 ≠ 실제 구매 (다름)

## 8. 후속 작업

1. **카테고리별 세분화**: pants / tops / outer 각각 100개 카운트
2. **시즌별 데이터**: 봄/여름/가을/겨울 베스트 아이템
3. **가격대별**: 저가/중가/고가 선호 색상
4. **브랜드별**: 무신사/지그재그/29cm 차이
