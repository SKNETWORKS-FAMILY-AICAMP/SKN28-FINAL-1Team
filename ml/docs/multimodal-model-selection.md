# 멀티모달 모델 선정 기준

이 문서는 현재 신체측정 기준에 맞춘 최신 요약이다. 과거의 허벅지둘레·종아리둘레·팔뚝둘레 기반 7개/10개 실험 기준은 사용하지 않는다.

## 1. 현재 출력 계약

| 구분 | 필드 |
|---|---|
| 기본 둘레·너비 | `shoulder`, `chest`, `waist`, `hip` |
| 패션용 길이감 | `thigh_length`, `calf_length`, `torso_length`, `leg_length`, `neck_length` |
| 패션용 비율 | `thigh_calf_ratio`, `torso_leg_ratio` |

입력은 `gender`, `height(cm)`, `weight(kg)`이며, 사진 경로는 정면/측면 전신 사진을 추가로 사용한다.

## 2. 선정 기준

| 기준 | 현재 판단 |
|---|---|
| 무사진 기준선 | HistGradientBoosting 11개 출력 모델을 기준선으로 둔다. |
| 사진 모델 | VLM은 정면/측면 사진에서 패션용 길이감을 추정한다. |
| 비율 계산 | VLM이 비율을 직접 반환하지 않고, `thigh_length / calf_length`, `torso_length / leg_length`로 후처리 계산한다. |
| 평균 비율 | SizeKorea 기준 `thigh_calf_ratio` 평균 0.823, `torso_leg_ratio` 평균 0.660을 해석 기준으로 둔다. |
| 정량 비교 | 같은 subject의 이미지와 실측 데이터가 연결된 행만 평가한다. |
| 개인정보 | 실제 서비스 전에는 얼굴 블러/저장 정책을 별도로 확정해야 한다. |

## 3. 현재 평가 문서

- 데이터 정의: `ml/body_measurement/docs/body_measurement_data_definition.md`
- 모델 평가: `ml/body_measurement/docs/body_measurement_model_evaluation.md`
- VLM 이미지 정답 생성: `ml/body_measurement/scripts/build_vlm_image_ground_truth.py`
- Hist 재학습: `ml/body_measurement/scripts/retrain_11targets.py`
