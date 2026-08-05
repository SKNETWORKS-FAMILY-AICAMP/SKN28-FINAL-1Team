# PROGRESS

## 2026-08-03 현재 대화 세션 정리

### 1. 현재 Codex 대화 세션

- 세션 ID: `019fc599-d140-78e0-9241-aa4ea89e306d`
- 세션 파일:

```text
C:\Users\Playdata\.codex\sessions\2026\08\03\rollout-2026-08-03T12-10-20-019fc599-d140-78e0-9241-aa4ea89e306d.jsonl
```

- 세션 저장 폴더:

```text
C:\Users\Playdata\.codex\sessions\2026\08\03
```

### 2. 기존 진행 문서 위치

루트에는 `PROGRESS.md`가 없었고, 기존 진행 문서는 아래 위치에 있었다.

```text
C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\local\docs\PROGRESS.md
```

이번 정리는 사용자가 요청한 루트 위치에 새로 작성했다.

```text
C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\PROGRESS.md
```

### 3. 이번 세션에서 정리한 핵심 작업

#### 테스트셋 기준 정리

- 기본 모델과 Hugging Face 모델이 같은 테스트셋으로 비교되도록 `test_set.csv`를 공통 기준으로 사용하게 했다.
- `test_set.csv`에는 `source_row_id`를 포함해 같은 1000개 행인지 검증할 수 있게 했다.
- Colab 실행 시 `--test-data test_set.csv`를 사용하도록 했다.

#### 헷갈리는 파일 정리

- 더 이상 사용하지 않도록 정리한 파일:

```text
validation_set.csv
validation_predictions_*.csv
test_set_모델명.csv
```

- 앞으로 기준 파일:

```text
test_set.csv
test_predictions_모델명.csv
metrics.json
run_manifest.json
```

#### 기본 모델 4개 복구

기존 기본 모델 4개 중 빠져 있던 `baseline`을 복구했다.

현재 기본 모델:

```text
baseline
random_forest
hist_gradient_boosting
knn
```

생성 확인한 CSV:

```text
test_set.csv                                1000행
test_predictions_baseline.csv               1000행
test_predictions_random_forest.csv          1000행
test_predictions_hist_gradient_boosting.csv 1000행
test_predictions_knn.csv                    1000행
```

#### Hugging Face/Colab 기준

Colab에는 아래 4개 파일을 올리면 된다.

```text
benchmark.py
huggingface_benchmark.ipynb
sizekorea_measurements_clean.csv
test_set.csv
```

로컬 위치:

```text
ml/body_measurement/src/benchmark.py
ml/body_measurement/src/huggingface_benchmark.ipynb
ml/body_measurement/data/processed/sizekorea_measurements_clean.csv
ml/body_measurement/artifacts/classic/test_set.csv
```

Colab 실행 후 확인할 파일:

```text
test_predictions_tabpfn_v2.csv
test_predictions_nori.csv
test_predictions_tabpfn_mix.csv
```

### 4. 수정/생성한 주요 파일

```text
ml/body_measurement/src/benchmark.py
ml/body_measurement/src/huggingface_benchmark.ipynb
ml/body_measurement/src/compare_all_models.py
ml/body_measurement/README.md
ml/body_measurement/requirements.txt
ml/body_measurement/artifacts/classic/test_set.csv
ml/body_measurement/artifacts/classic/test_predictions_baseline.csv
ml/body_measurement/artifacts/classic/test_predictions_random_forest.csv
ml/body_measurement/artifacts/classic/test_predictions_hist_gradient_boosting.csv
ml/body_measurement/artifacts/classic/test_predictions_knn.csv
ml/body_measurement/reports/model_comparison_summary.csv
ml/body_measurement/reports/model_comparison_detail.csv
ml/body_measurement/reports/model_comparison.png
```

### 5. 현재 주의사항

- `test_set.csv`는 기본 모델과 HF 모델 비교의 공통 시험지다.
- 모델별로 봐야 하는 파일은 `test_predictions_모델명.csv`다.
- `validation_*` 파일은 더 이상 사용하지 않는다.
- `test_set_모델명.csv`도 중복이라 더 이상 만들지 않는다.

## 2026-08-04 사진 기반 신체치수 추정 API 모델 테스트 계획

### 1. 목적

- Gemini API와 OpenRouter API를 같은 조건에서 비교한다.
- 모델마다 최종 테스트셋 예측 파일을 별도로 보존한다.
- 사람이 사진, 예측값, 실제값, 오차를 직접 확인할 수 있는 검토 보고서를 만든다.

### 2. 데이터 분할

| 구분 | 비율 | 182명 기준 | 용도 |
|---|---:|---:|---|
| 검토용 | 20% | 약 36명 | 사진·예측·오차를 사람이 확인하고 프롬프트/오류 점검 |
| 최종 테스트 | 80% | 약 146명 | 모델 성능의 공정한 비교 |

