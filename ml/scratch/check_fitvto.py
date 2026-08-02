from huggingface_hub import HfApi

def main():
    api = HfApi()
    print("=== Yuanhao-Harry-Wang/fitvto-100k 파일 목록 조회 ===")
    try:
        files = api.list_repo_files(repo_id="Yuanhao-Harry-Wang/fitvto-100k", repo_type="dataset")
        print(f"총 파일 수: {len(files)}")
        for file in files[:30]:
            print(f"- {file}")
        if len(files) > 30:
            print("...")
    except Exception as e:
        print(f"조회 실패: {e}")

if __name__ == "__main__":
    main()
