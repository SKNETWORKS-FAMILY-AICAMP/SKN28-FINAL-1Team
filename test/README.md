# 세그멘테이션 모델 후보 비교 테스트

옷장 등록 기능(사진 → 아이템 분리 → 특징 추출)의 세그멘테이션 모델 3후보를
같은 사진·같은 특징 추출기로 비교한다.

## 구조

```
test/
├── common/
│   ├── taxonomy.py           # Confluence 카테고리-태그 매핑 문서의 enum (한글 라벨 ↔ 영어 프롬프트)
│   ├── feature_extractor.py  # Marqo-FashionSigLIP 제로샷 특징 추출 (공통)
│   └── pipeline.py           # 마스크 정리 → 흰 배경 크롭 → 특징 추출 → 저장 (공통)
├── test_segformer.py             # 후보 1: SegFormer clothes (경량, semantic)
├── test_yolov8_deepfashion2.py   # 후보 2: YOLOv8-seg + DeepFashion2 (instance, 가중치 필요)
└── test_grounded_sam2.py         # 후보 3: Grounding DINO + SAM2 (open-vocab, 품질 상한)
```

세 테스트의 차이는 `segment()` 뿐이고 후처리·특징 추출은 동일 — 세그멘테이션 품질만 비교된다.

## 실행

```bash
cd test
pip install -r requirements.txt

python test_segformer.py sample.jpg
python test_grounded_sam2.py sample.jpg
python test_yolov8_deepfashion2.py sample.jpg --weights df2_yolov8.pt  # 가중치 별도 준비
```

- `DEVICE=cuda|cpu` 환경변수로 디바이스 지정 (기본: cuda 가능 시 cuda)
- 첫 실행은 HF/ultralytics 모델 다운로드로 오래 걸림. latency 비교는 2회차부터.

## 출력

`output/<모델명>/<이미지명>/`:

- `item_XX_<대분류>.png` — 아이템별 흰 배경 크롭
- `_overlay.jpg` — 검출 시각화
- `items.json` — 아이템별 특징(Confluence 스키마) + 세그 메타 + 단계별 latency

특징 스키마 예 (`items.json`의 각 항목):

```json
{
  "item_name": "화이트 오버핏 반팔 티셔츠",
  "category_large": "상의", "category_small": "티셔츠",
  "season": ["여름"], "style": ["캐주얼", "베이직"],
  "color": "화이트", "pattern": "무지", "fit": "오버핏",
  "material": "코튼", "sleeve": "반팔", "length": "기본",
  "usage": ["데일리", "외출"], "layer_role": "기본 상의", "layer_order": 1,
  "_confidence": {"category_small": 0.91, "...": "제로샷 확률"},
  "_seg": {"model": "...", "raw_label": "...", "score": 0.87, "bbox": [..]}
}
```

## 특징 추출 방식 (공통)

- **시각 판별 필드**(category, color, pattern, fit, material, sleeve, length, style):
  FashionSigLIP 제로샷 분류. 배열 필드(color/style)는 확률 임계값 이상 top-2.
- **규칙 유도 필드**: `season`(소분류·소매·소재 → 규칙), `layer_role/order`(카테고리 → 규칙).
- **판별 불가 필드**: `usage`는 기본값 `["데일리","외출"]` — 사진만으로 알 수 없어
  이후 Vision LLM 태깅 또는 사용자 입력으로 보정하는 것을 전제.

## 비교 체크리스트

| 항목 | 확인 방법 |
|---|---|
| 아이템 분리 정확도 (누락·오검출) | `_overlay.jpg`, `num_items` |
| 마스크 경계 품질 (흰 배경 합성) | `item_XX_*.png` 육안 비교 |
| 레이어드 착장 분리 (재킷 속 이너) | 레이어드 사진으로 테스트 |
| latency | `items.json`의 `timings_sec` (warm 기준) |
| 특징 추출 정확도 | 동일 크롭이라도 마스크 품질에 따라 달라짐 — `_confidence` 비교 |

## 알려진 제약

- **SegFormer**: semantic 방식 — 같은 클래스 2벌 분리 불가(connected component로 근사),
  상의/아우터 구분 없음(Upper-clothes 단일 클래스 → SigLIP이 대분류 재판별).
- **YOLOv8+DF2**: 신발·가방·모자 클래스 없음(의류 13종만). 공식 가중치 없어 별도 준비.
- **Grounded SAM2**: 모델 2개 로드로 무겁고 콜드 스타트 김. threshold 튜닝 필요.
