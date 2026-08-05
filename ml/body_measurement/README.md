# 신체치수 모델 비교 도구

키와 몸무게로 상세 신체치수 7개를 예측하는 모델을 동일한 데이터 분할과
지표로 비교한다.

## 폴더 구조

```text
body_measurement/
├── data/
│   ├── processed/
│   │   └── sizekorea_measurements_clean.csv   ← SizeKorea 정제본 (실제 사용)
│   └── raw/
│       └── sizekorea_8th.xlsx            ← SizeKorea 8차 원본 (재정제용)
├── src/
│   ├── benchmark.py                       ← 메인 벤치마크 CLI
│   ├── compare_all_models.py              ← 7모델 비교 리포트 생성
│   ├── benchmark_vlm.py                   ← VLM 벤치마크
│   ├── benchmark_openrouter_two_view.py   ← OpenRouter 2-view 벤치마크
│   ├── inference.py                       ← API 서빙용 추론 헬퍼
│   └── huggingface_benchmark.ipynb        ← Colab GPU에서 HF 모델 실행
├── artifacts/models/                      ← API 서빙용 joblib 모델
├── experiments/                           ← 모델별·실행별 평가 결과
│   ├── tabular/<model>/<run_name>/
│   └── vlm/<model>/<run_name>/
├── reports/                               ← 비교 리포트
│   ├── model_comparison_report.md         ← 사람이 보는 7모델 비교 보고서
│   ├── model_comparison_summary.csv       ← 모델별 평균 지표
│   ├── model_comparison_detail.csv        ← target별 상세 지표
│   └── model_comparison.png               ← R2/MAE/RMSE 차트
├── __init__.py
├── requirements.txt
├── README.md
└── .gitignore
```

## 비교 모델

기본 설치:

1. `DummyRegressor(strategy="mean")` — baseline
2. `RandomForestRegressor`
3. `HistGradientBoostingRegressor`
4. `KNeighborsRegressor`

선택 설치 (GPU/외부 의존성 필요):

5. `Prior-Labs/TabPFN-v2-reg`
6. `Synthefy/Nori`
7. `autogluon/tabpfn-mix-1.0-regressor`

Hugging Face 후보는 모델 다운로드, 큰 의존성, 라이선스 검토가 필요하므로
기본 설치에서 제외했다.

## 데이터 형식

정제 CSV에 다음 컬럼이 필요하다.

```text
gender,height,weight,chest,waist,hip,thigh,calf,arm,shoulder
```

- `gender`: M/F
- `height`: cm
- `weight`: kg
- 나머지 target: cm
- 결측 행은 현재 MVP에서 제외한다.
- 실제 평가에서는 동일 조사 대상이 train/test에 중복되지 않도록 전처리
  단계에서 subject 기준 split 컬럼을 추가하는 방향으로 확장한다.

VLM 이미지 평가용 SizeKorea 요약 CSV는
`data/raw_test_data/summary_raw_test_data.csv`에 있다. 이 파일은
개별 `*_profile.csv` 원본을 하나로 묶은 결과이며
`chest/waist/hip/thigh/calf/arm/shoulder` 7개 실측값을 보존한다.

## 설치

```powershell
python -m venv .venv-ml
.\.venv-ml\Scripts\Activate.ps1
pip install -r ml\body_measurement\requirements.txt
```

## 실행 위치

모든 명령은 `ml\body_measurement\` 폴더에서 실행한다고 가정한다.
다른 위치에서 실행하면 상대 경로가 깨질 수 있다.

```powershell
cd ml\body_measurement
```

## 배선 확인

실제 데이터가 없을 때 기본 4개 모델의 학습·저장·예측 흐름만 확인한다.
이 결과는 실제 신체치수나 모델 성능으로 해석하면 안 된다.

```powershell
python src\benchmark.py benchmark --demo
```

## 실제 CSV 비교 (정제본 사용)

정제본은 `data/processed/sizekorea_measurements_clean.csv` 에 있다.

```powershell
python src\benchmark.py benchmark --data data\processed\sizekorea_measurements_clean.csv
```

모델을 명시할 수도 있다.

```powershell
python src\benchmark.py benchmark `
  --data data\processed\sizekorea_measurements_clean.csv `
  --models baseline random_forest hist_gradient_boosting knn
