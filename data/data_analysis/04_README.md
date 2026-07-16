# 04_HM_추천데이터 (HM Personalized Fashion Recommendations)

## §1 요약 (Summary)

H&M 개인화 패션 추천 시스템을 위한 제품 카탈로그 데이터셋이다. S3 실제 조사 결과, **articles.csv 1개 파일**(36.1 MB, 105,542건)과 **상품 이미지 105,100개**(29.1 GB)로 구성되어 있다. CSV는 H&M의 패션 아이템(의류, 액세서리 등)Metadata를 담고 있으며, 이미지는 각 article_id에 대응하는 JPG 상품 사진이다.

| 항목 | 값 |
|------|-----|
| 데이터 포맷 | CSV (articles.csv) + JPG 이미지 |
| article 레코드 수 | 105,542건 (헤더 제외) |
| 이미지 파일 수 | 105,100개 |
| CSV 크기 | 36,127,865 bytes (~36.1 MB) |
| 이미지 총 크기 | 30,557,038,537 bytes (~29.1 GB) |
| 전체 합계 | 105,101개 오브젝트, ~29.2 GB |

---

## §2 데이터 구조 상세 (Data Structure)

### 폴더 구조

```
s3://skn28-cozy/4_HM_Personalized_Fashion_Recommendations/
├── articles.csv                    (36.1 MB)
└── images/
    ├── 010/  (0108775015.jpg ~)
    ├── 011/  (0110065001.jpg ~)
    ├── 012/
    ├── 013/
    ... (010 ~ 095_prefix 디렉토리, 총 105,100개 이미지)
```

### 파일 목록 (비이미지 파일)

| S3 Key | 크기 (bytes) |
|--------|-------------|
| 4_HM_Personalized_Fashion_Recommendations/articles.csv | 36,127,865 |

### articles.csv 스키마 (24개 컬럼)

| # | 컬럼명 | 설명 | 예시값 |
|---|--------|------|--------|
| 1 | `article_id` | 상품 고유 ID (10자리) | 0108775015 |
| 2 | `product_code` | 상품 코드 (7자리) | 0108775 |
| 3 | `prod_name` | 상품명 | Strap top |
| 4 | `product_type_no` | 상품 유형 번호 | 253 |
| 5 | `product_type_name` | 상품 유형명 | Vest top |
| 6 | `product_group_name` | 상품 그룹명 | Garment Upper body |
| 7 | `graphical_appearance_no` | 그래픽Appearance 번호 | 1010016 |
| 8 | `graphical_appearance_name` | 그래픽Appearance 명 | Solid |
| 9 | `colour_group_code` | 색상 그룹 코드 | 09 |
| 10 | `colour_group_name` | 색상 그룹명 | Black |
| 11 | `perceived_colour_value_id` | 인지 색상값 ID | 4 |
| 12 | `perceived_colour_value_name` | 인지 색상값 명 | Dark |
| 13 | `perceived_colour_master_id` | 인지 주색상 ID | 5 |
| 14 | `perceived_colour_master_name` | 인지 주색상 명 | Black |
| 15 | `department_no` | 부서 번호 | 1676 |
| 16 | `department_name` | 부서명 | Jersey Basic |
| 17 | `index_code` | 인덱스 코드 | A |
| 18 | `index_name` | 인덱스명 (고객 세그먼트) | Ladieswear |
| 19 | `index_group_no` | 인덱스 그룹 번호 | 1 |
| 20 | `index_group_name` | 인덱스 그룹명 | Ladieswear |
| 21 | `section_no` | 섹션 번호 | 1002 |
| 22 | `section_name` | 섹션명 | Jersey Basic |
| 23 | `garment_group_no` | 의류 그룹 번호 | 1002 |
| 24 | `garment_group_name` | 의류 그룹명 | Jersey Basic |
| 25 | `detail_desc` | 상세 설명 | Jersey top with narrow shoulder straps... |

