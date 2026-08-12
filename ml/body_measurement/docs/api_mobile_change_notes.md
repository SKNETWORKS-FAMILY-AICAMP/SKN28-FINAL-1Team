# 신체측정 API/mobile 변경 메모

나중에 main 병합 충돌이 날 때 기준을 빠르게 잡기 위한 메모다.

## 1. API / DB

| main 기준 기존 | 현재 확정 변경 |
|---|---|
| `BodyMeasurement`에 `thigh`, `calf`, `arm` 둘레 컬럼 사용 | `thigh`, `calf`, `arm` 둘레 유지 + 길이 기반 `thigh_length`, `calf_length`, `torso_length`, `leg_length`, `neck_length` 추가 (상세 14개 필드) |
| 상세 7개 + 체형 지표 3개처럼 설명 | 총 14개 상세 저장 항목 (기본 둘레 7개 + 보조 길이 5개 + 비율 2개) |
| `torso_leg_ratio`가 `키-샅높이` 또는 골반→하체 기준과 섞임 | `torso_length / leg_length`로 통일 (`어깨선→골반점` / `샅선→발목`) |
| `neck_length` 정의 모호성 | 시각적 목길이 `상체길이(머리~골반) - (어깨~골반) - 얼굴길이` (8~12cm 범위, 평균 8.3cm) |
| 비율 범위를 벗어나면 사진 측정 실패 처리 | 참고 분포는 문서/캡션에만 쓰고, 계산 가능한 양수 비율은 저장 |

## 2. ML contract

| main 기준 기존 | 현재 확정 변경 |
|---|---|
| 모델 artifact 경로가 `artifacts/models/hist_gradient_boosting.joblib` | 181명 이미지 세트 기반 `data/hist/models/hist_gradient_boosting_181.joblib` (단일 세트 서빙) + 둘레 모델 `hist_gradient_boosting_circumference.joblib` |
| 학습 target에 과거 `thigh/calf/arm` 둘레 포함 여부 혼선 | 14개 필드 전체 지원 (`chest`, `waist`, `hip`, `thigh`, `calf`, `arm`, `shoulder`, `thigh_length`, `calf_length`, `torso_length`, `leg_length`, `neck_length`, 비율 2개) |
| VLM 프롬프트가 M/F 또는 과거 ratio 기준과 섞일 수 있음 | VLM 프롬프트 노출 성별은 `male/female`, 시각적 목길이(8~12cm) 가이드 포함, 비율은 서버/후처리에서 길이값으로 계산 |

## 3. mobile

| main 기준 기존 | 현재 확정 변경 |
|---|---|
| 결과 화면/가이드에 `thigh`, `calf`, `arm` 둘레 설명 존재 | main 기존 둘레(가슴·허리·엉덩이·어깨·허벅지·종아리·팔뚝) 유지 + 길이 지표는 보조 수치로 표시 |
| 성별 미선택 값이 서버로 갈 수 있음 | `male/female`만 보내고, 미선택은 필드 생략 |
| 사진 분석 로딩 문구가 “몇 분”처럼 모호 | “최대 약 5분”으로 표시 |

## 4. 충돌 해결 우선순위

1. **DB/API 계약은 main 기존 둘레 필드(`thigh`, `calf`, `arm`)를 유지하면서 `*_length` 5개 지표를 추가한 상세 14개 필드 구조를 우선한다.**
2. `gender`는 API/Swagger/mobile에서는 `male/female`을 우선한다.
3. ML 내부 학습 인코딩에서만 `M/F`를 허용한다.
4. 목길이는 시각적 목길이 공식 `상체길이(머리~골반) - (어깨~골반) - 얼굴길이` (평균 8.3cm, 범위 8~12cm)를 우선 적용한다.
