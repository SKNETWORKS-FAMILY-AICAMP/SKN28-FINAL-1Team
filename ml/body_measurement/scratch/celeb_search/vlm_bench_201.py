"""
201명 VLM 벤치마크 (gpt-4o-mini).
sizkorea (표준 full body + 측면 90°) 181명 + celeb 20명.
"""
import os
import sys
import csv
import json
import time
import base64
from pathlib import Path

from openai import OpenAI

ROOT = Path("/Users/vosnuevo/Shared/workspaces/SKN28-FINAL-1Team")
ML = ROOT / "ml/body_measurement"
CD = ML / "data/celebrities"
IC = CD / "celebrities_index.csv"
OD = ML / "reports"
OD.mkdir(exist_ok=True)

ENV = ROOT / ".env"
if ENV.exists():
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k] = v.strip("'\"")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def build_prompt(h, g, w):
    gf = "Female" if g.upper().startswith("F") else "Male"
    return f"""You are an expert in anthropometry and visual body measurement from photos.

Analyze the provided full-body photo of a real person.

Known metadata:
- Height: {h} cm
- Gender: {gf}
- Weight: {w} kg

Using the height as pixel-to-centimeter calibration anchor, estimate:
1. Chest circumference (가슴둘레) in cm
2. Waist circumference (허리둘레) in cm
3. Hip circumference (엉덩이둘레) in cm

Output strictly as JSON with keys "chest", "waist", "hip" as floats in cm. No explanations."""


def q1(p, prompt):
    with open(p, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    r = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]}],
        max_tokens=300,
    )
    return json.loads(r.choices[0].message.content.strip())


def q_avg(fp, sp, prompt):
    a = q1(fp, prompt)
    b = q1(sp, prompt)
    avg = {}
    for k in ("chest", "waist", "hip"):
        if k in a and k in b:
            avg[k] = (a[k] + b[k]) / 2
        elif k in a:
            avg[k] = a[k]
        else:
            avg[k] = b[k]
    return avg


