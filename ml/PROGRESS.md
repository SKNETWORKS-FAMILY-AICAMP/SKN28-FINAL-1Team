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
ml/body_measurement/data/sizekorea_measurements_clean.csv
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
