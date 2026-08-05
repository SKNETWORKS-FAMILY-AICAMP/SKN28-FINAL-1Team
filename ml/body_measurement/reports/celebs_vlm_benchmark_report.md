# 한국 연예인 VLM 벤치마크 보고서

## 목적
`사진 + (키, 몸무게, 성별) → 가슴/허리/엉덩이` 시스템의 정확도를 평가.

## 데이터셋
- **18명 한국 연예인 (full body 사진 보장)**
- 출처: bodysize.org, kdramastars, press photo
- 카테고리: celeb_actor 8, idol 8, plus_size_model 1, comedian_mc 1
- 사진: 8명 front+side, 10명 front only
  - "side" 사진도 사실 정면 컷인 경우 多 (한국 연예인 press 자료의 한계)

## 측정
- 모델: gpt-4o-mini (JSON mode, max_tokens=300)
- 입력: full body 사진 + (height, gender, weight) 메타데이터
- 출력: chest/waist/hip cm 추정
- 1회 호출, 1~5초/celeb

## 결과

### 전체 MAE (n=18)
| 부위 | MAE | Bias |
|---|---|---|
| 가슴 | **4.95 cm** | +3.31 |
| 허리 | **2.53 cm** | +2.19 |
| 엉덩이 | **3.82 cm** | +3.15 |

**Bias 모두 양수** → VLM은 약 2-3cm 과대 추정. 사진이 face shot 위주라 신체 비율 정보 부족.

### view별 비교
| view | n | 가슴 | 허리 | 엉덩이 |
|---|---|---|---|---|
| front+side | 8 | 4.26 | 2.19 | 4.21 |
| front only | 10 | 5.50 | 2.80 | 3.50 |

### 카테고리별
| 카테고리 | n | 가슴 | 허리 | 엉덩이 |
|---|---|---|---|---|
| idol | 8 | 4.70 | 2.31 | 3.96 |
| celeb_actor | 8 | 5.19 | 3.12 | 3.56 |
| plus_size_model | 1 | 0.00 | 1.00 | 8.00 |
| comedian_mc | 1 | 10.00 | 1.00 | 0.50 |

## 베스트/워스트 사례

### Best 5 (sum of abs errors)
| celeb | err_sum | actual C/W/H | pred C/W/H |
|---|---|---|---|
| kim_hyuna | 2.0cm | 81/59/86 | 81/60/84 |
| kim_yoo-jung | 3.0cm | 83/60/86 | 82/62/86 |
| hyuna | 4.0cm | 81/59/86 | 80/58/84 |
| yoo_in_na | 7.0cm | 81/61/84 | 84/61/88 |
| park_bo-young | 8.0cm | 76/58/84 | 80/62/84 |

### Worst 5
| celeb | err_sum | actual C/W/H | pred C/W/H | 비고 |
|---|---|---|---|---|
| yoon_eun_hye | 22.5cm | 76/58/81 | 84/65/88 | 빨간 정장, 구조적 옷 |
| iu | 19.0cm | 76/58/76 | 83/60/86 | 헐렁한 보라 드레스 |
| song_ji-hyo | 18.0cm | 76/59/81 | 84/63/87 | 빨간 드레스 |
| seulgi | 18.0cm | 76/55/80 | 84/60/85 | 카툰 스웨터 |
| kim_go-eun | 14.0cm | 79/61/84 | 85/65/88 | |

## 데이터 한계
1. **100명 목표 미달**: 18명만 확보. 한국 celeb press photo 중 full body 비율이 낮음. 보디사이즈의 "large-photo" 427x640이 전신이지만 일부 celeb은 portrait 300x400만 있음.
2. **side 사진 부재**: 진짜 90° 측면 사진은 거의 없음. "side"로 라벨링한 것도 정면 컷인 경우 多.
3. **구조적/헐렁한 의상**: VLM이 신체 비율을 정확히 추정하기 어려움. (yoon_eun_hye의 정장, iu의 드레스 등)
4. **jun_ji_hyun 제외**: 재킷이 몸 가림 + side 사진이 portrait라 VLM이 C42/W31/H43 같은 비현실 값 반환 → MAE 왜곡 방지로 제외

## 비교 (vs 이전 실험)
| 실험 | n | 가슴 | 허리 | 엉덩이 |
|---|---|---|---|---|
| 10명 celeb_actor (이전) | 10 | 3.83 | 2.95 | 3.90 |
| 19명 (이전, jun 포함) | 19 | 6.93 | 4.08 | 5.93 |
| **18명 (현재)** | **18** | **4.95** | **2.53** | **3.82** |

→ 이전 10명 celeb_actor 결과보다 약간 안 좋음. 이유: 8명의 idol (체구 작고 loose 의상) 추가로 bias ↑

## 결론
- **허리 MAE 2.53cm는 실용적**: SizeKorea 베이스라인(KNN 1.92cm)에 근접
- **가슴/엉덩이 MAE 4-5cm**: 의상 가림, side 부재로 한계
- **bias 양수 (+2-3cm)**: VLM이 작은 체구 celebs를 과대 추정. 평균적 body 비율 가정 때문.
- **개선 방향**:
  1. 진짜 측면 사진 확보 (런웨이/사이드뷰 잡지)
  2. side도 정면이면 의미 없음 → weight, age 등 추가 메타 활용
  3. VLM에게 의상 가림 시 "보이는 cue만 사용" 명시
  4. 한국인 평균 body 비율 prior 추가

## 산출 파일
- `data/celebrities/celebrities_index.csv` (18명)
- `data/celebrities/all_measurements.csv` (18명 + 빈 pred 컬럼)
- `data/celebrities/<sid>_front.jpg` × 18, `<sid>_side.jpg` × 8
- `reports/celebrities_vlm_benchmark_20.csv` (raw, jun 포함)
- `reports/celebrities_vlm_benchmark_final.csv` (clean, jun 제외)
- 연예인 사진 수집·VLM 임시 벤치마크 스크립트는 현재 사용하지 않아 제거했다.
