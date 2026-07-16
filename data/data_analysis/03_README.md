# 03 패션 상품 및 착용 영상 데이터

## §1 요약 (Summary)

`s3://skn28-cozy/03_패션 상품 및 착용 영상/`은 패션 상품 단독 촬영 이미지와 모델 착용 이미지를 제공하는 2D 이미지 + JSON 라벨 데이터셋이다.

핵심 파일은 `winfo_train.json` (~15.8MB)과 `winfo_val.json` (~4.3MB)로, 모델 착용 이미지와 상품 ID를 직접 연결하는 착장 정보다. `winfo_train.json`은 86,380건, `winfo_val.json`은 23,420건의 착장 조합을 담고 있다.

전체 S3 파일 수는 약 **331,108개** (JSON 라벨 + JPG 이미지)로, Training이 대다수를 차지한다.

| 구분 | Item-Image | Item-Parse | Item-Pose | Model-Image | Model-Parse | Model-Pose | winfo |
|------|-----------|------------|-----------|-------------|-------------|------------|-------|
| Training | 27,814 | 27,814 | 27,814 | 86,380 | 86,380 | 86,380 | 1 |
| Validation | 7,822 | 7,822 | 7,820 | 23,420 | 23,420 | 23,420 | 1 |

추천 시스템 활용: 착장 조합 빈도 분석, 상품 co-occurrence 매트릭스, 카테고리 정규화, 부위별 색상 추출, 멀티모달 이미지 임베딩 구축에 직접 활용 가능.

---

## §2 데이터 구조 상세 (Data Structure)

### 2.1 S3 폴더 구조

```
s3://skn28-cozy/03_패션 상품 및 착용 영상/
└── 01.데이터/
    ├── 1.Training/
    │   ├── 라벨링데이터_230515_add/
    │   │   └── 2021_Fashion_train_labels_v230428/
    │   │       ├── Item-Parse/       (27,814 JSON)
    │   │       ├── Item-Pose/        (27,814 JSON)
    │   │       ├── Model-Parse/      (86,380 JSON)
    │   │       ├── Model-Pose/       (86,380 JSON)
    │   │       └── winfo_train.json  (15,837,992 bytes)
    │   └── 원천데이터_230515_add/
    │       ├── 2021_Fashion_train_itemimages_v230428/
    │       │   └── Item-Image/       (27,814 JPG)
    │       └── 2021_Fashion_train_modelimages_v230428/
    │           └── Model-Image/      (86,380 JPG)
    └── 2.Validation/
        ├── 라벨링데이터/                           (original, Item only)
        │   └── 2021_Fashion_val_labels/
        │       ├── Item-Parse/       (7,822 JSON)
        │       └── Item-Pose/        (7,820 JSON)
        ├── 라벨링데이터_230515_add/
        │   └── 2021_Fashion_val_labels_v230428/
        │       ├── Item-Parse/       (7,822 JSON)
        │       ├── Item-Pose/        (7,820 JSON)
        │       ├── Model-Parse/      (23,420 JSON)
        │       ├── Model-Pose/       (23,420 JSON)
        │       └── winfo_val.json    (4,296,867 bytes)
        ├── 원천데이터/                              (original source)
        │   └── 2021_Fashion_val_images/
        │       ├── Item-Image/       (7,822 JPG)
        │       └── Model-Image/     (23,420 JPG)
        └── 원천데이터_230515_add/
            └── 2021_Fashion_val_images_v230428/
                ├── Item-Image/       (7,822 JPG)
                └── Model-Image/     (23,420 JPG)
```

### 2.2 S3 실측 증거 (S3 Evidence)

S3 API (`list-objects-v2`) 실측 기반:

```
Training 라벨 (라벨링데이터_230515_add):
  Item-Parse:  27,814 files  (2021_Fashion_train_labels_v230428/Item-Parse/)
  Item-Pose:   27,814 files  (2021_Fashion_train_labels_v230428/Item-Pose/)
  Model-Parse: 86,380 files  (2021_Fashion_train_labels_v230428/Model-Parse/)
  Model-Pose:  86,380 files  (2021_Fashion_train_labels_v230428/Model-Pose/)
  winfo_train.json: 15,837,992 bytes

Training 이미지 (원천데이터_230515_add):
  Item-Image:  27,814 files  (2021_Fashion_train_itemimages_v230428/Item-Image/)
  Model-Image: 86,380 files  (2021_Fashion_train_modelimages_v230428/Model-Image/)

Validation 라벨 (라벨링데이터_230515_add):
  Item-Parse:   7,822 files  (2021_Fashion_val_labels_v230428/Item-Parse/)
  Item-Pose:    7,820 files  (2021_Fashion_val_labels_v230428/Item-Pose/)
  Model-Parse: 23,420 files  (2021_Fashion_val_labels_v230428/Model-Parse/)
  Model-Pose:  23,420 files  (2021_Fashion_val_labels_v230428/Model-Pose/)
  winfo_val.json: 4,296,867 bytes

Validation 이미지 (원천데이터_230515_add):
  Item-Image:   7,822 files  (2021_Fashion_val_images_v230428/Item-Image/)
  Model-Image: 23,420 files  (2021_Fashion_val_images_v230428/Model-Image/)
```

