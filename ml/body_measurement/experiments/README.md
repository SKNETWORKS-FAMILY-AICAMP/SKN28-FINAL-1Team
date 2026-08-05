# 실험 결과 보관 규칙

## 1. 경로 규칙

```text
experiments/
├── tabular/
│   ├── <model>/<run_name>/
│   │   ├── predictions.csv
│   │   └── metrics.json
│   ├── _datasets/<run_name>/       # 모든 tabular 모델이 공유한 테스트셋·실행 조건
│   └── _summaries/<run_name>/      # 전체 모델 요약
└── vlm/
    ├── <model>/<run_name>/
    │   ├── predictions.csv
    │   ├── evaluated.csv
    │   └── metrics.json
    └── _summaries/<run_name>/      # 여러 VLM을 함께 실행한 요약
```

`run_name`은 `validation-prompt-full-v1`, `test-final-v1`처럼 데이터 구간과 실험 조건이
구분되게 작성한다. 같은 모델을 재실행할 때는 기존 폴더를 덮어쓰지 않고 새 실행명을 쓴다.

## 2. 파일 의미

1. `predictions.csv`: 모델 원본 응답과 예측값.
2. `evaluated.csv`: 정답을 결합하고 오차를 계산한 결과. VLM 평가에서 사용한다.
3. `metrics.json`: 평균 오차, 성공률, 지연 시간 등 요약 지표.
4. `_datasets`: 여러 모델에 공통으로 사용한 테스트셋과 재현 조건.

실험 결과에는 사진 경로와 원본 모델 응답이 포함될 수 있다. 대용량 또는 민감 데이터는
S3로 이전한 뒤, Git에는 실행 조건과 요약 지표만 남긴다.
