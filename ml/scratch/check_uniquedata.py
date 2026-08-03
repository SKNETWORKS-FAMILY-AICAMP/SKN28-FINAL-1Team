from datasets import load_dataset

def main():
    print("=== UniqueData/body-measurements-dataset 진단 시작 ===")
    try:
        ds = load_dataset("UniqueData/body-measurements-dataset", streaming=True)
        split = list(ds.keys())[0]
        iterator = iter(ds[split])
        
        # 첫 3개 레코드 가져오기
        for i in range(3):
            print(f"\n--- 레코드 {i} ---")
            row = next(iterator)
            for k, v in row.items():
                if k == "image" or k == "person_image" or k == "cloth":
                    print(f"- {k}: {type(v)}")
                else:
                    # 너무 길 경우 슬라이싱 출력
                    val_str = str(v)
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "..."
                    print(f"- {k}: {val_str}")
    except Exception as e:
        print(f"진단 중 에러 발생: {e}")

if __name__ == "__main__":
    main()
