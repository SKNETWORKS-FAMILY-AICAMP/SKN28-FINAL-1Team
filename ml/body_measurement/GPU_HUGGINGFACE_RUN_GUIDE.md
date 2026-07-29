# GPU 환경에서 HuggingFace 신체 치수 모델 테스트하기

이 문서는 GPU 서버에서 `ml/body_measurement` 폴더를 보고 신체 치수 예측 모델을 실행하는 방법을 정리한다.

현재 목표는 키와 몸무게를 입력해서 아래 7개 신체 치수를 예측하는 모델을 비교하는 것이다.

```text
chest, waist, hip, thigh, calf, arm, shoulder
```

비교 대상 모델은 다음 6개다.

1. `random_forest`
2. `hist_gradient_boosting`
3. `knn`
4. `nori`
5. `tabpfn_v2`
6. `tabpfn_mix`

HuggingFace 계열 모델은 모델 다운로드, GPU 메모리, 의존성 문제가 생길 수 있으므로 한 번에 전부 돌리지 말고 가벼운 모델부터 순서대로 확인한다.

---

## 01. 전체 흐름

```text
프로젝트 받기
→ Python 가상환경 생성
→ 기본 패키지 설치
→ GPU 인식 확인
→ SizeKorea 정제 CSV 준비
→ 기본 3개 모델 실행
→ Nori 실행
→ TabPFN-v2 실행
→ TabPFNMix 실행
→ 전체 모델 비교
→ metrics.json / sample_predictions.json 확인
```

---

## 02. GPU 서버 기본 확인

GPU 서버에 접속한 뒤 프로젝트 루트에서 진행한다.

```bash
cd SKN28-FINAL-1Team
```

GPU가 보이는지 먼저 확인한다.

```bash
nvidia-smi
```

정상이라면 GPU 이름, CUDA 버전, 메모리 사용량이 출력된다.

Python 버전도 확인한다.

```bash
python --version
```

권장 버전은 Python 3.11 이상이다.

---

## 03. 가상환경 만들기

GPU 서버에서는 기존 백엔드 가상환경과 분리해서 ML 전용 가상환경을 쓰는 것을 권장한다.

```bash
python -m venv .venv-ml
source .venv-ml/bin/activate
```

pip 기본 도구를 업데이트한다.

```bash
pip install -U pip setuptools wheel
```

---

## 04. 기본 의존성 설치

먼저 기본 모델 실행에 필요한 패키지를 설치한다.

```bash
pip install -r ml/body_measurement/requirements.txt
```

현재 `requirements.txt`에는 scikit-learn 기반 기본 모델 실행에 필요한 패키지만 기본 설치 대상으로 들어 있다.

HuggingFace 후보는 무겁기 때문에 선택 설치로 분리되어 있다.

---

## 05. PyTorch GPU 인식 확인

HuggingFace 계열 모델은 내부적으로 PyTorch를 사용한다.

먼저 PyTorch가 설치되어 있는지 확인한다.

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

기대 결과는 다음과 같다.

```text
True
NVIDIA ...
```

`torch.cuda.is_available()`가 `False`이면 GPU로 돌고 있는 것이 아니다.

이 경우 CUDA 버전에 맞는 PyTorch를 다시 설치해야 한다. 서버의 CUDA 버전은 `nvidia-smi`에서 확인한다.

예시:

