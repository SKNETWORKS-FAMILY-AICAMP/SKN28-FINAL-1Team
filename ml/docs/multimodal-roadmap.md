# 멀티모달 신체측정 로드맵

현재 로드맵은 11개 패션용 체형 지표 기준으로 정리한다. 과거 7개/10개 신체치수 실험과 팔뚝둘레·허벅지둘레·종아리둘레 기준은 더 이상 현재 기준으로 사용하지 않는다.

## 1. 완료된 기준 정리

| 항목 | 현재 상태 |
|---|---|
| 출력 필드 | `shoulder`, `chest`, `waist`, `hip`, `thigh_length`, `calf_length`, `torso_length`, `leg_length`, `neck_length`, `thigh_calf_ratio`, `torso_leg_ratio` |
| 무사진 추정 | 8차 Size Korea 기반 HistGradientBoosting 11개 출력 |
| 사진 추정 | 정면/측면 사진 기반 VLM 추정 + 서버 후처리 비율 계산 |
| 평균 비율 | SizeKorea 기준 `thigh_calf_ratio` 평균 0.823, `torso_leg_ratio` 평균 0.660 |
| 원본 데이터 | `data/raw/`에 보관, 직접 수정하지 않음 |
| 파생 데이터 | `data/preprocessed/`, `data/hist/`, `data/vlm/`에 분리 보관 |

## 2. 다음 작업

1. VLM 평가 가능한 정답 컬럼을 더 확보한다.
2. 수치별 `source`와 `confidence`를 API 응답에 추가할지 결정한다.
3. 사진 분석 결과는 바로 확정하지 않고, 사용자가 수정·확정할 수 있는 프론트 흐름으로 연결한다.
4. 실제 서비스 전 얼굴 블러와 사진 저장/폐기 정책을 확정한다.

## 3. 기준 문서

- 데이터 정의: `ml/body_measurement/docs/body_measurement_data_definition.md`
- 모델 평가: `ml/body_measurement/docs/body_measurement_model_evaluation.md`
