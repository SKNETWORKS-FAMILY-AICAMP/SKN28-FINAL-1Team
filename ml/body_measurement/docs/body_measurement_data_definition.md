# 신체측정 데이터 정의 (11개 저장 항목)

## 1. 데이터 출처와 보관 위치

| 구분 | 위치 | 용도 |
|---|---|---|
| 원본 workbook | `ml/body_measurement/data/raw/sizekorea_8th.xlsx` | 사이즈코리아 제8차 원본 보관. 직접 수정하지 않는다. |
| 원본 3D 추출 CSV | `ml/body_measurement/data/raw/sizekorea_8th_3d_source.csv` | `(1~2차년도) 3D 측정` 시트의 학습 관련 원천 컬럼 |
| 전처리 전체 | `ml/body_measurement/data/preprocessed/sizekorea_8th_11targets.csv` | 단위 변환·파생식 적용 후 모델 입력/정답 |
| 전처리 분할 | `ml/body_measurement/data/preprocessed/splits/{train,validation,test}.csv` | seed 42, 80/10/10 분할 |
| Hist 모델 | `ml/body_measurement/data/hist/models/hist_gradient_boosting_11targets.joblib` | 성별·키·몸무게 입력 모델 |
| Hist 행별 결과 | `ml/body_measurement/data/hist/predictions/*.csv` | 실제값·예측값·오차를 행 단위로 저장 |
| VLM | `ml/body_measurement/data/vlm/` | 새 11개 프롬프트 실행 결과를 저장할 위치 |
| 과거 7개/둘레 기준 자료 | `ml/body_measurement/data/archive/legacy_7target_vlm/` | 현재 계약에는 사용하지 않는 참고용 보관 |

원본 workbook은 Git 이력에서 복구했으며 원본 자체에는 손대지 않는다. 원본 시트의 길이·둘레는 mm, 몸무게는 kg이므로 모델 CSV에서는 cm/kg로 변환한다.

## 2. 모델 입력과 14개 저장 항목 (상세 14개)

모델 입력은 `gender`, `height(cm)`, `weight(kg)` 3개다. API/mobile의 성별은 `male/female`, ML 내부 학습 인코딩은 `M/F`다. 기존 하위 호환성을 위해 둘레 3개(`thigh`, `calf`, `arm`)를 유지하고, 체형 비율 분석용 보조 지표로 길이 5개 및 비율 2개를 서비스한다 (총 14개 필드).

| API/모델 필드 | 단위 | 8차 원본 컬럼 또는 계산식 |
|---|---:|---|
| `shoulder` | cm | `298. 어깨사이너비` / 10 |
| `chest` | cm | `460. 젖가슴둘레` / 10 |
| `waist` | cm | `463. 허리둘레` / 10 |
| `hip` | cm | `465. 엉덩이둘레` / 10 |
| `thigh` | cm | `넙다리둘레` / 10 |
| `calf` | cm | `장딴지둘레` / 10 |
| `arm` | cm | `편위팔둘레` / 10 |
| `thigh_length` | cm | 샅선/인심 라인 → 무릎뼈/무릎 중심 |
| `calf_length` | cm | 무릎뼈/무릎 중심 → 바닥/복사뼈 |
| `torso_length` | cm | 어깨선 → 골반점 |
| `leg_length` | cm | 샅선/인심 라인 → 바닥/복사뼈 |
| `neck_length` | cm | `상체길이(머리~골반) - (어깨~골반) - 얼굴길이` (시각적 목길이, 8~12cm 범위, 평균 8.3cm) |
| `thigh_calf_ratio` | 비율 | `thigh_length / calf_length` |
| `torso_leg_ratio` | 비율 | `torso_length / leg_length` |

## 3. 최종 측정 기준

| 지표 | 확정 기준 |
|---|---|
| 허벅지 길이 | 샅선/인심 라인 → 무릎뼈/무릎 중심 |
| 종아리 길이 | 무릎뼈/무릎 중심 → 복사뼈/발목 |
| 상체 길이 | 어깨선/어깨높이 → 골반점 |
| 하체 길이 | 샅선/샅높이 → 복사뼈/발목 |
| 목길이 | 시각적 목길이 `상체길이(머리~골반) - (어깨~골반) - 얼굴길이` (8~12cm 범위, 평균 8.3cm) |

SizeKorea 181명 이미지 세트 기준 참고 분포는 다음과 같다. 이 값은 해석·캡션용 참고 범위이며, 사용자가 직접 수정한 양수 값은 저장할 수 있게 둔다.

| 지표 | 평균 | min | max |
|---|---:|---:|---:|
| `thigh_length` | 31.161 | 19.130 | 40.280 |
| `calf_length` | 38.006 | 28.850 | 48.860 |
| `torso_length` | 45.030 | 25.000 | 59.000 |
| `leg_length` | 68.416 | 54.300 | 85.300 |
| `thigh_calf_ratio` | 0.823 | 0.506 | 1.026 |
| `torso_leg_ratio` | 0.660 | 0.339 | 0.920 |

## 4. HistGradientBoosting 재현

`retrain_11targets.py`가 원본에서 매번 전처리·분할·학습·평가를 재현한다. `validation_predictions.csv`와 `test_predictions.csv`는 다음 컬럼을 모두 포함한다.

`source_row_id`, `subject_id`, 입력 3개, `actual_<target>`, `predicted_<target>`, `error_<target>`

따라서 평균 MAE만 보지 않고 각 사람·각 항목의 실제값과 예측값을 확인할 수 있다.

## 5. VLM 기준

기존 VLM 결과는 허벅지·종아리·팔뚝을 둘레로 요청한 실험이 섞여 있었기 때문에 새 길이 정의와 직접 비교하지 않는다. 과거 split/label 자료는 `data/archive/legacy_7target_vlm/`에 분리했다.

VLM은 비율을 직접 반환하지 않는다. 응답에는 `thigh_length_cm`, `calf_length_cm`, `torso_length_cm`, `leg_length_cm`를 포함하고, 서빙/벤치마크 코드가 아래처럼 계산한다.

| 저장 필드 | 계산식 |
|---|---|
| `thigh_calf_ratio` | `thigh_length_cm / calf_length_cm` |
| `torso_leg_ratio` | `torso_length_cm / leg_length_cm` |

비율이 SizeKorea 참고 분포를 벗어나도 실패 처리하지 않는다. 사진 추정값은 사용자가 결과 화면에서 수정할 수 있으므로, 필수 키 누락·숫자 변환 실패·0 이하 분모 같은 실제 계산 불가 상황만 실패로 본다.
