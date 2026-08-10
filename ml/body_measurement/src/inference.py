"""API 서버가 호출하는 신체치수 추론 인터페이스.

추론 경로는 두 개지만, 둘 다 7개 부위를 모두 채운 같은 형태의 dict를 반환한다.

- ``estimate_from_basic``  : 성별·키·몸무게 → 표 기반 모델이 7개 예측
- ``estimate_from_photos`` : 위 7개를 만든 뒤, 사진 VLM 응답으로 덮어씀

사진 VLM은 7개를 다 물어본다. 초기 모델 비교는 비용을 아끼려고
가슴·허리·엉덩이 3개만 채점했지만, SizeKorea 기반 VLM 라벨에는
허벅지·장딴지·팔·어깨 정답도 복구되어 오프라인 평가는 7개 모두 가능하다.

학습 코드(``benchmark.py``)와 달리 이 모듈은 서빙 전용이다. 모델을 하나만 lazy 로드하고
CLI·S3·학습 의존성을 갖지 않는다. 상수는 학습 시점
``experiments/tabular/_datasets/sizekorea-1000-v1/run_manifest.json``
값과 반드시 일치해야 한다.
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
from pathlib import Path

import joblib
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 학습 시점과 동일해야 하는 값들 (run_manifest.json / benchmark.py 기준).
# 순서가 어긋나면 예외 없이 조용히 틀린 숫자가 나오므로 임의로 바꾸지 않는다.
FEATURES = ["gender", "height", "weight"]
TARGETS = ["chest", "waist", "hip", "thigh", "calf", "arm", "shoulder"]
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

# 사진 VLM에게 물어보고 최종 API에서 제공할 부위 = 7대 부위 + 3대 비율
PHOTO_TARGETS = TARGETS + ["neck_length", "thigh_calf_ratio", "torso_leg_ratio"]
# 응답에 이 값이 없으면 사진 추정이 실패한 것으로 본다.
PHOTO_CORE_TARGETS = ["chest", "waist", "hip"]

# 학습 데이터(SizeKorea) 범위를 벗어난 입력은 KNN이 외삽하지 못해 신뢰할 수 없다.
HEIGHT_RANGE_CM = (100.0, 230.0)
WEIGHT_RANGE_KG = (25.0, 300.0)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# 서빙은 7개를 다 물어보는 _full 프롬프트를 쓴다.
# 모델 선정 벤치마크(scripts/run_openrouter.py)는 비용을 아끼려고 3개만 묻는
# body_measurement_prompt.j2를 쓰며, 기록된 MAE를 재현할 수 있도록 그대로 둔다.
PROMPT_PATH = PROJECT_ROOT / "prompts" / "body_measurement_prompt_full.j2"
SCHEMA_PATH = PROJECT_ROOT / "prompts" / "body_measurement_schema_full.json"

# 서빙 모델은 hist_gradient_boosting이다.
# ⚠️ 이 아티팩트는 scikit-learn 1.8.0으로 저장됐고, 1.9.0에서 열면
#    ModuleNotFoundError: No module named '_loss'로 실패한다. 실행 환경의
#    scikit-learn은 반드시 1.8.0으로 고정해야 한다 (api/requirements.txt).
DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "models" / "hist_gradient_boosting.joblib"
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


def calculate_ratios(gender: str, height: float, weight: float) -> dict[str, float]:
    """성별, 키, 몸무게에 기반한 3대 비율(목길이, 허벅지/종아리 비율, 상하체 비율)을 계산합니다.
    계수는 SizeKorea 8차 데이터를 바탕으로 산출된 다중선형회귀 모델의 값입니다.
    """
    g = normalize_gender(gender) # 'M' 또는 'F'
    h = float(height)
    w = float(weight)

    if g == "M":
        # 남성 공식 (시각적 목길이 = 키 - 머리수직길이 - 어깨가쪽높이 기준)
        neck_len = -9.345006493457939 + (0.13157641423182745 * h) + (-0.05935597499347307 * w)
        thigh_calf = 0.34071454583431354 + (0.002875852241576988 * h) + (-0.001736836913080183 * w)
        torso_leg = 2.119090085171346 + (-0.0060599959727511065 * h) + (0.002248838082996495 * w)
    else:
        # 여성 공식 (시각적 목길이 = 키 - 머리수직길이 - 어깨가쪽높이 기준)
        neck_len = -4.570591870215094 + (0.09709096211820346 * h) + (-0.05189601246843043 * w)
        thigh_calf = 0.4356590685473226 + (0.0025675121752655396 * h) + (-0.0017664083698426172 * w)
        torso_leg = 1.8783480592799626 + (-0.0047122865308593135 * h) + (0.0018165824663871851 * w)

    return {
        "neck_length": round(neck_len, 1),
        "thigh_calf_ratio": round(thigh_calf, 3),
        "torso_leg_ratio": round(torso_leg, 3)
    }


def estimate_from_basic(gender: str, height: float, weight: float) -> dict[str, float]:
    """성별·키·몸무게로 10개 부위/비율을 추정한다. 값은 cm 또는 비율 단위."""
    features = _build_features(gender, height, weight)
    predicted = load_model().predict(features)[0]
    
    measurements = {
        target: round(float(value), 1)
        for target, value in zip(TARGETS, predicted, strict=True)
    }
    
    # 3대 비율 추가 연산 병합
    ratios = calculate_ratios(gender, height, weight)
    measurements.update(ratios)
    return measurements


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
        gender=normalize_gender(gender),
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

    핵심 3개(가슴·허리·엉덩이)는 없으면 실패로 본다. 나머지 4개는 모델이
    빠뜨리거나 숫자가 아니면 조용히 건너뛰고, 호출부가 기본 정보 추정값을
    그대로 쓰게 한다 — 사진 한 장 때문에 응답에 빈칸이 생기면 안 된다.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise BodyEstimationError(f"모델 응답을 JSON으로 읽지 못했습니다: {error}") from error

    missing = [
        f"{target}_cm" for target in PHOTO_CORE_TARGETS if f"{target}_cm" not in payload
    ]
    if missing:
        raise BodyEstimationError(f"모델 응답에 필수 키가 없습니다: {missing}")

    predicted: dict[str, float] = {}
    for target in PHOTO_TARGETS:
        # 비율 지표들은 _cm을 붙이지 않고 본 명칭 그대로 조회
        if target.endswith("_ratio"):
            key_name = target
        else:
            key_name = f"{target}_cm"
            
        value = payload.get(key_name)
        try:
            # 비율 지표는 소수점 3자리까지, 치수 지표는 1자리까지 정밀도를 유지
            precision = 3 if target.endswith("_ratio") else 1
            predicted[target] = round(float(value), precision)
        except (TypeError, ValueError):
            if target in PHOTO_CORE_TARGETS:
                raise BodyEstimationError(
                    f"모델이 {target} 값을 숫자로 주지 않았습니다: {value!r}"
                ) from None
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
    timeout = float(os.getenv("BODY_VLM_TIMEOUT_SECONDS", "120"))
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
        response = requests.post(
            OPENROUTER_URL, headers=headers, json=payload, timeout=timeout
        )
        if not response.ok:
            raise BodyEstimationError(
                f"VLM 호출 실패 (HTTP {response.status_code})"
            )

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
    """사진 2장 + 기본 정보로 7개 부위를 추정한다.

    기본 정보 추정으로 7개를 먼저 채운 뒤 VLM 응답으로 덮어쓴다. VLM이 7개를
    다 주면 전부 사진 기반 값이 되고, 일부를 빠뜨리면 그 부위만 기본 정보
    추정값이 남는다 — 어느 쪽이든 7칸이 비지 않는다. 반환 형태는
    ``estimate_from_basic``과 완전히 같아서 API 응답 스키마가 갈라지지 않는다.
    """
    measurements = estimate_from_basic(gender, height, weight)
    prompt = _render_prompt(gender, height, weight)
    content = _call_vlm(prompt, front_image, side_image)
    measurements.update(_parse_prediction(content))
    return measurements