```bash
pip install -U torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

위 명령은 CUDA 12.1 예시다. 실제 서버 CUDA/PyTorch 조합은 PyTorch 공식 설치 명령에 맞춰 조정한다.

---

## 06. HuggingFace 캐시 경로 설정

모델 가중치는 Git에 넣지 않는다.

GPU 서버의 작업 디스크에 HuggingFace 캐시를 두는 것을 권장한다.

```bash
export HF_HOME="$PWD/.cache/huggingface"
export TABPFN_MODEL_CACHE_DIR="$PWD/.cache/tabpfn"
```

익명 다운로드 제한에 걸리면 HuggingFace read token을 사용한다.

```bash
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxx"
```

토큰은 절대 Git에 커밋하지 않는다.

---

## 07. 데이터 준비

가장 권장하는 방식은 이미 정제된 CSV를 사용하는 것이다.

필요한 파일:

```text
local/sizekorea/sizekorea_measurements_clean.csv
```

CSV에는 다음 컬럼이 있어야 한다.

```text
height,weight,chest,waist,hip,thigh,calf,arm,shoulder
```

정제 CSV가 없다면 AWS S3 접근 권한을 확인한다.

```bash
aws sts get-caller-identity
```

그 다음 원본 Excel을 받아 정제한다.

```bash
python ml/body_measurement/manual_test.py
```

정상 실행되면 아래 파일이 생성된다.

```text
local/sizekorea/sizekorea_measurements_clean.csv
```

---

## 08. 기본 3개 모델 먼저 실행

HuggingFace 모델을 돌리기 전에 기본 모델이 정상 동작하는지 확인한다.

```bash
python ml/body_measurement/benchmark.py benchmark \
  --data local/sizekorea/sizekorea_measurements_clean.csv \
  --models random_forest hist_gradient_boosting knn \
  --artifact-dir ml/body_measurement/artifacts/classic \
  --height 170 \
  --weight 65
```

정상이라면 모델별 평균 성능과 입력값 예측 결과가 출력된다.

결과 파일:

```text
ml/body_measurement/artifacts/classic/metrics.json
ml/body_measurement/artifacts/classic/sample_predictions.json
ml/body_measurement/artifacts/classic/run_manifest.json
```

---

## 09. Nori 테스트

Nori는 HuggingFace 후보 중 가장 가볍게 먼저 테스트하기 좋다.

설치:

```bash
pip install synthefy-nori
```

설치 확인:

```bash
python -c "from synthefy_nori import NoriRegressor; print('nori ok')"
```

실행:

```bash
python ml/body_measurement/benchmark.py benchmark \
  --data local/sizekorea/sizekorea_measurements_clean.csv \
  --models nori \
  --artifact-dir ml/body_measurement/artifacts/nori \
  --height 170 \
  --weight 65
```

Nori는 GPU가 있으면 GPU를 사용하고, 없으면 CPU로 fallback한다.

아래 메시지가 나오면 CPU로 실행 중이라는 뜻이다.

```text
Mixed precision is not supported for CPU inference, so it has been automatically disabled
```

GPU 서버에서 이 메시지가 계속 나온다면 `torch.cuda.is_available()`를 다시 확인한다.

---

## 10. TabPFN-v2 테스트

TabPFN은 CPU에서도 동작할 수 있지만 데이터가 커지면 매우 느리다. GPU 실행을 권장한다.

설치:

```bash
pip install -U tabpfn
```

설치 확인:

```bash
python -c "from tabpfn import TabPFNRegressor; print('tabpfn ok')"
```

실행:

```bash
python ml/body_measurement/benchmark.py benchmark \
  --data local/sizekorea/sizekorea_measurements_clean.csv \
  --models tabpfn_v2 \
  --artifact-dir ml/body_measurement/artifacts/tabpfn_v2 \
  --height 170 \
  --weight 65
```

첫 실행은 모델 체크포인트를 다운로드하므로 시간이 오래 걸릴 수 있다.

TabPFN 관련 오류가 나면 먼저 아래를 확인한다.

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

---

## 11. AutoGluon TabPFNMix 테스트

TabPFNMix는 의존성이 가장 무겁다. Nori와 TabPFN-v2가 정상 실행된 뒤 마지막에 테스트한다.

설치:

```bash
pip install autogluon
```

설치 확인:

```bash
python -c "from autogluon.tabular import TabularPredictor; print('autogluon ok')"
```

실행:

```bash
python ml/body_measurement/benchmark.py benchmark \
  --data local/sizekorea/sizekorea_measurements_clean.csv \
  --models tabpfn_mix \
  --artifact-dir ml/body_measurement/artifacts/tabpfn_mix \
  --height 170 \
  --weight 65
