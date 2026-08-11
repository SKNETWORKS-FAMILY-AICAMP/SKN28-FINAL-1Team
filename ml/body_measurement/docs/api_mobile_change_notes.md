# 신체측정 API/mobile 변경 메모

나중에 main 병합 충돌이 날 때 기준을 빠르게 잡기 위한 메모다.

## 1. API / DB

| main 기준 기존 | 현재 변경 |
|---|---|
| `BodyMeasurement`에 `thigh`, `calf`, `arm` 둘레 컬럼 사용 | `thigh`, `calf`, `arm` 제거, 길이 기반 `thigh_length`, `calf_length`, `torso_length`, `leg_length` 추가 |
| 상세 7개 + 체형 지표 3개처럼 설명 | 총 11개 저장 항목으로 통일 |
| `torso_leg_ratio`가 `키-샅높이` 또는 골반→하체 기준과 섞임 | `torso_length / leg_length`로 통일 (`어깨선→골반점` / `샅선→발목`) |
| 비율 범위를 벗어나면 사진 측정 실패 처리 | 참고 분포는 문서/캡션에만 쓰고, 계산 가능한 양수 비율은 저장 |
| Swagger 설명에 예전 둘레/10개 기준 표현 존재 | 11개 패션용 체형 지표 설명으로 통일 |

## 2. ML contract

| main 기준 기존 | 현재 변경 |
|---|---|
| 모델 artifact 경로가 `artifacts/models/hist_gradient_boosting.joblib` | `data/hist/models/hist_gradient_boosting_11targets.joblib` |
| 학습 target에 과거 `thigh/calf/arm` 둘레 포함 | 11개 target: `shoulder`, `chest`, `waist`, `hip`, `thigh_length`, `calf_length`, `torso_length`, `leg_length`, `neck_length`, `thigh_calf_ratio`, `torso_leg_ratio` |
| VLM 프롬프트가 M/F 또는 과거 ratio 기준과 섞일 수 있음 | VLM 프롬프트 노출 성별은 `male/female`, 비율은 서버/후처리에서 길이값으로 계산 |
| 과거 실험 코드/CSV가 활성 경로에 섞임 | `legacy/`, `data/archive/legacy_7target_vlm/`로 분리 |

## 3. mobile

| main 기준 기존 | 현재 변경 |
|---|---|
| 결과 화면/가이드에 `thigh`, `calf`, `arm` 둘레 설명 존재 | 허벅지길이·종아리길이·상체길이·하체길이 설명으로 교체 |
| 성별 미선택 값이 서버로 갈 수 있음 | `male/female`만 보내고, 미선택은 필드 생략 |
| 사진 분석 로딩 문구가 “몇 분”처럼 모호 | “최대 약 5분”으로 표시 |

## 4. 충돌 해결 우선순위

1. DB/API 필드는 현재 11개 항목 기준을 우선한다.
2. `gender`는 API/Swagger/mobile에서는 `male/female`을 우선한다.
3. ML 내부 학습 인코딩에서만 `M/F`를 허용한다.
4. 과거 `thigh/calf/arm` 둘레 자료는 archive 참고용으로만 둔다.