- 분할은 성별·키·몸무게 분포를 고려하고 고정 시드로 재현 가능하게 만든다.
- 실제 신체 치수는 모델 입력에 넣지 않으며, 예측 후 오차 계산에만 사용한다.
- 생성 기준 파일: `data/splits/review_20.csv`, `data/splits/test_80.csv`

### 3. 공통 모델 조건

- 입력: 정면 사진 1장, 측면 사진 1장, 성별, 키, 몸무게
- 이미지: 긴 변 960px JPEG
- 출력: 가슴·허리·엉덩이 예측값 JSON
- 설정: `temperature=0`, 이미지 생성·검색·RAG 미사용
- 모든 후보 모델에 같은 프롬프트와 같은 JSON 형식을 사용한다.

### 4. 구현 예정 파일

```text
ml/body_measurement/
├─ scripts/
│  ├─ split_dataset.py
│  ├─ run_gemini.py
│  ├─ run_openrouter.py
│  ├─ evaluate_results.py
│  └─ make_review_report.py
├─ prompts/
│  └─ body_measurement_prompt.txt
└─ results/
```

### 5. 실행 순서

1. Gemini 3.5 Flash-Lite를 검토용 20%에 실행하여 요청·JSON·이상값·응답 시간을 점검한다.
2. Gemini를 최종 테스트 80%에 실행한다.
3. Qwen 3.7 Flash를 같은 최종 테스트 80%에 실행한다.
4. Kimi K2.5와 Grok 4.3은 우선 검토용 20%로 비용과 정확도를 확인한 뒤, 기준을 만족하면 최종 테스트 80%로 확대한다.
5. 결과를 모델별 파일과 종합 요약 파일로 저장한다.

### 6. 결과 파일 규칙

```text
results/
└─ <model_name>/
   ├─ review_20_predictions.csv
   ├─ test_80_predictions.csv
   ├─ test_80_evaluated.csv
   ├─ test_80_failures.csv
   ├─ review_20_visual_report.html
   └─ run_metadata.json
```

- 예측 파일에는 `subject_id`, 이미지 경로, 예측값, 지연 시간, 토큰, 추정 비용, 상태, 원본 응답을 남긴다.
- 평가 파일에는 실제값과 부위별 절대오차를 추가한다.
- 종합 파일은 `results/model_benchmark_summary.csv`로 만든다.

### 7. API 역할

- `GEMINI_API_KEY`: Gemini 3.5 Flash-Lite 직접 호출
- `OPENROUTER_API_KEY`: Qwen 3.7 Flash, Kimi K2.5, Grok 4.3 호출
- Gemini를 두 API에서 중복 호출하지 않는다.
- AWS GPU는 현재 API 테스트에 필요 없고, 추후 오픈웨이트 모델 직접 운영에만 사용한다.

## 2026-08-04 신체치수 추정 API 2종 구현 완료

### 1. 무엇을 만들었나

| API | 방식 | 입력 | 출력 |
|---|---|---|---|
| `POST /api/v1/users/me/body/estimate/` (신규) | 동기 200 | 성별·키·몸무게 | 상세 7개 |
| `POST /api/v1/users/me/body/photos/` (기존 껍데기 → 실제 연결) | 비동기 202 + 폴링 | 성별·키·몸무게 + 사진 2장 | 상세 7개 |
| `GET /api/v1/users/me/body/photos/{tx_id}/` | 조회 | — | 상세 7개 + 상태/실패사유 |

- 성별·키·몸무게는 두 API 모두 생략 가능하다. 생략하면 저장된 기본 신체치수를 쓴다.

### 2. Response 통일 방식

POST 껍데기는 동기(200)/비동기(202)라 같게 만들 수 없어 **결과 payload를 통일**했다.
`POST /body/estimate/`와 `GET /body/photos/{tx_id}/`가 아래 형태를 공유한다.

```json
{
  "status": "succeeded",
  "source": "basic_info | photo",
  "transaction_id": null,
  "measurement": { "gender": "male", "height": "175.5", "weight": "70.0",
                   "chest": "98.7", "waist": "83.8", "hip": "94.0",
                   "thigh": "55.2", "calf": "37.3", "arm": "32.0",
                   "shoulder": "40.3", "updated_at": "..." },
  "error_message": null
}
```

### 3. 7개 vs 3개 갭 해결

- 무사진 모델(hist_gradient_boosting)은 7개를 전부 예측한다.
- 사진 모델(VLM)은 초기 모델 성능 비교에서는 비용을 아끼려고 가슴·허리·엉덩이
  3개만 예측했다.
