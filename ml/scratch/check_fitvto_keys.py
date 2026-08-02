from datasets import load_dataset

def main():
    print("=== fitvto-100k 레코드의 전체 Keys 분석 ===")
    try:
        ds = load_dataset("Yuanhao-Harry-Wang/fitvto-100k", streaming=True)
        split = list(ds.keys())[0]
        iterator = iter(ds[split])
        row = next(iterator)
        print("전체 컬럼 목록:")
        for k, v in row.items():
            print(f"- {k}: {type(v)}")
    except Exception as e:
        print(f"에러: {e}")

if __name__ == "__main__":
    main()
