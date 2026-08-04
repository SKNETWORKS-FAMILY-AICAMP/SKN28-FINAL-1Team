"""
Celebrities VLM 벤치마크.

15명 한국 연예인에 대해:
  1. 첫 번째 전신 사진 선택
  2. OpenAI gpt-4o-mini로 가슴/허리/엉덩이 예측
  3. 실측값과 비교
  4. 부위별 MAE, BMI별 MAE 출력
"""
import os
import sys
import json
import base64
import time
import csv
from pathlib import Path
from openai import OpenAI
import pandas as pd

ROOT = Path("/Users/vosnuevo/Shared/workspaces/SKN28-FINAL-1Team")
CELEB_DIR = ROOT / "ml/body_measurement/data/celebrities"
INDEX_CSV = ROOT / "ml/body_measurement/data/celebrities_index.csv"
OUT_DIR = ROOT / "ml/body_measurement/reports"
OUT_DIR.mkdir(exist_ok=True)

# .env 수동 로드
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
    print("ERROR: OPENAI_API_KEY not set")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)


def build_prompt(height, gender, weight, source_note=""):
    gender_full = "Female" if str(gender).upper().startswith("F") else "Male"
    src = f"\nNote: {source_note}" if source_note else ""
    return f"""You are an expert in anthropometry and visual body measurement from photos.

Analyze the provided full-body photo of a real person (a Korean celebrity).

Known metadata:
- Height: {height} cm
- Gender: {gender_full}
- Weight: {weight} kg
{src}

Using the height as pixel-to-centimeter calibration anchor, estimate:
1. Chest circumference (가슴둘레) in cm — at the fullest part of the chest/bust
2. Waist circumference (허리둘레) in cm — at the narrowest torso point
3. Hip circumference (엉덩이둘레) in cm — at the fullest part of the hips/buttocks

Consider what the person is actually wearing — clothing can hide the true shape. If the body is partially obscured (e.g., baggy clothing), state your best estimate based on visible cues (limb thickness, posture, face/body proportions).

Output strictly as JSON with keys: "chest", "waist", "hip". Floating-point numbers in cm. No explanations."""


def pick_photos(celeb_dir: Path, name: str) -> tuple:
    """<name>_front.jpg, <name>_side.jpg를 찾아서 반환. 없으면 가장 큰 이미지."""
    from PIL import Image
    front_p = celeb_dir / f"{name}_front.jpg"
    side_p = celeb_dir / f"{name}_side.jpg"
    front = front_p if front_p.exists() else None
    side = side_p if side_p.exists() else None
    return front, side


def validate_image(p: Path) -> bool:
    """PIL로 OpenAI 호환 포맷 검증."""
    from PIL import Image
    try:
        with Image.open(p) as im:
            fmt = im.format.lower()
            return fmt in ("jpeg", "jpg", "png", "webp", "gif")
    except Exception:
        return False


def query_vlm(img_path: Path, prompt: str) -> dict:
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }],
        max_tokens=300,
    )
    text = response.choices[0].message.content
    return json.loads(text.strip())


