# SKN28-FINAL-1Team 데이터

LLM 기반 대화형 패션 추천 시스템에서 사용하는 데이터 분석 자료, 추천 규칙, 샘플 데이터와 데이터 처리 파이프라인을 모아 둔 폴더입니다.

## 폴더 구조

```text
data/
├── data_analysis/  # 데이터셋별 분석 README와 시각화 이미지
├── samples_data/   # 데이터셋별 최소 샘플 원본
├── docs/           # 설계서, 체크리스트, 데이터 목록 및 작성 지침
├── pipeline/       # 스캔·정제·임베딩·추천 룰 생성 파이프라인
├── color/          # 색상 조합 규칙
├── combination/    # 패션 아이템 조합 규칙
├── weather/        # 날씨별 코디 규칙
├── tpo/            # 상황(TPO)별 코디 규칙
├── style/          # 패션 스타일 정의
└── rag/            # RAG 구성 설정
```

## 데이터셋 분석 자료

`data_analysis/`에는 데이터셋별 분석 문서와 시각화 결과가 있습니다. 파일명 앞의 번호는 원본 데이터셋 번호입니다.

| 번호 | 데이터셋                  | 분석 문서        | 시각화                 |
| ---- | ------------------------- | ---------------- | ---------------------- |
| 03   | 패션상품 및 착용영상      | `03_README.md` | `03_artifact.jpg`    |
| 04   | H&M 추천 데이터           | `04_README.md` | `04_artifact.jpg`    |
| 05   | Polyvore Outfits          | `05_README.md` | `05_artifact.jpg`    |
| 10   | 한국인 3D 스캐닝          | `10_README.md` | `10_artifact.jpg`    |
| 11   | PoC 패션 코디             | `11_README.md` | `11_artifact.jpg`    |
| 12   | FASCODE                   | `12_README.md` | `12_artifact.jpg`    |
| 20   | 전신 형상 및 치수         | `20_README.md` | `20_artifact.jpg`    |
| 22   | 사이즈코리아              | `22_README.md` | `22_artifact.jpg`    |
| 23   | 공공데이터 의류·생활체육 | `23_README.md` | `23_artifact.jpg`    |
| 26   | K-Fashion                 | `26_README.md` | `26_artifact_A4.jpg` |

01 의류통합데이터는 현재 `samples_data/`에 샘플만 있으며, `data_analysis/`에는 별도 분석 문서나 아티팩트가 없습니다.

## 샘플 데이터

`samples_data/`에는 전체 원본을 저장하지 않고, 구조와 필드를 확인할 수 있는 최소 샘플만 보관합니다.

- 포함 데이터셋: 01, 03, 04, 05, 10, 11, 12, 20, 22, 23, 26
- 파일 형식: JPG, JSON, CSV, XLSX, OBJ, MTL 등
- 샘플 확인 안내: `samples_data/how_to_read_samples.md`
- 대용량 전체 데이터는 이 저장소가 아닌 원본 저장소 또는 S3에서 관리합니다.

## 추천 규칙과 RAG 설정

| 경로                                         | 용도                                   |
| -------------------------------------------- | -------------------------------------- |
| `color/color_matching_rules.json`          | 색상 간 조합 및 매칭 규칙              |
|  `combination/item_combination_rules.json` | 상·하의, 아우터 등 아이템 조합 규칙   |
| `weather/weather_outfit_rules.json`        | 기온, 비, 눈, 강풍에 따른 코디 규칙    |
| `tpo/tpo_outfit_rules.json`                | 출근, 면접, 데이트 등 상황별 코디 규칙 |
| `style/style_definitions.json`             | 스타일별 특징과 컬러 팔레트 정의       |
| `rag/rag_config.json`                      | RAG 데이터 구성 및 검색 설정           |

## 데이터 파이프라인

`pipeline/`은 다음 순서로 구성되어 있습니다.

1. `01_s3_scan.py` — S3 데이터 인벤토리 스캔
2. `02_clean_encoding.py`, `02_validate_json.py` — 데이터 정제 및 JSON 검증
3. `03_embed_pipeline.py` — 임베딩 생성 파이프라인
4. `04_build_weather_rules.py` — 날씨 추천 규칙 생성
5. `05_build_combination_rules.py` — 아이템 조합 규칙 생성

각 단계에는 설명 문서와 n8n 워크플로 JSON이 함께 있습니다. n8n 실행 환경은 `pipeline/n8n/`을 참고합니다.

## 문서

`docs/`에는 다음 자료가 있습니다.

- `Data_List.xlsx` — 데이터 목록
- `SKN28_1팀_데이터_조회_프로그램.docx` — 데이터 조회 프로그램 문서
- `기능설계.md`, `기능설계.png` — 기능 설계
- `_QA_CHECKLIST.md` — 품질 점검 항목
- `_SECURITY_REVIEW.md` — 보안 검토 내용
- `_README_RULES.md` — 데이터 분석 README 작성 규칙
- `_artifact_prompt_template.md` — 분석 아티팩트 작성 템플릿
- `_How_to_read_samples.md` — 샘플 데이터 확인 안내

## 관리 원칙

- 실제 자격증명, 액세스 키와 환경 변수 값은 저장하지 않습니다.
- `.claude`, 캐시, 체크포인트와 임시 파일은 `data/`에 포함하지 않습니다.
- 분석 자료는 `data_analysis/`, 원본 샘플은 `samples_data/`, 공통 문서는 `docs/`에 분리합니다.
- JSON을 수정한 뒤에는 `pipeline/02_validate_json.py` 또는 `jq`로 구문을 검증합니다.
