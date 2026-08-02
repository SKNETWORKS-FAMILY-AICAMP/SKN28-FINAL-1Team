import boto3
import json
import numpy as np

BUCKET_NAME = "skn28-cozy"
session = boto3.Session(profile_name="cozy")
s3 = session.client("s3", region_name="ap-southeast-2")

def parse_polygon_points(polygon_str):
    points = [float(x) for x in polygon_str.strip().split()]
    xs = points[0::2]
    ys = points[1::2]
    return xs, ys

def main():
    base_prefix = "20.한국인_전신_형상_및_치수_측정_데이터/01.데이터/1.Training/라벨링데이터/TL_F009toF108/TL_F009/json/"
    
    camera_metrics = []
    print("=== 1~32번 카메라 투영 수직 신장 분석 ===")
    
    for zz in range(1, 33):
        json_key = f"{base_prefix}01_01_F009_{zz:02d}.json"
        try:
            obj = s3.get_object(Bucket=BUCKET_NAME, Key=json_key)
            data = json.loads(obj["Body"].read().decode("utf-8"))
            
            all_xs = []
            all_ys = []
            head_ys = []
            foot_ys = []
            
            for item in data.get("labelingInfo", []):
                poly = item.get("polygon", {})
                label = poly.get("label")
                loc = poly.get("location", "")
                
                if not loc:
                    continue
                xs, ys = parse_polygon_points(loc)
                all_xs.extend(xs)
                all_ys.extend(ys)
                
                if label == "머리":
                    head_ys.extend(ys)
                elif "발" in label:
                    foot_ys.extend(ys)
            
            if not all_ys:
                continue
                
            min_y, max_y = min(all_ys), max(all_ys)
            body_height_px = max_y - min_y
            
            mean_head_y = np.mean(head_ys) if head_ys else 0
            mean_foot_y = np.mean(foot_ys) if foot_ys else 0
            
            camera_metrics.append({
                "camera_num": zz,
                "height_px": body_height_px,
                "min_y": min_y,
                "max_y": max_y,
                "head_y": mean_head_y,
                "foot_y": mean_foot_y
            })
            
        except Exception as e:
            # print(f"Error loading {zz}: {e}")
            continue
            
    # 수직 픽셀 신장이 가장 큰 순서로 정렬 (수평에 가까워 왜곡이 덜한 카메라)
    camera_metrics.sort(key=lambda x: x["height_px"], reverse=True)
    
    print("\n[수직 픽셀 높이가 큰 상위 10개 카메라 목록]")
    print(f"{'Rank':<5} | {'Cam Num':<8} | {'Body Height (px)':<18} | {'Head Y':<8} | {'Foot Y':<8}")
    print("-" * 60)
    for rank, metric in enumerate(camera_metrics[:15], 1):
        print(f"{rank:<5} | {metric['camera_num']:<8} | {metric['height_px']:<18.1f} | {metric['head_y']:<8.1f} | {metric['foot_y']:<8.1f}")

if __name__ == "__main__":
    main()
