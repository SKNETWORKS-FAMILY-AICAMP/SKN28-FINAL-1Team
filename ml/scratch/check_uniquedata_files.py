from huggingface_hub import list_repo_files

def main():
    print("=== UniqueData/body-measurements-dataset 파일 목록 ===")
    try:
        files = list_repo_files(repo_id="UniqueData/body-measurements-dataset", repo_type="dataset")
        for f in files:
            print(f"- {f}")
    except Exception as e:
        print(f"조회 실패: {e}")

if __name__ == "__main__":
    main()