def query_vlm_two(img_front: Path, img_side: Path, prompt_front: str, prompt_side: str) -> dict:
    """정면+측면 두 이미지를 보내고, 각 VLM 응답을 평균."""
    r_front = query_vlm(img_front, prompt_front)
    r_side = query_vlm(img_side, prompt_side)
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
    celebs = pd.read_csv(INDEX_CSV)
    print(f"=== Celebrities VLM Benchmark (front+side) ===")
    print(f"model: {OPENAI_MODEL}")
    print(f"총 {len(celebs)}명\n")

    results = []
    for _, row in celebs.iterrows():
        sid = row["subject_id"]
        celeb_path = CELEB_DIR / sid
        front_p, side_p = pick_photos(celeb_path, sid)

        # 둘 다 없으면 fallback
        if not front_p and not side_p:
            # 가장 큰 valid 이미지 1장 사용
            for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
                cands = list(celeb_path.glob(ext))
                cands = [p for p in cands if validate_image(p)]
                if cands:
                    front_p = max(cands, key=lambda p: p.stat().st_size)
                    break
            if not front_p:
                print(f"  [SKIP] {sid}: no photo")
                continue

        # 실측값
        try:
            actual_chest = float(row["chest"])
            actual_waist = float(row["waist"])
            actual_hip = float(row["hip"])
        except (ValueError, TypeError):
            actual_chest = actual_waist = actual_hip = None

        prompt = build_prompt(row["height"], row["gender"], row["weight"])

        # 정면만 / 측면만 / 둘 다
        t0 = time.time()
        try:
            if front_p and side_p and front_p.exists() and side_p.exists():
                r = query_vlm_two(front_p, side_p, prompt, prompt)
                pred_chest = r["avg"]["chest"]
                pred_waist = r["avg"]["waist"]
                pred_hip = r["avg"]["hip"]
                used_views = "front+side"
            elif front_p and front_p.exists():
                pred = query_vlm(front_p, prompt)
                pred_chest, pred_waist, pred_hip = pred["chest"], pred["waist"], pred["hip"]
                used_views = "front"
            else:
                pred = query_vlm(side_p, prompt)
                pred_chest, pred_waist, pred_hip = pred["chest"], pred["waist"], pred["hip"]
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
        }
        if actual_chest is not None:
            result["err_chest"] = round(pred_chest - actual_chest, 1)
            result["err_waist"] = round(pred_waist - actual_waist, 1)
            result["err_hip"] = round(pred_hip - actual_hip, 1)
        results.append(result)

        ac = f"{actual_chest:.0f}" if actual_chest else "-"
        aw = f"{actual_waist:.0f}" if actual_waist else "-"
        ah = f"{actual_hip:.0f}" if actual_hip else "-"
        print(f"  {sid:18s} {row['gender']} {row['height']:5.1f}/{row['weight']:5.1f}kg BMI{row['bmi']:4.1f} [{used_views:11s}] | "
              f"actual: C{ac} W{aw} H{ah} | pred: C{pred_chest:.0f} W{pred_waist:.0f} H{pred_hip:.0f} ({elapsed:.1f}s)")

    out_csv = OUT_DIR / "celebrities_vlm_benchmark.csv"
    df_results = pd.DataFrame(results)
    df_results.to_csv(out_csv, index=False)
    print(f"\nresults saved: {out_csv}")

    if "err_chest" in df_results.columns:
        measured = df_results.dropna(subset=["err_chest"])
        if len(measured) > 0:
            print(f"\n=== MAE (n={len(measured)} measured) ===")
            for t in ["chest", "waist", "hip"]:
                mae = measured[f"err_{t}"].abs().mean()
                bias = measured[f"err_{t}"].mean()
                print(f"  {t}: MAE={mae:.2f}cm, bias={bias:+.2f}cm")
            print(f"\n=== BMI 카테고리별 MAE ===")
            for cat in sorted(measured["category"].unique()):
                sub = measured[measured["category"] == cat]
                if len(sub) > 0:
                    mae = sub[["err_chest", "err_waist", "err_hip"]].abs().mean().mean()
                    print(f"  {cat:20s} (n={len(sub)}): mean MAE = {mae:.2f}cm")
            not_measured = df_results[df_results["actual_chest"].isna()]
            if len(not_measured) > 0:
                print(f"\n=== H/W만 있는 celebs (n={len(not_measured)}) ===")
                for _, r in not_measured.iterrows():
                    print(f"  {r['subject_id']:18s} {r['height']:5.1f}/{r['weight']:5.1f}kg BMI{r['bmi']:4.1f} | "
                          f"pred: C{r['pred_chest']:.0f} W{r['pred_waist']:.0f} H{r['pred_hip']:.0f}")


if __name__ == "__main__":
    main()