```

AutoGluon은 설치 파일과 의존성이 커서 별도 가상환경에서 테스트하는 것이 안전하다.

---

## 12. 전체 모델 한 번에 비교

각 모델이 단독 실행에 성공한 뒤 전체 비교를 실행한다.

```bash
python ml/body_measurement/benchmark.py benchmark \
  --data local/sizekorea/sizekorea_measurements_clean.csv \
  --models random_forest hist_gradient_boosting knn nori tabpfn_v2 tabpfn_mix \
  --artifact-dir ml/body_measurement/artifacts/all_models \
  --height 170 \
  --weight 65
```

같은 `artifact-dir`로 여러 실험을 동시에 돌리면 결과 파일이 덮어써질 수 있다.

병렬 실행이 필요하면 모델마다 `artifact-dir`를 다르게 지정한다.

---

## 13. 결과 보는 법

터미널에는 모델별 평균 성능이 출력된다.

```text
model  mean_mae  mean_rmse  mean_p90_error  fit_seconds  predict_ms_per_row
```

기준:

1. `mean_mae`는 낮을수록 좋다.
2. `mean_rmse`는 낮을수록 좋다.
3. `mean_p90_error`는 낮을수록 좋다.
4. `fit_seconds`는 학습 또는 context 준비 시간이다.
5. `predict_ms_per_row`는 한 사람 예측에 걸리는 평균 시간이다.

상세 결과는 아래 파일에서 확인한다.

```text
metrics.json
sample_predictions.json
run_manifest.json
```

`metrics.json`은 모델별, target별 상세 지표다.

`sample_predictions.json`은 `--height`, `--weight`로 넣은 샘플 입력의 예측값이다.

`run_manifest.json`은 어떤 데이터와 설정으로 실행했는지 기록한다.

---

## 14. 최종 판단 기준

최종 모델은 정확도만 보고 고르지 않는다.

아래 기준을 같이 본다.

| 기준 | 확인 항목 |
|---|---|
| 정확도 | `mean_mae`, `mean_rmse`, `mean_p90_error` |
| 속도 | `predict_ms_per_row` |
| 실행 안정성 | GPU에서 재실행해도 실패하지 않는지 |
| 설치 난이도 | 의존성 충돌이 적은지 |
| 배포 가능성 | Docker 이미지 크기와 라이선스 |
| 라이선스 | 상용/프로젝트 배포에 문제가 없는지 |

현재 기본 모델 중에는 `hist_gradient_boosting`이 가장 좋은 후보였다.

HuggingFace 모델은 GPU에서 같은 데이터와 같은 지표로 비교한 뒤 최종 후보 여부를 판단한다.

---

## 15. 자주 생기는 문제

### GPU가 안 잡힘

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

`False`이면 CUDA가 되는 PyTorch가 설치되지 않았거나, 컨테이너가 GPU를 못 보고 있는 상태다.

### HuggingFace 다운로드가 느림

처음 실행은 모델 가중치를 다운로드한다.

캐시 경로를 고정해두면 다음 실행부터 다시 받지 않는다.

```bash
export HF_HOME="$PWD/.cache/huggingface"
```

### 같은 실험 결과가 덮어써짐

실험마다 `--artifact-dir`를 다르게 지정한다.

```bash
--artifact-dir ml/body_measurement/artifacts/nori
```

### CPU mixed precision 경고

```text
Mixed precision is not supported for CPU inference
```

CPU에서 실행 중이라는 뜻이다. GPU 서버라면 PyTorch CUDA 인식부터 확인한다.

---

## 16. 참고 링크

1. Nori HuggingFace: https://huggingface.co/Synthefy/Nori
2. TabPFN 공식 Quickstart: https://docs.priorlabs.ai/quickstart
3. TabPFN GitHub: https://github.com/PriorLabs/TabPFN
4. AutoGluon 설치 문서: https://auto.gluon.ai/stable/install.html
