"""API 서버가 호출하는 신체치수 추론 인터페이스.

추론 경로는 두 개지만, 둘 다 새 11개 저장 항목을 채운 같은 형태의 dict를 반환한다.

- ``estimate_from_basic``  : 성별·키·몸무게 → HistGradientBoosting 11개 항목 예측
- ``estimate_from_photos`` : 사진 VLM의 길이 예측에서 비율을 계산

사진 VLM은 저장할 치수와 비율 계산용 길이를 함께 요청한다. 기존 결과는 허벅지·종아리
둘레와 팔뚝둘레를 사용했으므로 새 길이 정의의 평가에 재사용하지 않는다.

학습 코드(``benchmark.py``)와 달리 이 모듈은 서빙 전용이다. 모델을 하나만 lazy 로드하고
CLI·S3·학습 의존성을 갖지 않는다. 상수는 학습 시점
``data/hist/manifest.json``
값과 반드시 일치해야 한다.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import time
import threading
from pathlib import Path

import joblib
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 학습 시점과 동일해야 하는 값들 (data/hist/manifest.json / retrain_11targets.py 기준).
# 순서가 어긋나면 예외 없이 조용히 틀린 숫자가 나오므로 임의로 바꾸지 않는다.
FEATURES = ["gender", "height", "weight"]
TARGETS = [
    "shoulder",
    "chest",
    "waist",
    "hip",
    "thigh_length",
    "calf_length",
    "torso_length",
    "leg_length",
    "neck_length",
    "thigh_calf_ratio",
    "torso_leg_ratio",
]
GENDER_CODES = {"M": 0.0, "F": 1.0}
GENDER_ALIASES = {
    "M": "M",
    "F": "F",
    "MALE": "M",
    "FEMALE": "F",
    "남": "M",
    "여": "F",
    "남성": "M",
    "여성": "F",
}
GENDER_PUBLIC_LABELS = {"M": "male", "F": "female"}

# 사진 VLM에게 직접 물어보는 값. 비율은 응답값을 저장하지 않고 서버에서 계산한다.
PHOTO_MEASUREMENT_TARGETS = [
    "shoulder",
    "chest",
    "waist",
    "hip",
    "thigh_length",
    "calf_length",
    "torso_length",
    "leg_length",
    "neck_length",
]
PHOTO_SUPPORT_TARGETS = ["torso_length", "leg_length"]
PHOTO_TARGETS = TARGETS
PHOTO_RESPONSE_TARGETS = PHOTO_MEASUREMENT_TARGETS

# SizeKorea 기준 참고 분포. 저장 실패 조건이 아니라 해석·문서화 기준으로만 쓴다.
RATIO_REFERENCE_RANGES = {
    "thigh_calf_ratio": (0.506, 1.026),
    "torso_leg_ratio": (0.339, 0.920),
}

# 학습 데이터(SizeKorea) 범위를 벗어난 입력은 KNN이 외삽하지 못해 신뢰할 수 없다.
HEIGHT_RANGE_CM = (100.0, 230.0)
WEIGHT_RANGE_KG = (25.0, 300.0)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# 서빙은 새 11개 저장 항목을 물어보는 _full 프롬프트를 쓴다.
PROMPT_PATH = PROJECT_ROOT / "prompts" / "body_measurement_prompt_full.j2"
SCHEMA_PATH = PROJECT_ROOT / "prompts" / "body_measurement_schema_full.json"

# 서빙 모델은 새 11개 target으로 학습한 hist_gradient_boosting이다.
# ⚠️ 이 아티팩트는 scikit-learn 1.8.0으로 저장됐고, 1.9.0에서 열면
#    ModuleNotFoundError: No module named '_loss'로 실패한다. 실행 환경의
#    scikit-learn은 반드시 1.8.0으로 고정해야 한다 (api/requirements.txt).
DEFAULT_MODEL_PATH = PROJECT_ROOT / "data" / "hist" / "models" / "hist_gradient_boosting_11targets.joblib"
# 사진 기반 서빙 모델. validation 39명에서 평균 MAE 2.757cm로 후보 중 가장 정확했다
# (Qwen 3.597 / Grok 3.441 / Gemini 3.962). 호출당 $0.004492로 Qwen보다 약 30배
# 비싸지만 정확도를 우선한다.
DEFAULT_VLM_MODEL = "moonshotai/kimi-k2.5"

_model = None
_model_lock = threading.Lock()


class BodyEstimationError(Exception):
    """추론 입력이 잘못됐거나 추론에 실패했을 때."""


def _model_path() -> Path:
    """서빙에 쓸 joblib 경로. 배포 환경에서는 환경변수로 주입한다.

    ``artifacts/models/*.joblib``은 .gitignore 대상이라 클론만으로는 파일이 없다.
    AWS에서는 S3에서 내려받은 경로를 BODY_MODEL_PATH로 지정해야 한다.
    """
    return Path(os.getenv("BODY_MODEL_PATH") or DEFAULT_MODEL_PATH)


def load_model():
    """추론 모델을 한 번만 로드해서 재사용한다 (프로세스당 1회)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                path = _model_path()
                if not path.exists():
                    raise BodyEstimationError(
                        f"신체치수 추정 모델 파일이 없습니다: {path}. "
                        "BODY_MODEL_PATH 환경변수를 확인하세요."
                    )
                _model = joblib.load(path)
    return _model


def normalize_gender(gender: str) -> str:
    """'male'/'남성'/'M' 등 표기 차이를 학습 때 쓴 'M'/'F'로 맞춘다."""
    key = str(gender).strip().upper()
    normalized = GENDER_ALIASES.get(key)
    if normalized is None:
        raise BodyEstimationError(f"성별은 male 또는 female이어야 합니다: {gender!r}")
    return normalized


def public_gender(gender: str) -> str:
    """API/Swagger/VLM 프롬프트에 노출할 성별 표기는 male/female로 통일한다."""
    return GENDER_PUBLIC_LABELS[normalize_gender(gender)]


def _build_features(gender: str, height: float, weight: float) -> pd.DataFrame:
    """모델 입력 1행을 만든다. 학습 때와 같은 컬럼명·순서를 유지한다."""
    try:
        height = float(height)
        weight = float(weight)
    except (TypeError, ValueError) as error:
        raise BodyEstimationError("키와 몸무게는 숫자여야 합니다.") from error

    if not HEIGHT_RANGE_CM[0] <= height <= HEIGHT_RANGE_CM[1]:
        raise BodyEstimationError(
            f"키는 {HEIGHT_RANGE_CM[0]:.0f}~{HEIGHT_RANGE_CM[1]:.0f}cm 사이여야 합니다."
        )
    if not WEIGHT_RANGE_KG[0] <= weight <= WEIGHT_RANGE_KG[1]:
        raise BodyEstimationError(
            f"몸무게는 {WEIGHT_RANGE_KG[0]:.0f}~{WEIGHT_RANGE_KG[1]:.0f}kg 사이여야 합니다."
        )

    return pd.DataFrame(
        [
            {
                "gender": GENDER_CODES[normalize_gender(gender)],
                "height": height,
                "weight": weight,
            }
        ],
        columns=FEATURES,
    )


def estimate_from_basic(gender: str, height: float, weight: float) -> dict[str, float]:
    """성별·키·몸무게로 11개 부위/비율을 추정한다."""
    features = _build_features(gender, height, weight)
    predicted = load_model().predict(features)[0]
    
    measurements = {
        target: round(float(value), 3 if target.endswith("_ratio") else 1)
        for target, value in zip(TARGETS, predicted, strict=True)
    }
    return measurements


def _safe_ratio(numerator: float, denominator: float, field_name: str) -> float:
    """VLM이 준 기준 길이 2개로 저장용 비율을 계산한다."""
    if denominator <= 0:
        raise BodyEstimationError(f"{field_name} 계산에 필요한 분모가 0 이하입니다.")
    ratio = numerator / denominator
    if not math.isfinite(ratio):
        raise BodyEstimationError(f"{field_name} 계산 결과가 유효하지 않습니다.")
    return round(ratio, 3)


# ---------------------------------------------------------------------------
# 사진 기반 (VLM)
# ---------------------------------------------------------------------------


def _render_prompt(gender: str, height: float, weight: float) -> str:
    """평가 때 쓴 프롬프트를 그대로 재사용한다.

    벤치마크와 서빙이 다른 프롬프트를 쓰면 측정한 MAE가 운영 성능을 설명하지 못한다.
    """
    from jinja2 import Environment, StrictUndefined

    template = Environment(undefined=StrictUndefined).from_string(
        PROMPT_PATH.read_text(encoding="utf-8")
    )
    prompt = template.render(
        gender=public_gender(gender),
        height_cm=float(height),
        weight_kg=float(weight),
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return prompt + "\n\nRequired JSON schema:\n" + json.dumps(schema)


def _image_part(image_bytes: bytes) -> dict:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
    }


def _parse_prediction(content: str) -> dict[str, float]:
    """모델 응답 JSON에서 부위별 수치를 꺼낸다. 코드펜스로 감싸서 오는 경우가 있다.

    필수 측정값 중 하나라도 빠지거나 숫자가 아니면 실패로 본다. 사진 응답을
    무사진 모델의 임시값으로 조용히 대체하지 않는다.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise BodyEstimationError(f"모델 응답을 JSON으로 읽지 못했습니다: {error}") from error
    if not isinstance(payload, dict):
        raise BodyEstimationError("모델 응답은 JSON 객체여야 합니다.")

    missing = []
    for target in PHOTO_RESPONSE_TARGETS:
        key_name = f"{target}_cm"
        if key_name not in payload:
            missing.append(key_name)
    if missing:
        raise BodyEstimationError(f"모델 응답에 필수 키가 없습니다: {missing}")

    predicted: dict[str, float] = {}
    support: dict[str, float] = {}
    for target in PHOTO_RESPONSE_TARGETS:
        key_name = f"{target}_cm"
        value = payload.get(key_name)
        try:
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError("finite number required")
            predicted[target] = round(numeric, 1)
            if target in PHOTO_SUPPORT_TARGETS:
                support[target] = numeric
        except (TypeError, ValueError):
            raise BodyEstimationError(
                f"모델이 {key_name} 값을 숫자로 주지 않았습니다: {value!r}"
            ) from None
    predicted["thigh_calf_ratio"] = _safe_ratio(
        predicted["thigh_length"], predicted["calf_length"], "thigh_calf_ratio"
    )
    predicted["torso_leg_ratio"] = _safe_ratio(
        predicted["torso_length"], predicted["leg_length"], "torso_leg_ratio"
    )
    return predicted


def _call_vlm(prompt: str, front_image: bytes, side_image: bytes) -> str:
    """OpenRouter로 사진 2장을 보내고 응답 본문을 받는다.

    벤치마크와 동일하게, 응답이 길이 제한으로 잘렸을 때만 토큰을 늘려 한 번 재시도한다
    (검증 39명 중 1건이 이 경우였다).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise BodyEstimationError("OPENROUTER_API_KEY가 설정되지 않았습니다.")

    model = os.getenv("BODY_VLM_MODEL") or DEFAULT_VLM_MODEL
    timeout = float(os.getenv("BODY_VLM_TIMEOUT_SECONDS", "90"))
    max_retries = int(os.getenv("BODY_VLM_MAX_RETRIES", "3"))
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_finish_reason = None
    for max_tokens in (256, 512):
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        _image_part(front_image),
                        _image_part(side_image),
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "reasoning": {"effort": "none"},
            "response_format": {"type": "json_object"},
        }
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    OPENROUTER_URL, headers=headers, json=payload, timeout=timeout
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < max_retries:
                    time.sleep(min(attempt, 3))
                continue

            if response.ok:
                break
            last_error = BodyEstimationError(
                f"VLM 호출 실패 (HTTP {response.status_code})"
            )
            if response.status_code < 500 or attempt == max_retries:
                raise last_error
            time.sleep(min(attempt, 3))
        else:
            raise BodyEstimationError(f"VLM 호출 실패: {last_error}") from last_error

        choice = response.json()["choices"][0]
        content = choice["message"].get("content")
        if content:
            return content
        last_finish_reason = choice.get("finish_reason")
        if last_finish_reason != "length":
            break

    raise BodyEstimationError(
        f"모델이 응답 본문을 반환하지 않았습니다 (finish_reason={last_finish_reason})."
    )


def estimate_from_photos(
    gender: str,
    height: float,
    weight: float,
    front_image: bytes,
    side_image: bytes,
) -> dict[str, float]:
    """사진 2장 + 기본 정보로 상세 치수·체형 지표를 추정한다.

    VLM이 필수 길이값을 모두 반환해야 성공한다. 누락 시 기본 정보의 임시 수치로
    대체하지 않고 오류를 반환한다.
    반환 형태는
    ``estimate_from_basic``과 완전히 같아서 API 응답 스키마가 갈라지지 않는다.
    """
    prompt = _render_prompt(gender, height, weight)
    content = _call_vlm(prompt, front_image, side_image)
    return _parse_prediction(content)