```

기본 `--artifact-dir`은 스크립트 기준 `artifacts` 이다. 모델별 테스트 결과를
구분하려면 모델 하나당 별도 실행 폴더를 지정한다.

```powershell
python src\benchmark.py benchmark `
  --data data\processed\sizekorea_measurements_clean.csv `
  --models hist_gradient_boosting `
  --artifact-dir experiments\tabular\hist_gradient_boosting\sizekorea-1000-v2
```

평가 결과 (`--artifact-dir` 아래):

```text
csv/test_set.csv
csv/test_predictions_{model_name}.csv
models/{model_name}.joblib
metrics/metrics.json
metrics/run_manifest.json
```

각 target에 대해 다음을 기록한다.

1. MAE
2. RMSE
3. P90 absolute error
4. 학습 시간
5. 행당 예측 시간

## S3 SizeKorea 원본으로 실행

S3에서 원본을 받아 바로 벤치마크할 수 있다.
별도 인자 없이 실행하면 다음 원본을 사용한다.

```text
s3://skn28-cozy/22.사이즈코리아/8차 인체치수조사(2020~24)_치수데이터(공개용).xlsx
```

```powershell
python src\benchmark.py benchmark `
  --models baseline random_forest hist_gradient_boosting knn `
  --height 170 `
  --weight 65
```

처리 기준:

1. `(1~2차년도) 직접측정` 시트를 사용한다.
2. 표준 측정항목명으로 컬럼을 찾으므로 번호가 바뀌어도 이름이 같으면 동작한다.
3. 키와 둘레는 원본 mm에서 cm로 변환한다.
4. 몸무게는 kg를 유지한다.
5. S3 원본은 사용자 캐시 디렉터리에 저장하고 ETag가 바뀌었을 때만 다시 받는다.
6. 원본 SHA-256, 행 수, 컬럼 매핑, seed를 `run_manifest.json`에 기록한다.

AWS 자격증명은 코드나 `.env`에 넣지 않고 표준 AWS credential chain을 사용한다.

```powershell
aws sts get-caller-identity
```

다른 S3 파일을 쓰려면:

```powershell
python src\benchmark.py benchmark `
  --s3-uri "s3://bucket/path/file.xlsx"
```

## 키·몸무게 단일 예측

먼저 benchmark를 실행해 모델을 저장한 다음 사용한다.

```powershell
python src\benchmark.py predict `
  --artifact-dir artifacts `
  --height 170 `
  --weight 65
```

세 기본 모델의 상세 7개 예측값이 JSON으로 출력된다.

`benchmark` 명령에도 `--height`, `--weight`가 있으므로 7개 모델을 학습한
직후 같은 입력을 한 번에 비교할 수 있다. Hugging Face 모델은 라이브러리별
영구 저장 방식이 달라 `sample_predictions.json`에 해당 실행의 예측값을 남긴다.

## 7모델 비교 리포트 생성

기본 4개 + HF 3개, 총 7개 모델을 한 표로 비교한 리포트를 생성한다.
`experiments/tabular/<model>/sizekorea-1000-v1/metrics.json`을 읽어 합친다.

```powershell
python src\compare_all_models.py
```

생성물:

- `reports/model_comparison_summary.csv` — 모델별 평균 지표
- `reports/model_comparison_detail.csv` — target별 상세 지표
- `reports/model_comparison.png` — R2/MAE/RMSE 차트
- `reports/model_comparison_report.md` — 사람이 보는 종합 분석 (직접 작성)

## 데이터 정제 기준

`data/processed/sizekorea_measurements_clean.csv`는 SizeKorea 원본에서
아래 기준으로 만든 정제본이다. `benchmark.py`는 같은 기준으로 S3/Excel 원본을
읽어 벤치마크할 수 있다.

```powershell
python src\benchmark.py benchmark `
  --models baseline random_forest hist_gradient_boosting knn
```

정제 파이프라인:

1. S3에서 `data/raw/sizekorea_8th.xlsx` 다운로드 (없을 때만)
2. 측정 컬럼 추출
3. mm → cm 단위 변환
4. 정상 범위 외 값은 결측 처리
5. 결측 행 제거 후 `data/processed/sizekorea_measurements_clean.csv`로 저장