def main():
    rows = list(csv.DictReader(open(IC)))
    print(f"=== VLM Benchmark 201 celebs ===")
    print(f"model: {MODEL}")
    print(f"총 {len(rows)}명\n")

    out_csv = OD / "celebrities_vlm_benchmark_201.csv"
    fieldnames = ["subject_id", "gender", "height", "weight", "bmi", "category", "source",
                  "views", "latency_sec",
                  "actual_chest", "actual_waist", "actual_hip",
                  "pred_chest", "pred_waist", "pred_hip",
                  "err_chest", "err_waist", "err_hip"]
    out = open(out_csv, "w", newline="")
    w = csv.DictWriter(out, fieldnames=fieldnames)
    w.writeheader()

    results = []
    failures = []
    for i, c in enumerate(rows, 1):
        sid = c["subject_id"]
        fp = CD / f"{sid}_front.jpg"
        sp = CD / f"{sid}_side.jpg"
        if not fp.exists():
            continue
        try:
            a_c = float(c["chest"]); a_w = float(c["waist"]); a_h = float(c["hip"])
        except (ValueError, TypeError):
            continue
        prompt = build_prompt(float(c["height"]), c["gender"], float(c["weight"]))
        t0 = time.time()
        try:
            if sp.exists():
                pred = q_avg(fp, sp, prompt)
                views = "front+side"
            else:
                pred = q1(fp, prompt)
                views = "front"
        except Exception as e:
            print(f"  [{i}/{len(rows)}] [ERR] {sid}: {e}")
            failures.append((sid, str(e)))
            continue
        elapsed = time.time() - t0

        # None 가드
        if not all(k in pred and pred[k] is not None for k in ("chest", "waist", "hip")):
            print(f"  [{i}/{len(rows)}] [SKIP] {sid}: VLM returned None for one of chest/waist/hip")
            failures.append((sid, "None values"))
            continue
        pc, pw, ph = pred["chest"], pred["waist"], pred["hip"]
        if any(v is None for v in (pc, pw, ph)):
            print(f"  [{i}/{len(rows)}] [SKIP] {sid}: None in pred")
            continue
        ec, ew, eh = round(pc - a_c, 1), round(pw - a_w, 1), round(ph - a_h, 1)
        rec = {
            "subject_id": sid, "gender": c["gender"],
            "height": c["height"], "weight": c["weight"], "bmi": c["bmi"],
            "category": c["category"], "source": c["source"],
            "views": views, "latency_sec": round(elapsed, 2),
            "actual_chest": a_c, "actual_waist": a_w, "actual_hip": a_h,
            "pred_chest": round(pc, 1), "pred_waist": round(pw, 1), "pred_hip": round(ph, 1),
            "err_chest": ec, "err_waist": ew, "err_hip": eh,
        }
        w.writerow(rec)
        results.append(rec)
        if i % 20 == 0:
            import statistics
            ec_l = [abs(r["err_chest"]) for r in results]
            print(f"  [{i}/{len(rows)}] progress: {len(results)} done, MAE_c={statistics.mean(ec_l):.2f}")

    out.close()
    print(f"\n=== 완료: {len(results)}명 ===")
    print(f"실패: {len(failures)}명")
    if failures:
        for sid, e in failures[:5]:
            print(f"  - {sid}: {e[:60]}")

    if results:
        import statistics
        from collections import defaultdict
        print(f"\n=== MAE (n={len(results)}) ===")
        for t in ["chest", "waist", "hip"]:
            errs = [abs(r[f"err_{t}"]) for r in results]
            biases = [r[f"err_{t}"] for r in results]
            print(f"  {t}: MAE={statistics.mean(errs):.2f}cm, bias={statistics.mean(biases):+.2f}cm")

        # 카테고리별
        by_cat = defaultdict(list)
        for r in results: by_cat[r["category"]].append(r)
        print(f"\n=== 카테고리별 ===")
        for cat, rs in sorted(by_cat.items()):
            mc = statistics.mean(abs(r["err_chest"]) for r in rs)
            mw = statistics.mean(abs(r["err_waist"]) for r in rs)
            mh = statistics.mean(abs(r["err_hip"]) for r in rs)
            print(f"  {cat:20s} (n={len(rs):3d}): C={mc:.2f}, W={mw:.2f}, H={mh:.2f}")

        # view별
        for view in ["front+side", "front"]:
            rs = [r for r in results if r["views"] == view]
            if rs:
                print(f"\n--- {view} (n={len(rs)}) ---")
                for t in ["chest", "waist", "hip"]:
                    errs = [abs(r[f"err_{t}"]) for r in rs]
                    biases = [r[f"err_{t}"] for r in rs]
                    print(f"  {t}: MAE={statistics.mean(errs):.2f}, bias={statistics.mean(biases):+.2f}")

        # BMI 카테고리별
        def bmi_cat(b):
            try: b = float(b)
            except: return "?"
            if b < 18.5: return "underweight"
            elif b < 25: return "normal"
            elif b < 30: return "overweight"
            else: return "obese"
        bmi_data = defaultdict(list)
        for r in results: bmi_data[bmi_cat(r.get("bmi"))].append(r)
        print(f"\n=== BMI 카테고리별 ===")
        for bc, rs in sorted(bmi_data.items()):
            if bc == "?": continue
            mc = statistics.mean(abs(r["err_chest"]) for r in rs)
            mw = statistics.mean(abs(r["err_waist"]) for r in rs)
            mh = statistics.mean(abs(r["err_hip"]) for r in rs)
            print(f"  BMI {bc:12s} (n={len(rs):3d}): C={mc:.2f}, W={mw:.2f}, H={mh:.2f}")

        # best/worst
        print(f"\n=== best 5 ===")
        for r in sorted(results, key=lambda x: abs(x["err_chest"])+abs(x["err_waist"])+abs(x["err_hip"]))[:5]:
            s = abs(r["err_chest"])+abs(r["err_waist"])+abs(r["err_hip"])
            print(f"  {r['subject_id']:25s} sum={s:.1f}cm | cat={r['category']:12s} | err C{r['err_chest']:+.1f} W{r['err_waist']:+.1f} H{r['err_hip']:+.1f}")
        print(f"\n=== worst 5 ===")
        for r in sorted(results, key=lambda x: -(abs(x["err_chest"])+abs(x["err_waist"])+abs(x["err_hip"])))[:5]:
            s = abs(r["err_chest"])+abs(r["err_waist"])+abs(r["err_hip"])
            print(f"  {r['subject_id']:25s} sum={s:.1f}cm | cat={r['category']:12s} | err C{r['err_chest']:+.1f} W{r['err_waist']:+.1f} H{r['err_hip']:+.1f}")

    print(f"\nsaved: {out_csv}")


if __name__ == "__main__":
    main()