- **결정(2026-08-04 갱신)**: 사진 VLM에게도 **7개를 전부** 물어본다. 3개만 물었던 건
  모델 선정 벤치마크에서 비용을 아끼려던 조치였고 제품 요구사항이 아니었다.
  기본 정보 추정으로 7개를 먼저 채운 뒤 VLM 응답으로 덮어쓴다 (VLM이 일부를
  빠뜨려도 빈칸이 생기지 않는다).
- **2026-08-05 복구**: SizeKorea 개별 `*_profile.csv` 원본에는
  `thigh/calf/arm/shoulder` 정답이 있었으므로 `data/labels/sizekorea_vlm_182_labels.csv`,
  `data/labels/sizekorea_vlm_subjects.csv`, `data/splits/vlm/*_set.csv`에 7개 정답을 복구했다.
  Kimi K2.5 full 테스트/검증 결과도 7개 부위 MAE를 다시 계산했다.
- 서빙 프롬프트는 `body_measurement_prompt_full.j2`(7개), 벤치마크 프롬프트는
  기존 `body_measurement_prompt.j2`(3개)로 분리했다. 기록된 MAE를 재현할 수 있게
  벤치마크 쪽은 건드리지 않았다.
- 상세 값은 덮어쓴다. 추정 후 사용자가 `PATCH /body/detail/`로 고치는 흐름이다.

### 4. 트러블슈팅

| 문제 | 원인 | 해결 |
|---|---|---|
| `hist_gradient_boosting.joblib` 로드 불가 (`ModuleNotFoundError: _loss`) | sklearn 1.8.0으로 저장 → 1.9.0에서 언피클 | 실행 환경을 1.8.0으로 고정 (`api/requirements.txt`) |
| 배포 시 모델 파일 없음 | `.gitignore`의 `*.joblib` (루트 + ml 하위 2곳) | 예외 규칙 추가해 커밋 가능하게 변경 |
| 백그라운드에서 사진 접근 불가 | 업로드 파일이 응답 후 사라지는데 `start_measurement(tx_id)`만 넘김 | 접수 시 바이트로 읽어 스레드에 전달하도록 시그니처 변경 |
| 실패 사유를 프론트가 알 수 없음 | 트랜잭션에 상태만 있고 사유 컬럼 없음 | `BodyPhotoTransaction.error_message` 추가 (마이그레이션 0012) |
| sqlite로 테스트 불가 | `catalog` 앱이 Postgres 전용 ArrayField/GinIndex 사용 | Postgres(docker compose db)로 테스트 |

### 5. 검증 결과

- `manage.py test apps.users` — **63개 전부 통과** (Postgres)
- 무사진 추정 종단 확인: `male 175.5cm 70kg` → 7개 전부 반환, 200
- 사진 추정 종단 확인: SizeKorea 샘플 기준 7개 전부 반환, 200

### 6. 남은 일

- [ ] 사진 모델 최종 확정 (Qwen 3.7 Flash 기본값 / Kimi K2.5는 정확도 1위·비용 30배)
- [x] 선택한 모델로 Test 154명 최종 평가 (Kimi K2.5, 2026-08-04)
- [ ] 백그라운드 스레드 → Celery/SQS 교체 (AWS 이관 시)
- [ ] 프론트 연동 확인

## 2026-08-05 데이터셋 정책 확정 + 도커 서빙 종단 시연

### 1. 데이터셋 정책 — SizeKorea만 사용

최종 평가·학습 데이터는 **SizeKorea 실측만** 쓴다. 비-SizeKorea 외부 데이터는
동일한 실측 기준으로 검증되지 않았기 때문에 최종 기준에서 제외한다.

- 비-SizeKorea 외부 이미지, 라벨 행, split 행, VLM 실험 CSV 행은 삭제했다.
- Test 기준은 SizeKorea 145명이다. 정답오류 2건 제외 시 **143명 3.126cm**다.
- Validation 기준은 SizeKorea 36명이다.
- SizeKorea-only 기준 split 비율은 Test 145명(80.11%) / Validation 36명(19.89%)로 유지된다.
- 근거와 상세 표는 `reports/model_evaluation_summary.md` §5-3 참조

### 2. 도커 서빙 환경 결함 3건 수정

`97d23a9`(API 2종 구현)은 로컬에서만 검증됐고 **도커에서 한 번도 빌드된 적이 없었다.**
그래서 컨테이너 이미지가 7/29에 멈춰 있었고 `/body/estimate/`가 404였다.
Swagger 캐시 문제가 아니라 이미지가 낡은 것이 원인이었다.