### 주요 통계 (articles.csv 기반)

**index_name (고객 세그먼트) 분포:**
| 세그먼트 | 건수 |
|---------|------|
| Ladieswear | 26,001 |
| Divided | 15,149 |
| Menswear | 12,553 |
| Children Sizes 92-140 | 12,007 |
| Children Sizes 134-170 | 9,214 |
| Baby Sizes 50-98 | 8,875 |
| Ladies Accessories | 6,961 |
| Lingeries/Tights | 6,775 |
| Children Accessories | 4,615 |
| Sport | 3,392 |

**product_type_name 상위 10:**
| 유형 | 건수 |
|------|------|
| Trousers | 11,169 |
| Dress | 10,362 |
| Sweater | 9,302 |
| T-shirt | 7,904 |
| Top | 4,155 |
| Blouse | 3,979 |
| Jacket | 3,940 |
| Shorts | 3,939 |
| Shirt | 3,405 |
| Vest top | 2,991 |

### 샘플 레코드 (실제 데이터)

```csv
article_id,product_code,prod_name,product_type_no,product_type_name,product_group_name,graphical_appearance_no,graphical_appearance_name,colour_group_code,colour_group_name,perceived_colour_value_id,perceived_colour_value_name,perceived_colour_master_id,perceived_colour_master_name,department_no,department_name,index_code,index_name,index_group_no,index_group_name,section_no,section_name,garment_group_no,garment_group_name,detail_desc
0108775015,0108775,Strap top,253,Vest top,Garment Upper body,1010016,Solid,09,Black,4,Dark,5,Black,1676,Jersey Basic,A,Ladieswear,1,Ladieswear,16,Womens Everyday Basics,1002,Jersey Basic,Jersey top with narrow shoulder straps.
0110065001,0110065,OP T-shirt (Idro),306,Bra,Underwear,1010016,Solid,09,Black,4,Dark,5,Black,1339,Clean Lingerie,B,Lingeries/Tights,1,Ladieswear,61,Womens Lingerie,1017,"Under-, Nightwear","Microfibre T-shirt bra with underwired, moulded, lightly padded cups..."
```

---

## §3 추천 시스템 활용 방안 (Recommendation Use Cases)

1. **아이템 기반 협업 필터링 (Item-based CF)**
   - article_id를 아이템 고유키로 활용, 상품 유형/색상/그래픽Appearance 등의 피처 벡터를 구성하여 유사 아이템 추천에 활용 가능

2. **콘텐츠 기반 추천 (Content-Based Recommendation)**
   - `product_type_name`, `colour_group_name`, `graphical_appearance_name`, `detail_desc`(텍스트) 등을 활용하여 사용자 구매 이력 기반 유사 스타일 아이템 추천
   - 텍스트 임베딩(detail_desc)으로 아이템 설명 기반 유사도 계산 가능

3. **범주 기반 추천 (Category-Based)**
   - `index_name`(Ladieswear/Menswear/Baby 등)으로 사용자 세그먼트별 추천
   - `product_group_name`, `section_name`으로 상위/하위 범주 계층 추천 가능

4. **멀티모달 추천 (Vision + Metadata)**
   - 105,100개 상품 이미지(H&M 상품 사진)와 CSV 메타데이터를 결합
   - 이미지 CLIP 임베딩 + 텍스트 메타데이터 임베딩으로 멀티모달 추천 시스템 구축 가능

5. **Cold-Start 아이템 추천**
   - 새 상품 등록 시 product_type, colour, department, section 등의 피처를 활용하여 기존 사용자 취향에 매핑

---

## §4 출처 (Source)

- **S3 경로**: `s3://skn28-cozy/4_HM_Personalized_Fashion_Recommendations/`
- **Confluence**: pages/9797646
- **수집일**: 2026-07-06
- **분석 기준**: AWS CLI `--profile team`, `s3 ls --recursive` + `s3api list-objects-v2` 실측 결과
