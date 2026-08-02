from huggingface_hub import HfApi

def main():
    api = HfApi()
    print("=== ud-biometrics/body-measurements-image-dataset 파일 목록 조회 ===")
    try:
        files = api.list_repo_files(repo_id="ud-biometrics/body-measurements-image-dataset", repo_type="dataset")
        print(f"총 파일 수: {len(files)}")
        for file in files[:30]:
            print(f"- {file}")
        if len(files) > 30:
            print("...")
    except Exception as e:
        print(f"조회 실패: {e}")

if __name__ == "__main__":
    main()
