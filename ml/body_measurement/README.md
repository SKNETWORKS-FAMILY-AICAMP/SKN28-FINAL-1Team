# 신체측정 모델

현재 기준은 8차 Size Korea 3D 원본의 복사·전처리본으로 학습한 11개 출력 HistGradientBoosting 모델이다.
원본 파일은 직접 수정하지 않고, 파생 데이터만 `data/preprocessed/`, `data/hist/`, `data/vlm/` 아래에 둔다.

## 현재 출력

`shoulder`, `chest`, `waist`, `hip`, `thigh_length`, `calf_length`, `torso_length`, `leg_length`, `neck_length`, `thigh_calf_ratio`, `torso_leg_ratio`

입력은 `gender`, `height(cm)`, `weight(kg)`이다.
출력은 의료·해부학적 실측이 아니라 옷 추천과 핏 판단에 쓰는 패션용 체형 지표다.

## 주요 경로

- 원본: `data/raw/sizekorea_8th.xlsx`
- 전처리: `data/preprocessed/`
- Hist 모델·행별 평가: `data/hist/`
- 이미지 연결 결과·VLM: `data/vlm/`
- 데이터 정의: `docs/body_measurement_data_definition.md`
- 모델 평가: `docs/body_measurement_model_evaluation.md`
- 과거 7개/둘레 기준 실험: `legacy/`, `data/archive/legacy_7target_vlm/`

## 재현

```powershell
python ml/body_measurement/scripts/retrain_11targets.py
python ml/body_measurement/scripts/filter_predictions_to_people.py
python ml/body_measurement/scripts/build_sizekorea_image_measurements.py
python ml/body_measurement/scripts/build_vlm_image_ground_truth.py
python ml/body_measurement/scripts/align_vlm_predictions.py
```

VLM 실행 전에는 `OPENROUTER_API_KEY`와 이미지-대상자 매핑이 필요하다. VLM 비율은 모델이 직접 반환하지 않고, 서버/후처리에서 길이값으로 계산한다.

## 현재 활성 스크립트

| 스크립트 | 역할 |
|---|---|
| `scripts/retrain_11targets.py` | SizeKorea 8차 원본에서 11개 항목 Hist 모델 재학습 |
| `scripts/build_sizekorea_image_measurements.py` | `data/people` 이미지 181명과 git 이력 profile 매칭 |
| `scripts/build_vlm_image_ground_truth.py` | 같은 이미지 대상자의 비교 가능한 실측 라벨 생성 |
| `scripts/align_vlm_predictions.py` | 기존/신규 VLM 결과를 Hist CSV 계약과 같은 컬럼으로 정렬 |
| `scripts/filter_predictions_to_people.py` | 사진 파일이 있는 대상자만 prediction CSV에 남김 |
| `scripts/run_openrouter.py` | 비용 승인 후에만 쓰는 VLM 실행 스크립트 |

과거 `thigh/calf/arm` 둘레 기준 벤치마크와 split 파일은 현재 API 계약에 쓰지 않으므로 `legacy/`와 `data/archive/legacy_7target_vlm/`로 분리했다.
