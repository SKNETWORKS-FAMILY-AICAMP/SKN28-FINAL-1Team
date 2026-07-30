# 신체치수 예측 모델 비교 보고서

키·몸무게로 신체치수 7개(가슴/허리/엉덩이/허벅지/장딴지/팔/어깨)를 예측하는
기본 모델 3개와 Hugging Face 모델 3개, 총 6개를 같은 조건에서 비교했다.

이 벤치마크는 키와 몸무게만 입력했을 때 의류 사이즈 추천에 필요한 주요 신체치수 7개를 얼마나 정확하게 예측할 수 있는지 확인하기 위한 실험이다.

- 데이터: SizeKorea 정제 CSV (`sizekorea_measurements_clean.csv`)
- 분할: `train_test_split(test_size=0.2, random_state=42)` 동일 적용
- 지표: MAE, RMSE, R2 (모두 `benchmark.py`의 `benchmark()` 함수로 계산)
- 기본 모델 3개는 로컬 CPU에서, HF 모델 3개는 Colab GPU 환경에서 실행

## 결과

| # | 모델                   | mean_mae (cm) | mean_rmse (cm) | mean_r2       | fit_seconds | predict_ms/row |
| - | ---------------------- | ------------: | -------------: | ------------: | ----------: | -------------: |
| 1 | tabpfn_v2              |         1.971 |          2.515 |     **0.775** |        8.21 |           9.85 |
| 2 | nori                   |         1.980 |          2.528 |         0.773 |        1.80 |          19.89 |
| 3 | tabpfn_mix             |         2.008 |          2.561 |         0.768 |      261.20 |           3.47 |
| 4 | hist_gradient_boosting |         2.080 |          2.653 |         0.750 |        8.24 |           0.22 |
| 5 | random_forest          |         2.090 |          2.666 |         0.749 |        0.59 |           0.12 |
| 6 | knn                    |         2.082 |          2.678 |         0.746 |        0.01 |           0.01 |

R2 기준 내림차순 정렬. 상세 target별 수치는 `model_comparison_detail.csv` 참고.
예를 들어 mean_mae가 1.971cm라면, 예측한 7개 신체치수가 실제 측정값과 평균적으로 약 1.97cm 차이났다는 의미다.

![모델 6종 비교](model_comparison.png)

## 분석

1. **tabpfn_v2** — R2 0.775로 6개 모델 중 1위. MAE 1.971cm, RMSE 2.515cm로
   세 지표 모두 최고 성능이다. 학습 8.21초로 무겁지 않아 정확도와 비용
   둘 다 챙긴다.

   - 근거: `reports/model_comparison_summary.csv` 1행

2. **nori** — R2 0.773으로 2위, 1위 tabpfn_v2와 차이는 0.002뿐이라
   사실상 동급 성능이다. 학습 1.80초로 6개 모델 중 HF 모델 안에서는
   가장 빠르다.

   - 근거: `reports/model_comparison_summary.csv` 2행,
     `artifacts/nori/metrics.json`의 `fit_seconds` 1.802588

3. **tabpfn_mix** — R2 0.768로 3위. 성능은 1·2위와 0.007 이내로
   큰 차이가 없지만, 학습 261.20초로 나머지 5개 모델 중 가장 느리고
   2위 nori보다 145배 느리다. target 7개마다 AutoGluon predictor를
   따로 학습하는 구조가 원인이라 데이터·target이 늘수록 더 느려진다.

   - 근거: `artifacts/tabpfn_mix/metrics.json`의 `fit_seconds` 261.19747,
     `benchmark.py`의 `TabPFNMixRegressor.fit()`이 target마다
     `TabularPredictor`를 새로 학습하는 구조

4. **hist_gradient_boosting** — R2 0.750으로 4위. 기본 모델 3개 중에서는
   가장 성능이 좋지만, HF 모델 중 가장 낮은 tabpfn_mix(0.768)보다도
   낮다. 학습 8.24초로 tabpfn_v2와 비슷한 비용이 든다.

   - 근거: `reports/model_comparison_summary.csv` 4행

5. **random_forest** — R2 0.749로 5위. hist_gradient_boosting과
   0.001 차이로 사실상 같은 수준이고, 학습은 0.59초로 훨씬 가볍다.

   - 근거: `reports/model_comparison_summary.csv` 5행

6. **knn** — R2 0.746로 6위(최하위)지만, 학습 0.0063초·예측
   0.0078ms/row로 전체 모델 중 압도적으로 가장 가볍다. HF 모델 대비
   학습은 최소 280배(nori 대비), 예측은 최소 400배 이상 빠르다.
   성능 손해가 1위 대비 R2 -0.029, MAE +0.11cm 수준이라 GPU·외부
   의존성 없이도 쓸 만한 대안이다.

   - 근거: `reports/model_comparison_summary.csv` 6행

## 결론

- **정확도 우선**: tabpfn_v2 (R2 1위, 학습 8초로 합리적)
- **속도+정확도 균형**: nori (R2 2위, 학습 1.8초로 HF 중 가장 빠름)
- **의존성 최소화가 우선**: knn (기본 모델 중 가장 가볍고, 성능 손해가 크지 않음)
- tabpfn_mix는 성능 우위가 크지 않은데 학습 비용만 압도적으로 커서,
  현재 데이터 규모에서는 우선순위가 낮다.

## 재현 방법

```powershell
cd ml\body_measurement
python src\benchmark.py benchmark --data data\sizekorea_measurements_clean.csv --models random_forest hist_gradient_boosting knn --artifact-dir artifacts\classic
python src\compare_all_models.py
```

HF 3개 모델(`tabpfn_v2`, `nori`, `tabpfn_mix`)은 GPU 환경(Colab)에서 실행한
결과를 `artifacts/tabpfn_v2`, `artifacts/nori`, `artifacts/tabpfn_mix`에
옮겨둔 것을 사용했다.
