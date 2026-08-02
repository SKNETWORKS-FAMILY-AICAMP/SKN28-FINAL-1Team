import os
import re

KEYWORDS = ["키", "몸무게", "둘레", "모델", "사이즈", "성별", "나이"]
DOCS_DIR = "data/data_analysis"

def main():
    print("=== 데이터셋 설명서 내 신체 측정 키워드 탐색 ===")
    for filename in sorted(os.listdir(DOCS_DIR)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(DOCS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        found = []
        for kw in KEYWORDS:
            matches = list(re.finditer(kw, content))
            if matches:
                found.append(f"{kw}({len(matches)}회)")
                
        if found:
            print(f"- {filename}: {', '.join(found)}")

if __name__ == "__main__":
    main()
