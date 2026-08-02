import os
import pandas as pd
import numpy as np

META_FILE = "data/all_subjects_meta.csv"
OUTPUT_FILE = "data/golden_200_meta.csv"

def main():
    if not os.path.exists(META_FILE):
        print("인덱스 메타파일이 없습니다.")
        return
        
    df = pd.read_csv(META_FILE)
    print("=== 원천 데이터셋 991명 통계 분석 ===")
    print(f"전체 인원: {len(df)}명")
    
    # 1. 성별 분포
    print("\n[성별 분포]")
    print(df["gender"].value_counts())
    
    # 2. 연령대 구간 분포 (10대부터 60대 이상까지)
    df["age_group"] = pd.cut(
        df["age"],
        bins=[0, 19, 29, 39, 49, 59, 100],
        labels=["10대", "20대", "30대", "40대", "50대", "60대이상"]
    )
    print("\n[연령대 분포]")
    print(df["age_group"].value_counts().sort_index())
    
    # 3. 키, 몸무게 분포 요약
    print("\n[키 분포 요약 (cm)]")
    print(df["height"].describe()[["min", "50%", "max"]])
    print("\n[몸무게 분포 요약 (kg)]")
    print(df["weight"].describe()[["min", "50%", "max"]])
    
    # === 골든셋 200명 수학적 샘플링 구현 ===
    # 목표: 남녀 1:1, 10대~30대 비중 대폭 강화 (~60%), 다양한 체형(키/몸무게 빈 분할)
    np.random.seed(42)  # 재현 가능성을 위해 시드 고정
    
    # 키와 몸무게 빈 분할 (3x3 = 9개 체형 그룹)
    df["height_bin"] = pd.qcut(df["height"], q=3, labels=["Short", "Medium", "Tall"])
    df["weight_bin"] = pd.qcut(df["weight"], q=3, labels=["Light", "Normal", "Heavy"])
    df["body_type"] = df["height_bin"].astype(str) + "_" + df["weight_bin"].astype(str)
    
    # 연령대별 타겟 분할 비율 설정
    # 10대~30대 타겟: 60% (120명)
    # 40대~60대 타겟: 40% (80명)
    
    # 연령대 그룹을 청년층(Young: 10~30대)과 장년층(Senior: 40대 이상)으로 분할
    df["age_cohort"] = df["age"].apply(lambda a: "Young" if a < 40 else "Senior")
    
    golden_list = []
    
    # 성별(2) x 연령코호트(2) x 체형그룹(9) = 총 36개 슬롯으로 나누어 균등 추출 시도
    # 남성 Young (60명) / 남성 Senior (40명)
    # 여성 Young (60명) / 여성 Senior (40명)
    targets = {
        ("M", "Young"): 60,
        ("M", "Senior"): 40,
        ("F", "Young"): 60,
        ("F", "Senior"): 40
    }
    
    for (gender, cohort), target_count in targets.items():
        sub_df = df[(df["gender"] == gender) & (df["age_cohort"] == cohort)]
        
        # 체형그룹별로 고르게 뽑기 위해 체형그룹별 셔플 후 라운드로빈 추출
        body_types = sub_df["body_type"].unique()
        type_dfs = {bt: sub_df[sub_df["body_type"] == bt].sample(frac=1.0, random_state=42) for bt in body_types}
        
        selected = []
        # 각 체형그룹에서 순차적으로 1개씩 꺼내 타겟 숫자를 채움 (특정 체형 편중 방지)
        loop_counter = 0
        while len(selected) < target_count and any(len(tdf) > 0 for tdf in type_dfs.values()):
            for bt in body_types:
                if len(selected) >= target_count:
                    break
                tdf = type_dfs[bt]
                if not tdf.empty:
                    selected.append(tdf.iloc[0])
                    type_dfs[bt] = tdf.iloc[1:]
            loop_counter += 1
            if loop_counter > 1000:  # 무한루프 방지
                break
                
        golden_list.extend(selected)
        
    golden_df = pd.DataFrame(golden_list)
    golden_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    
    print("\n" + "="*50)
    print("=== 골든 테스트셋 200명 샘플링 완료 ===")
    print(f"생성된 파일: {OUTPUT_FILE}")
    print(f"최종 추출 인원: {len(golden_df)}명")
    
    print("\n[골든셋 성별 구성]")
    print(golden_df["gender"].value_counts())
    
    print("\n[골든셋 연령대 구성 (Young 10-30대 vs Senior 40대이상)]")
    print(golden_df["age_cohort"].value_counts())
    
    print("\n[골든셋 세부 연령대 구성]")
    golden_df["age_group"] = pd.cut(
        golden_df["age"],
        bins=[0, 19, 29, 39, 49, 59, 100],
        labels=["10대", "20대", "30대", "40대", "50대", "60대이상"]
    )
    print(golden_df["age_group"].value_counts().sort_index())
    
    print("\n[골든셋 체형 그룹별 골고루 분포 검증]")
    print(golden_df["body_type"].value_counts())

if __name__ == "__main__":
    main()
