"""
20명 full body celebs VLM 벤치마크 (gpt-4o-mini).

- input: data/celebrities/celebrities_index.csv (20명)
- photos: data/celebrities/<sid>_front.jpg, <sid>_side.jpg
- output: reports/celebrities_vlm_benchmark_20.csv
"""
import os
import sys
import csv
import json
import time
import base64
from pathlib import Path

# openai
from openai import OpenAI

ROOT = Path("/Users/vosnuevo/Shared/workspaces/SKN28-FINAL-1Team")
ML_ROOT = ROOT / "ml/body_measurement"
CELEB_DIR = ML_ROOT / "data/celebrities"
INDEX_CSV = CELEB_DIR / "celebrities_index.csv"
OUT_DIR = ML_ROOT / "reports"
OUT_DIR.mkdir(exist_ok=True)

# .env 로드
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k] = v.strip("'\"")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not set"); sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)


def build_prompt(height, gender, weight):
    gender_full = "Female" if str(gender).upper().startswith("F") else "Male"
    return f"""You are an expert in anthropometry and visual body measurement from photos.

Analyze the provided full-body photo(s) of a real person (a Korean celebrity).

Known metadata:
- Height: {height} cm
- Gender: {gender_full}
- Weight: {weight} kg

Using the height as pixel-to-centimeter calibration anchor, estimate:
1. Chest circumference (가슴둘레) in cm — at the fullest part of the chest/bust
2. Waist circumference (허리둘레) in cm — at the narrowest torso point
3. Hip circumference (엉덩이둘레) in cm — at the fullest part of the hips/buttocks

Consider what the person is actually wearing — clothing can hide the true shape. If the body is partially obscured (e.g., baggy clothing), state your best estimate based on visible cues (limb thickness, posture, face/body proportions).

Output strictly as JSON with keys: "chest", "waist", "hip". Floating-point numbers in cm. No explanations."""


def validate_image(p: Path) -> bool:
    from PIL import Image
    try:
        with Image.open(p) as im:
            return im.format.lower() in ("jpeg", "jpg", "png", "webp", "gif")
    except Exception:
        return False


def query_vlm(img_paths: list, prompt: str) -> dict:
    content = [{"type": "text", "text": prompt}]
    for p in img_paths:
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": content}],
        max_tokens=300,
    )
    text = response.choices[0].message.content
    return json.loads(text.strip())


def query_avg(front_p: Path, side_p: Path, prompt: str) -> dict:
    r_front = query_vlm([front_p], prompt)
    r_side = query_vlm([side_p], prompt)
    avg = {}
    for k in ("chest", "waist", "hip"):
        if k in r_front and k in r_side:
            avg[k] = (r_front[k] + r_side[k]) / 2
        elif k in r_front:
            avg[k] = r_front[k]
        else:
            avg[k] = r_side[k]
    return {"front": r_front, "side": r_side, "avg": avg}


def main():
    celebs = list(csv.DictReader(INDEX_CSV.open()))
    print(f"=== Celebs VLM Benchmark (full body) ===")
    print(f"model: {OPENAI_MODEL}")
    print(f"총 {len(celebs)}명\n")

    results = []
    for row in celebs:
        sid = row["subject_id"]
        front_p = CELEB_DIR / f"{sid}_front.jpg"
        side_p = CELEB_DIR / f"{sid}_side.jpg"

        if not front_p.exists() and not side_p.exists():
            print(f"  [SKIP] {sid}: no photo")
            continue

        # Validate
        if front_p.exists() and not validate_image(front_p):
            print(f"  [SKIP] {sid}: front invalid"); continue
        if side_p.exists() and not validate_image(side_p):
            print(f"  [SKIP] {sid}: side invalid"); continue

        # Actual measurements
        try:
            actual_chest = float(row["chest"])
            actual_waist = float(row["waist"])
            actual_hip = float(row["hip"])
        except (ValueError, TypeError):
            print(f"  [SKIP] {sid}: missing actual")
            continue

        prompt = build_prompt(row["height"], row["gender"], row["weight"])

        t0 = time.time()
        try:
            if front_p.exists() and side_p.exists():
                r = query_avg(front_p, side_p, prompt)
                pred_chest = r["avg"]["chest"]
                pred_waist = r["avg"]["waist"]
                pred_hip = r["avg"]["hip"]
                used_views = "front+side"
            elif front_p.exists():
                r = query_vlm([front_p], prompt)
                pred_chest, pred_waist, pred_hip = r["chest"], r["waist"], r["hip"]
                used_views = "front"
            else:
                r = query_vlm([side_p], prompt)
                pred_chest, pred_waist, pred_hip = r["chest"], r["waist"], r["hip"]
                used_views = "side"
        except Exception as e:
            print(f"  [ERR] {sid}: {e}")
            continue
        elapsed = time.time() - t0

        result = {
            "subject_id": sid,
            "gender": row["gender"],
            "height": row["height"],
            "weight": row["weight"],
            "bmi": row["bmi"],
            "category": row["category"],
            "views": used_views,
            "latency_sec": round(elapsed, 2),
            "pred_chest": round(pred_chest, 1),
            "pred_waist": round(pred_waist, 1),
            "pred_hip": round(pred_hip, 1),
            "actual_chest": actual_chest,
            "actual_waist": actual_waist,
            "actual_hip": actual_hip,
            "err_chest": round(pred_chest - actual_chest, 1),
            "err_waist": round(pred_waist - actual_waist, 1),
            "err_hip": round(pred_hip - actual_hip, 1),
        }
        results.append(result)

        print(f"  {sid:18s} {row['gender']} {float(row['height']):.0f}/{float(row['weight']):.0f}kg [{used_views:11s}] | "
              f"actual: C{actual_chest:.0f} W{actual_waist:.0f} H{actual_hip:.0f} | "
              f"pred: C{pred_chest:.0f} W{pred_waist:.0f} H{pred_hip:.0f} | "
              f"err: C{result['err_chest']:+.1f} W{result['err_waist']:+.1f} H{result['err_hip']:+.1f} ({elapsed:.1f}s)")

    out_csv = OUT_DIR / "celebrities_vlm_benchmark_20.csv"
    if results:
        keys = list(results[0].keys())
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(results)
        print(f"\nsaved: {out_csv}")

        # MAE
        if results:
            import statistics
            print(f"\n=== MAE (n={len(results)}) ===")
            for t in ["chest", "waist", "hip"]:
                errs = [abs(r[f"err_{t}"]) for r in results]
                biases = [r[f"err_{t}"] for r in results]
                print(f"  {t}: MAE={statistics.mean(errs):.2f}cm, bias={statistics.mean(biases):+.2f}cm")

            print(f"\n=== 카테고리별 MAE ===")
            from collections import defaultdict
            cat_data = defaultdict(list)
            for r in results:
                cat_data[r["category"]].append(r)
            for cat, rs in sorted(cat_data.items()):
                mae_c = statistics.mean(abs(r["err_chest"]) for r in rs)
                mae_w = statistics.mean(abs(r["err_waist"]) for r in rs)
                mae_h = statistics.mean(abs(r["err_hip"]) for r in rs)
                print(f"  {cat:20s} (n={len(rs)}): C={mae_c:.2f}, W={mae_w:.2f}, H={mae_h:.2f}")


if __name__ == "__main__":
    main()
