import argparse
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from jinja2 import Environment, StrictUndefined


API_URL = "https://openrouter.ai/api/v1/chat/completions"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "splits"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# 모델 선정 벤치마크 기준 부위. 응답에 없으면 실패로 본다.
CORE_TARGETS = ["chest", "waist", "hip"]
# 서빙에서 실제로 쓰는 7개. SizeKorea 라벨이 있는 행은 7개 모두 채점할 수 있다.
FULL_TARGETS = [*CORE_TARGETS, "thigh", "calf", "arm", "shoulder"]

# core: 모델 선정 벤치마크에 쓴 3개짜리. MODEL_EVALUATION_SUMMARY.md의 MAE를
#       재현하려면 이걸 써야 하므로 기본값으로 둔다.
# full: 서빙과 동일한 7개짜리. 서빙 성능을 재려면 이걸 쓴다.
PROMPT_SETS = {
    "core": {
        "targets": CORE_TARGETS,
        "prompt": PROMPTS_DIR / "body_measurement_prompt.j2",
        "schema": PROMPTS_DIR / "body_measurement_schema.json",
    },
    "full": {
        "targets": FULL_TARGETS,
        "prompt": PROMPTS_DIR / "body_measurement_prompt_full.j2",
        "schema": PROMPTS_DIR / "body_measurement_schema_full.json",
    },
}

TRAILING_METADATA_COLUMNS = [
    "front_image_path",
    "side_image_path",
    "model",
    "run_name",
    "prompt_set",
    "status",
]


def measurement_columns() -> list[str]:
    """예측값 → 정답값 → 오차 순으로 보이도록 앞쪽 열 순서를 만든다."""
    return [
        "subject_id",
        *[f"predicted_{target}_cm" for target in FULL_TARGETS],
        *FULL_TARGETS,
        *[f"{target}_absolute_error_cm" for target in FULL_TARGETS],
    ]


def order_result_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    preferred = [column for column in measurement_columns() if column in dataframe.columns]
    trailing = [
        column for column in TRAILING_METADATA_COLUMNS if column in dataframe.columns
    ]
    middle = [
        column
        for column in dataframe.columns
        if column not in preferred and column not in trailing
    ]
    return dataframe[preferred + middle + trailing]



def load_image_part(image_path: Path) -> dict:
    encoded_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
    }


def render_prompt(row: pd.Series, prompt_path: Path) -> str:
    template = Environment(undefined=StrictUndefined).from_string(
        prompt_path.read_text(encoding="utf-8")
    )
    return template.render(
        gender=row["gender"],
        height_cm=float(row["height"]),
        weight_kg=float(row["weight"]),
    )


