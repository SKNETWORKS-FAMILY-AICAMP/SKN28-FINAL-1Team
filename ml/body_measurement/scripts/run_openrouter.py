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
PROMPT_PATH = PROJECT_ROOT / "prompts" / "body_measurement_prompt.j2"
SCHEMA_PATH = PROJECT_ROOT / "prompts" / "body_measurement_schema.json"
TRAILING_METADATA_COLUMNS = [
    "front_image_path",
    "side_image_path",
    "model",
    "run_name",
    "status",
]


MEASUREMENT_COLUMNS = [
    "subject_id",
    "predicted_chest_cm",
    "predicted_waist_cm",
    "predicted_hip_cm",
    "chest",
    "waist",
    "hip",
    "chest_absolute_error_cm",
    "waist_absolute_error_cm",
    "hip_absolute_error_cm",
]


def order_result_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    preferred = [column for column in MEASUREMENT_COLUMNS if column in dataframe.columns]
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


def render_prompt(row: pd.Series) -> str:
    template = Environment(undefined=StrictUndefined).from_string(
        PROMPT_PATH.read_text(encoding="utf-8")
    )
    return template.render(
        gender=row["gender"],
        height_cm=float(row["height"]),
        weight_kg=float(row["weight"]),
    )


def parse_prediction(content: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    prediction = json.loads(cleaned)

    required_keys = {"chest_cm", "waist_cm", "hip_cm"}
    missing_keys = required_keys - set(prediction)
    if missing_keys:
        raise ValueError(f"응답에 필수 키가 없습니다: {sorted(missing_keys)}")

    return prediction


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
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY가 없습니다. Infisical 실행 여부를 확인하세요."
        )

    dataset_path = DATA_DIR / f"vlm_{args.split}_set.csv"
    df = pd.read_csv(dataset_path)
    if args.limit:
        df = df.head(args.limit)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    model_file_name = args.model.rsplit("/", maxsplit=1)[-1]
    output_path = results_dir / f"{model_file_name}_{args.split}_predictions_{args.run_name}.csv"

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
            "status": "success",
            "predicted_chest_cm": None,
            "predicted_waist_cm": None,
            "predicted_hip_cm": None,
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
            prompt = render_prompt(row)
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

            prediction = parse_prediction(content)
            usage = response_data.get("usage", {})
            record["predicted_chest_cm"] = prediction["chest_cm"]
            record["predicted_waist_cm"] = prediction["waist_cm"]
            record["predicted_hip_cm"] = prediction["hip_cm"]
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


if __name__ == "__main__":
    main()






