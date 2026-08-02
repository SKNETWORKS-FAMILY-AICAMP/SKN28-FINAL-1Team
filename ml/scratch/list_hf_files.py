from huggingface_hub import HfApi

def main():
    api = HfApi()
    print("=== UniqueData/body-measurements-dataset 리포지토리 파일 목록 ===")
    try:
        files = api.list_repo_files(repo_id="UniqueData/body-measurements-dataset", repo_type="dataset")
        # 처음 50개 파일 출력
        for file in files[:50]:
            print(f"- {file}")
        if len(files) > 50:
            print(f"... 외 {len(files) - 50}개 파일 존재")
    except Exception as e:
        print(f"파일 검색 오류: {e}")

if __name__ == "__main__":
    main()
