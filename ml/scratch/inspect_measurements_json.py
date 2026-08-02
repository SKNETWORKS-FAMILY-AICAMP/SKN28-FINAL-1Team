import json
from huggingface_hub import hf_hub_download

def main():
    print("=== UniqueData 'files/0/measurements.json' 다운로드 및 분석 ===")
    try:
        local_path = hf_hub_download(
            repo_id="UniqueData/body-measurements-dataset",
            filename="files/0/measurements.json",
            repo_type="dataset"
        )
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print("\n[0번 사용자 신체 정보 JSON 내용]")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"JSON 분석 에러: {e}")

if __name__ == "__main__":
    main()