| # | 증상 | 원인 | 수정 |
|---|---|---|---|
| 1 | 컨테이너에 `OPENROUTER_API_KEY` 없음 | compose의 api 서비스에 변수 선언 자체가 없어 shell env가 전달되지 않음 | `docker-compose.yml` api에 `OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}` 추가. 값은 파일에 두지 않고 `infisical run`으로 주입 |
| 2 | 이미지 빌드 실패 | `scipy==1.18.0`은 Python 3.12+ 요구, api 이미지는 `python:3.11-slim` | `api/requirements.txt` 핀을 실제 검증 환경 값(scipy 1.17.1 / numpy 2.4.3)으로 정정 |
| 3 | `ModuleNotFoundError: body_measurement` | 빌드 컨텍스트가 `./api`라 이미지에 `ml/`이 없음 | compose의 `migrate`·`api`에 `- ./ml:/ml:ro` 마운트 (settings/base.py가 `BASE_DIR.parent/ml`을 sys.path에 올림) |

실행 명령 (인증 우회 + 키 주입):

```bash
infisical run --env=dev --silent -- sh -c \
  'DJANGO_SETTINGS_MODULE=config.settings.swagger_noauth docker compose --profile api up -d --build api'
```

Infisical 시크릿이 shell 변수를 덮어쓰므로 `DJANGO_SETTINGS_MODULE` 지정은
`infisical run` **안쪽**에서 해야 한다.

### 3. HTTP 종단 시연 결과 (실제 OpenRouter 호출)

`POST /body/photos/` → 202 + tx_id → `GET /body/photos/{tx_id}/` 폴링 → succeeded까지
정상 완주했다. 추론 함수 직접 호출이 아닌 **진짜 HTTP 경로로는 처음** 성공했다.

여성·남성 각 1건씩 실제 호출했고 **2건 모두 7개 부위를 전부 반환**했다.
정답 7개가 복구돼 있어 3개 기준과 7개 기준을 함께 계산했다.

| 대상 | 3개 무사진 | 3개 사진 | 7개 무사진 | 7개 사진 | 우세 |
|---|----:|----:|----:|----:|---|
| `sizkorea_f111` (여, 164.1cm 59.3kg) | **0.667** | 3.600 | **0.800** | 2.986 | 무사진 |
| `sizkorea_m095` (남, 172.8cm 65.8kg) | 3.933 | **2.833** | 3.000 | **1.729** | 사진 |

1승 1패라 우열을 말할 수 없다. **이번 시연의 목적은 기능 검증이지 성능 비교가
아니며**, 성능 판단은 표본 전체 평균으로만 해야 한다.

관찰된 공통 패턴 하나: **두 건 모두 엉덩이 오차가 가장 컸다**
(f111 사진 4.9 / m095 사진 7.0, 무사진도 각각 0.5 / 6.1). Test 145명 집계에서
엉덩이가 가장 낮은 MAE(2.643)를 보인 것과 방향이 다르므로, 단건 관찰로 일반화하지 않는다.

### 4. VLM 응답 비결정성 관측

`temperature=0`인데도 같은 사진·같은 입력의 응답이 8/4 배치와 달라졌다.

| 대상 | 8/4 배치와 일치한 부위 |
|---|---|
| `sizkorea_f111` | 0 / 7 (전부 다름, MAE 1.17 → 3.60) |
| `sizkorea_m095` | 2 / 7 (`waist`, `thigh`만 동일) |

단건으로 모델 성능을 판단하면 안 되며, 재현이 필요한 벤치마크는 응답을 CSV로
남겨 대조해야 한다.

### 5. 기능 검증 (2026-08-05, 무료 검증만)

| 항목 | 결과 |
|---|---|
| `apps.users` 테스트 (dev 설정) | 65개 통과 |
| `apps.api_docs` 테스트 (swagger 설정) | 2개 통과 |
| 정상 경로 6개 엔드포인트 | 전부 200/202 |
| 에러 처리 (없는 tx / 범위초과 / 성별오타 / 사진누락 / 필드명오류) | 404 1건 + 400 4건, 전부 의도대로 |
| Swagger 스키마 노출 | body 6개 전부 |
| 응답 스키마 통일 | `POST /body/estimate/` ↔ `GET /body/photos/{tx}/` 완전 동일 |

`GET /body/`·`PUT /body/basic/`·`PATCH /body/detail/`는 `measurement` 알맹이만
반환하고, 추정 계열 2개는 `{status, source, transaction_id, measurement,
error_message}`로 감싼다. 감싼 형태는 비동기·실패 표현이 필요해서이며,
`measurement` 내부 11개 필드는 5개 API가 모두 동일하다
(프론트는 `res.measurement ?? res`로 통일 가능).

### 6. 남은 일

- [ ] 시연 후 `DJANGO_SETTINGS_MODULE`을 `prod`로 원복 (현재 인증 우회 상태)
- [ ] 백그라운드 스레드 → Celery/SQS 교체 (AWS 이관 시)
- [ ] 프론트 연동 확인