참고: Validation 라벨링데이터 (original, `_add` 없음)의 Item-Parse/Item-Pose는 라벨링데이터_230515_add와 동일한 7,822/7,820건. 2023-05-15 추가분은 Model-Parse, Model-Pose, winfo만 신규 추가.

### 2.3 파일명 규칙

**Item (상품 단독 이미지):**
```
{상품ID}_{B|F}.jpg   예: 1008011_F.jpg, 1008011_B.jpg
{상품ID}_{B|F}.Item-Parse.json
{상품ID}_{B|F}.Item-Pose.json
```
`B` = back (뒷면), `F` = front (앞면). Item-Parse, Item-Pose JSON 파일명과 1:1 대응.

**Model (모델 착용 이미지):**
```
{상품그룹ID}_{모델세트ID}_{각도}.jpg   예: 1008_A001_000.jpg
{상품그룹ID}_{모델세트ID}_{각도}.Model-Parse.json
{상품그룹ID}_{모델세트ID}_{각도}.Model-Pose.json
```
같은 `상품그룹ID_모델세트ID` 조합을 여러 각도(000, 044, 065, 085, ...)에서 촬영.

### 2.4 JSON 라벨 구조

**Item-Pose** (`category_name` 예: tops, bottoms, cap_and_hat):
```json
{
  "num_keypoints": 8,
  "category_id": 2,
  "category_name": "tops",
  "image_size": {"width": ..., "height": ...},
  "landmarks": [...]
}
```

**Item-Parse** (`region` 예: torso, rsleeve, lsleeve, top_hidden):
```json
{
  "region1": {"category_id": ..., "product_type": "torso", "segmentation": [[x,y],...]},
  "region2": {"category_id": ..., "product_type": "rsleeve", "segmentation": [[x,y],...]},
  ...
}
```
`segmentation`은 polygon 좌표 배열 `[[x1,y1],[x2,y2],...]`.

**Model-Pose** (COCO 17-keypoint 표준):
```json
{
  "num_keypoints": 17,
  "category_name": "human",
  "landmarks": [...]
}
```

**Model-Parse** (`region` 예: hair, hat, face, neck, inner_torso, pants_hip, right_leg, left_leg):
```json
{
  "hair": {"category_id": ..., "segmentation": [[x,y],...]},
  "hat": {...},
  "face": {...},
  "inner_torso": {...},
  "pants_hip": {...},
  "right_leg": {...},
  ...
}
```

### 2.5 핵심: winfo (착장 연결 정보)

`winfo_train.json`과 `winfo_val.json`은 모델 착용 이미지와 상품 ID를 1:1 연결한다.

```json
{
  "wearing": "1008_A001_000.jpg",
  "hat": "1008013",
  "main_top": "1008011",
  "inner_top": null,
  "bottom": "1008012",
  "shoes": null
}
```

`shoes`와 `inner_top`은 필요 시만 사용 (null 허용). Training의 86,380개 Model-Image가 winfo_train.json의 86,380개 entry에 1:1 대응.

### 2.6 파일 크기 범위

| 파일 타입 | 크기 범위 |
|---------|---------|
| Model-Parse JSON | ~76KB–134KB |
| Model-Pose JSON | ~1.1KB–1.4KB |
| Item-Parse JSON | ~5KB–35KB |
| Item-Pose JSON | ~1KB–1.5KB |
| winfo_train.json | 15,837,992 bytes (~15.1MB) |
| winfo_val.json | 4,296,867 bytes (~4.1MB) |
| Model-Image JPG | ~200KB–400KB (증감 추이) |
| Item-Image JPG | (미측정) |

### 2.7 데이터 Split 요약

| Split | Item 수 | Model-Image 수 | winfo 수 |
|-------|--------|--------------|---------|
| Training | 27,814 | 86,380 | 1 (train) |
| Validation | 7,822 | 23,420 | 1 (val) |
| **합계** | **35,636** | **109,800** | **2** |

Model-Image:Item 비율 = Training 3.1:1, Validation 3.0:1 (1개 상품에 평균 ~3개 각도 이미지).

---

## §3 추천 시스템 활용 방안 (Recommendation System Use Cases)

