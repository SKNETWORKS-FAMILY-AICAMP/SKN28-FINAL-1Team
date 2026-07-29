# 신체치수 모델 비교 도구

키와 몸무게로 상세 신체치수 7개를 예측하는 모델을 동일한 데이터 분할과
지표로 비교한다.

## 비교 모델

기본 설치:

1. `RandomForestRegressor`
2. `HistGradientBoostingRegressor`
3. `KNeighborsRegressor`

선택 설치:

4. `Prior-Labs/TabPFN-v2-reg`
5. `Synthefy/Nori`
6. `autogluon/tabpfn-mix-1.0-regressor`

Hugging Face 후보는 모델 다운로드, 큰 의존성, 라이선스 검토가 필요하므로
기본 설치에서 제외했다.

## 데이터 형식

정제 CSV에 다음 컬럼이 필요하다.

```text
height,weight,chest,waist,hip,thigh,calf,arm,shoulder
```

- `height`: cm
- `weight`: kg
- 나머지 target: cm
- 결측 행은 현재 MVP에서 제외한다.
- 실제 평가에서는 동일 조사 대상이 train/test에 중복되지 않도록 전처리
  단계에서 subject 기준 split 컬럼을 추가하는 방향으로 확장한다.

## 설치

```powershell
python -m venv .venv-ml
.\.venv-ml\Scripts\Activate.ps1
pip install -r ml\body_measurement\requirements.txt
```

## 배선 확인

실제 데이터가 없을 때 기본 3개 모델의 학습·저장·예측 흐름만 확인한다.
이 결과는 실제 신체치수나 모델 성능으로 해석하면 안 된다.

```powershell
python ml\body_measurement\benchmark.py benchmark --demo
```

## 실제 CSV 비교

```powershell
python ml\body_measurement\benchmark.py benchmark `
  --data C:\path\to\sizekorea_clean.csv
```

모델을 명시할 수도 있다.

```powershell
python ml\body_measurement\benchmark.py benchmark `
  --data C:\path\to\sizekorea_clean.csv `
  --models random_forest hist_gradient_boosting knn
```

평가 결과:

```text
ml/body_measurement/artifacts/local/metrics.json
```

각 target에 대해 다음을 기록한다.

1. MAE
2. RMSE
3. P90 absolute error
4. 학습 시간
5. 행당 예측 시간

## S3 SizeKorea 원본으로 실행

별도 인자 없이 실행하면 다음 원본을 사용한다.

```text
s3://skn28-cozy/22.사이즈코리아/8차 인체치수조사(2020~24)_치수데이터(공개용).xlsx
```

```powershell
python ml\body_measurement\benchmark.py benchmark `
  --models random_forest hist_gradient_boosting knn `
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
python ml\body_measurement\benchmark.py benchmark `
  --s3-uri "s3://bucket/path/file.xlsx"
```

## 키·몸무게 단일 예측

먼저 benchmark를 실행해 모델을 저장한 다음 사용한다.

```powershell
python ml\body_measurement\benchmark.py predict `
  --height 170 `
  --weight 65
```

세 기본 모델의 상세 7개 예측값이 JSON으로 출력된다.

`benchmark` 명령에도 `--height`, `--weight`가 있으므로 6개 모델을 학습한
직후 같은 입력을 한 번에 비교할 수 있다. Hugging Face 모델은 라이브러리별
영구 저장 방식이 달라 `sample_predictions.json`에 해당 실행의 예측값을 남긴다.

## Hugging Face 후보

각 패키지를 별도로 설치한 후 `--models`에 추가한다.

```powershell
pip install tabpfn
pip install synthefy-nori
pip install "autogluon.tabular[tabpfnmix]"
```

```powershell
python ml\body_measurement\benchmark.py benchmark `
  --data C:\path\to\sizekorea_clean.csv `
  --models tabpfn_v2 nori tabpfn_mix
```

주의:

1. `Prior-Labs/TabPFN-v2-reg`는 배포 전 라이선스를 확인한다.
2. 최초 실행은 Hugging Face 모델 다운로드 때문에 네트워크가 필요하다.
3. foundation 모델은 target별로 7번 실행하므로 CPU·메모리·지연을 측정한다.
4. Hugging Face 모델 저장·재로딩은 라이브러리별 방식이 달라 현재 CLI의
   `predict` 명령은 기본 3개 모델부터 지원한다.