def parse_prediction(content: str, targets: list[str]) -> dict:
    """응답 JSON에서 부위별 수치를 꺼낸다.

    CORE_TARGETS는 채점에 쓰므로 없으면 실패 처리한다. 나머지 부위는 모델이
    빠뜨려도 실패로 보지 않고 빈 값으로 남긴다 — 채점 대상이 아니기 때문이다.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    prediction = json.loads(cleaned)

    missing_keys = [f"{t}_cm" for t in CORE_TARGETS if f"{t}_cm" not in prediction]
    if missing_keys:
        raise ValueError(f"응답에 필수 키가 없습니다: {missing_keys}")

    return {target: prediction.get(f"{target}_cm") for target in targets}


def request_prediction(
    *, model: str, prompt: str, front_path: Path, side_path: Path, headers: dict
) -> tuple[dict, str]:
    """Retry once with more output space only when the response is truncated."""
    last_response_data = None
    for max_tokens in (256, 512):
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        load_image_part(front_path),
                        load_image_part(side_path),
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "reasoning": {"effort": "none"},
            "response_format": {"type": "json_object"},
        }
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text}")

        response_data = response.json()
        choice = response_data["choices"][0]
        content = choice["message"].get("content")
        last_response_data = response_data
        if content:
            return response_data, content
        if choice.get("finish_reason") != "length":
            break

    return last_response_data, ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--run-name", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="결과 저장 폴더. 생략하면 experiments/vlm/<model>/<split>-<run-name>입니다.",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--prompt-set",
        choices=sorted(PROMPT_SETS),
        default="core",
        help=(
            "core=가슴·허리·엉덩이 3개만 질문 (모델 선정 벤치마크 재현용, 기본값). "
            "full=서빙과 동일하게 7개 전부 질문."
        ),
    )
    args = parser.parse_args()

    prompt_set = PROMPT_SETS[args.prompt_set]
    targets = prompt_set["targets"]

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY가 없습니다. Infisical 실행 여부를 확인하세요."
        )

    dataset_path = DATA_DIR / f"vlm_{args.split}_set.csv"
    df = pd.read_csv(dataset_path)
    if args.limit:
        df = df.head(args.limit)

    schema = json.loads(prompt_set["schema"].read_text(encoding="utf-8"))
    model_file_name = args.model.rsplit("/", maxsplit=1)[-1]
    results_dir = args.output_dir or (
        PROJECT_ROOT
        / "experiments"
        / "vlm"
        / model_file_name
        / f"{args.split}-{args.run_name}"
    )
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / "predictions.csv"

    results = []
    if args.resume and output_path.exists():
        existing = pd.read_csv(output_path)
        successful = existing[existing["status"] == "success"].copy()
        completed_ids = set(successful["subject_id"])
        results = successful.to_dict("records")
        df = df[~df["subject_id"].isin(completed_ids)].copy()
        print(f"재개: 성공 {len(successful)}명 유지, {len(df)}명 호출 예정")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for _, row in df.iterrows():
        start_time = time.perf_counter()
        record = {
            "subject_id": row["subject_id"],
            "front_image_path": row["front_image_path"],
            "side_image_path": row["side_image_path"],
            "model": args.model,
            "run_name": args.run_name,
            "prompt_set": args.prompt_set,
            "status": "success",
            **{f"predicted_{target}_cm": None for target in targets},
            "latency_seconds": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "actual_cost_usd": None,
            "raw_response": None,
            "error_message": None,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        try:
            prompt = render_prompt(row, prompt_set["prompt"])
            prompt += "\n\nRequired JSON schema:\n" + json.dumps(schema)
            front_path = REPO_ROOT / row["front_image_path"]
            side_path = REPO_ROOT / row["side_image_path"]

            response_data, content = request_prediction(
                model=args.model,
                prompt=prompt,
                front_path=front_path,
                side_path=side_path,
                headers=headers,
            )
            record["raw_response"] = content or json.dumps(response_data, ensure_ascii=False)
            if not content:
                raise ValueError("모델이 최종 텍스트 응답을 반환하지 않았습니다.")

            prediction = parse_prediction(content, targets)
            usage = response_data.get("usage", {})
            for target in targets:
                record[f"predicted_{target}_cm"] = prediction[target]
            record["prompt_tokens"] = usage.get("prompt_tokens")
            record["completion_tokens"] = usage.get("completion_tokens")
            record["total_tokens"] = usage.get("total_tokens")
            record["actual_cost_usd"] = usage.get("cost")

        except Exception as error:
            record["status"] = "failed"
            record["error_message"] = str(error)

        record["latency_seconds"] = round(time.perf_counter() - start_time, 3)
        results.append(record)
        order_result_columns(pd.DataFrame(results)).to_csv(output_path, index=False)
        print(
            f'{record["subject_id"]}: '
            f'{record["status"]} ({record["latency_seconds"]}초)'
        )

    print(f"\n결과 저장 완료: {output_path}")

    # 여기서는 호출 직후 응답률만 보여준다. 정확도는 evaluate_results.py가
    # 라벨 CSV와 병합해서 계산한다.
    extra_targets = [t for t in targets if t not in CORE_TARGETS]
    if extra_targets:
        frame = pd.DataFrame(results)
        success = frame[frame["status"] == "success"]
        print(f"\n추가 부위 응답률 (성공 {len(success)}건 기준):")
        for target in extra_targets:
            filled = success[f"predicted_{target}_cm"].notna().sum()
            print(f"  {target:9s} {filled}/{len(success)}")


if __name__ == "__main__":
    main()