## Hugging Face 후보 (Colab GPU)

HF 3개 모델(`tabpfn_v2`, `nori`, `tabpfn_mix`)은 GPU 환경이 필요해
로컬 CPU에서는 실행하지 않는다. Colab에서 다음 노트북을 사용한다.

```text
src/huggingface_benchmark.ipynb
```

노트북은 다음을 수행한다:

1. Colab GPU 런타임에 HF 패키지 설치
2. 최신 `benchmark.py`를 Colab으로 복사해 같은 split/지표로 HF 3개 모델 학습
3. 기본 모델에서 생성한 `test_set.csv`를 `--test-data`로 전달해 같은 1000개 테스트셋을 사용한다.
4. `gender`, `height`, `weight` 입력으로 나머지 신체 치수를 예측한다.
5. Colab 쪽 결과는 `colab_{model}/` 아래에 로컬과 같은 `csv/`, `models/`, `metrics/`
   구조로 저장된다.
   - `metrics/metrics.json`: MAE/RMSE/R²/예측 시간 요약
   - `csv/test_set.csv`: 1000개 테스트 입력과 실제값 (로컬과 동일한 test_set)
   - `csv/test_predictions_{model}.csv`: 모델별 1000개 예측값과 오차
     (`actual_{부위}`, `predicted_{부위}`, `error_{부위}` 순서)
   - `metrics/run_manifest.json`: 실행 조건과 산출물 경로
6. 로컬로 가져올 때는 모델별 실행 폴더에 넣는다.

   ```text
   colab_tabpfn_v2/metrics/metrics.json  → experiments/tabular/tabpfn_v2/sizekorea-1000-v1/metrics.json
   colab_nori/metrics/metrics.json       → experiments/tabular/nori/sizekorea-1000-v1/metrics.json
   colab_tabpfn_mix/metrics/metrics.json → experiments/tabular/tabpfn_mix/sizekorea-1000-v1/metrics.json

   colab_{model}/csv/test_predictions_{model}.csv → experiments/tabular/{model}/sizekorea-1000-v1/predictions.csv
   ```
7. 그러면 `compare_all_models.py`가 7모델을 합쳐서 비교한다.

각 패키지를 별도로 설치한 후 `--models`에 추가한다.

```powershell
pip install tabpfn
pip install huggingface-hub
pip install synthefy-nori
pip install "autogluon.tabular[tabpfnmix]"
```

로컬에서 HF 모델을 직접 실행하려면:

```powershell
python src\benchmark.py benchmark `
  --data data\processed\sizekorea_measurements_clean.csv `
  --test-data experiments\tabular\_datasets\sizekorea-1000-v1\test_set.csv `
  --models tabpfn_v2 nori tabpfn_mix `
  --gender F `
  --height 160 `
  --weight 55
```

주의:

1. `Prior-Labs/TabPFN-v2-reg`는 배포 전 라이선스를 확인한다.
2. 최초 실행은 Hugging Face 모델 다운로드 때문에 네트워크가 필요하다.
3. foundation 모델은 target별로 7번 실행하므로 CPU·메모리·지연을 측정한다.
4. Hugging Face 모델 저장·재로딩은 라이브러리별 방식이 달라 현재 CLI의
   `predict` 명령은 기본 4개 모델부터 지원한다.
5. Colab 노트북에 예전 `benchmark.py` 패치 셀이 남아 있으면 실행하지 않는다.
   최신 `benchmark.py`가 이미 TabPFN-v2 체크포인트 다운로드와 모델별 CSV 생성을 처리한다.

## 보고서 (사람이 보는 결과)

`reports/model_comparison_report.md`는 7개 모델의 비교를 사람이 읽기 좋게
정리한 보고서다. 표·차트·분석·재현 명령어가 한 파일에 들어 있다.

```powershell
# 추천 워크플로
cd ml\body_measurement
python src\benchmark.py benchmark --data data\processed\sizekorea_measurements_clean.csv
python src\compare_all_models.py --run-name sizekorea-1000-v1
# Colab에서 HF 모델 결과를 experiments/tabular/{model}/sizekorea-1000-v1/에 추가
# → reports/model_comparison_report.md 직접 작성/갱신
```
