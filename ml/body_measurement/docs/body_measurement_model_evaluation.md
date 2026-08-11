# 신체측정 모델 평가

평가 기준은 현재 11개 저장 항목만 사용한다. 과거 허벅지둘레·종아리둘레·팔뚝둘레 결과와 과거 `(키-샅높이)/샅높이` 비율식 결과는 현재 평가에 포함하지 않는다.

## 1. 평가 대상

| 모델 | 입력 | 정답 데이터 | 행 수 |
|---|---|---|---:|
| HistGradientBoosting (11 targets) | 성별·키·몸무게 | 8차 3D 실측 파생 라벨 | train 3,588 / validation 448 / test 449 |
| HistGradientBoosting (사진 연결 subset) | 성별·키·몸무게 | 이미지 split 입력 + 가능한 실제 라벨 | test 145 / validation 36 |
| VLM (11-target CSV 계약 정렬) | 앞·옆 사진 + 기본 정보 | 기존 VLM 결과를 새 컬럼 계약으로 정렬 | validation 36 / test 145 |

이번 갱신에서는 외부 비용이 드는 VLM 호출을 하지 않았다. 기존 VLM 실행분을 새 11개 CSV 계약으로 정렬하되, 기존 응답에 `torso_length`, `leg_length`가 없으면 해당 예측 컬럼은 비워 둔다.

## 2. HistGradientBoosting 결과

단위는 cm이며, 비율은 단위가 없다.

| 항목 | Validation MAE | Validation RMSE | Validation R² | Test MAE | Test RMSE | Test R² |
|---|---:|---:|---:|---:|---:|---:|
| shoulder | 1.271 | 1.651 | 0.691 | 1.337 | 1.665 | 0.723 |
| chest | 2.534 | 3.221 | 0.877 | 2.658 | 3.605 | 0.852 |
| waist | 3.165 | 4.002 | 0.849 | 3.435 | 4.429 | 0.818 |
| hip | 1.976 | 2.517 | 0.856 | 1.988 | 2.571 | 0.853 |
| thigh_length | 1.364 | 1.887 | 0.369 | 1.435 | 1.873 | 0.360 |
| calf_length | 1.049 | 1.355 | 0.759 | 1.112 | 1.423 | 0.759 |
| torso_length | 1.699 | 2.172 | 0.431 | 1.598 | 2.059 | 0.511 |
| leg_length | 1.414 | 1.814 | 0.811 | 1.546 | 1.949 | 0.810 |
| neck_length | 0.980 | 1.233 | 0.191 | 0.901 | 1.120 | 0.286 |
| thigh_calf_ratio | 0.044 | 0.059 | 0.257 | 0.048 | 0.060 | 0.242 |
| torso_leg_ratio | 0.035 | 0.045 | 0.047 | 0.033 | 0.043 | 0.040 |

`leg_length`, `calf_length`, 가슴·허리·엉덩이 둘레는 기본 정보만으로도 상대적으로 안정적이다. `torso_leg_ratio`는 MAE는 작지만 R²가 낮으므로 개인별 미세 차이는 사진 측정 또는 사용자 수정값을 우선한다.

## 3. 행별 결과 파일

각 행에는 `source_row_id`, `subject_id`, 기본 입력 3개, 11개 `actual_*`, 11개 `predicted_*`, 11개 `error_*`가 있다.

| 파일 | 용도 |
|---|---|
| `data/hist/predictions/validation_predictions.csv` | validation 행별 실제값·예측값·오차 |
| `data/hist/predictions/test_predictions.csv` | test 행별 실제값·예측값·오차 |
| `data/hist/predictions/vlm_validation_inputs_hist_predictions.csv` | 이미지가 있는 validation 대상자의 Hist 예측 |
| `data/hist/predictions/vlm_test_inputs_hist_predictions.csv` | 이미지가 있는 test 대상자의 Hist 예측 |

## 4. VLM 실행 기준

새 실행부터 VLM은 ratio를 직접 반환하지 않고 `thigh_length_cm`, `calf_length_cm`, `torso_length_cm`, `leg_length_cm`를 반환한다. 정렬 스크립트는 `thigh_length/calf_length`, `torso_length/leg_length`로 ratio를 재계산한다. 기존 실행분처럼 support length가 없으면 기존 ratio 컬럼을 fallback으로 사용하고, 없는 길이 컬럼은 비워 둔다.

비율이 참고 분포 밖이어도 실패 처리하지 않는다. 필수 키 누락, 숫자 변환 실패, 0 이하 분모만 실패로 본다.

## 5. 재현 파일

- 학습 스크립트: `ml/body_measurement/scripts/retrain_11targets.py`
- 사진 필터 스크립트: `ml/body_measurement/scripts/filter_predictions_to_people.py`
- VLM 컬럼 정렬 스크립트: `ml/body_measurement/scripts/align_vlm_predictions.py`
- 같은 이미지 profile 복구/평가 스크립트: `ml/body_measurement/scripts/build_vlm_image_ground_truth.py`
- 집계 지표: `ml/body_measurement/data/hist/metrics.json`
- 행별 실측 비교: `ml/body_measurement/data/hist/predictions/`
- 과거 7개/둘레 기준 실험: `ml/body_measurement/legacy/`, `ml/body_measurement/data/archive/legacy_7target_vlm/`