### 3.1 착장 조합 빈도 분석

`winfo_train.json`과 `winfo_val.json`의 착장 조합을 바로 추천 데이터로 활용.

**상의-하의 빈도 쿼리:**
```sql
SELECT main_top, bottom, COUNT(*) AS cnt
FROM outfits
WHERE main_top IS NOT NULL AND bottom IS NOT NULL
GROUP BY main_top, bottom
ORDER BY cnt DESC;
```

**특정 상품의 코디 파트너 빈도:**
```sql
SELECT
  CASE WHEN hat = 'TARGET' THEN 'hat'
       WHEN main_top = 'TARGET' THEN 'main_top'
       WHEN bottom = 'TARGET' THEN 'bottom'
       WHEN shoes = 'TARGET' THEN 'shoes' END AS slot,
  COUNT(*) AS cnt
FROM outfits
WHERE 'TARGET' IN (hat, main_top, inner_top, bottom, shoes)
GROUP BY slot;
```

### 3.2 상품 Co-occurrence 매트릭스 구축

`winfo`에서 모든 상품 페어를 추출하여 동시 출현 매트릭스를 만들고, "이 옷과 함께 많이 입는 옷" 추천에 활용.

### 3.3 카테고리 정규화 기준

`Item-Pose.category_name`에 `tops`, `bottoms`, `cap_and_hat` 등 카테고리가 정의되어 있다. 크롤링 데이터나 사용자 옷장의 카테고리를 이 체계로 매핑하는 기준 데이터로 활용.

### 3.4 부위별 색상/패턴 추출

`Model-Parse`의 polygon 영역을 이미지에 적용하면 상품별 대표 색상을 자동 태깅 가능.

```python
# 예: Model-Parse에서 상의 영역만 추출
region = parse_json["inner_torso"]["segmentation"]  # polygon 좌표
mask = polygon_to_mask(region, image_size)
color_mean = extract_mean_color(image, mask)
```

### 3.5 멀티모달 임베딩

Item-Image와 Model-Image를 CLIP 등 비전 모델로 임베딩하면 "이런 느낌으로 입고 싶다" 이미지 검색, 또는 RAG 파이프라인 활용 가능.

### 3.6 pose 기반 필터링

`Model-Pose` 17 keypoint로 전신/상반신 판별 및 자세 분류 가능. 추천 결과 화면에 보여줄 착용샷을 적절히 선별하는 데 활용.

---

## §4 출처 (Sources)

- **S3 버킷:** `s3://skn28-cozy`
- **S3 경로:** `03_패션 상품 및 착용 영상/`
- **Confluence:** https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/11993134

### S3 폴더 경로 (실측)

```
s3://skn28-cozy/03_패션 상품 및 착용 영상/01.데이터/
  1.Training/
    라벨링데이터_230515_add/2021_Fashion_train_labels_v230428/
      Item-Parse/       → 27,814 JSON
      Item-Pose/        → 27,814 JSON
      Model-Parse/      → 86,380 JSON
      Model-Pose/       → 86,380 JSON
      winfo_train.json
    원천데이터_230515_add/
      2021_Fashion_train_itemimages_v230428/Item-Image/  → 27,814 JPG
      2021_Fashion_train_modelimages_v230428/Model-Image/ → 86,380 JPG
  2.Validation/
    라벨링데이터/2021_Fashion_val_labels/
      Item-Parse/       → 7,822 JSON
      Item-Pose/        → 7,820 JSON
    라벨링데이터_230515_add/2021_Fashion_val_labels_v230428/
      Item-Parse/       → 7,822 JSON
      Item-Pose/        → 7,820 JSON
      Model-Parse/      → 23,420 JSON
      Model-Pose/       → 23,420 JSON
      winfo_val.json
    원천데이터/2021_Fashion_val_images/
      Item-Image/       → 7,822 JPG
      Model-Image/      → 23,420 JPG
    원천데이터_230515_add/2021_Fashion_val_images_v230428/
      Item-Image/       → 7,822 JPG
      Model-Image/      → 23,420 JPG
```

### 확인 방법 (AWS CLI)

```powershell
# 전체 구조 확인
aws --profile team s3 ls "s3://skn28-cozy/03_패션 상품 및 착용 영상/" --recursive

# 특정 폴더 파일 수 확인
aws --profile team s3api list-objects-v2 --bucket skn28-cozy --prefix "03_패션 상품 및 착용 영상/01.데이터/1.Training/라벨링데이터_230515_add/2021_Fashion_train_labels_v230428/Model-Parse/" --max-items 100000 | ConvertFrom-Json | Select-Object -ExpandProperty Contents | Measure-Object
```
