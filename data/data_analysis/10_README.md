# 10. 한국인 신체 3D 스캐닝 데이터 보는 법

## 1. 이 데이터는 무엇인가

`s3://skn28-cozy/10.한국_신체_3D_스캐닝_데이터/`은 실제 한국인 성인 477명(남 234명, 여 243명)을 3D 스캐너로 촬영해 만든 **전신 3D 메시**와 그 메시에서 추출한 **32개 신체 keypoint의 3D/2D 좌표**, 그리고 **키·몸무게·BMI·가슴둘레·허리둘레·엉덩이둘레·팔길이 등 실측 신체 치수**를 한 세트로 묶어놓은 데이터셋이다.

사람 1명이 **20가지 자세(T포즈, 허리 회전 자세 등)**로 촬영되어 있고, 각 자세마다 **36개 카메라 각도(방위각 3 × 고도각 12)**의 2D 투영 이미지·keypoint가 함께 들어 있어, "3D 형상 + 정확한 신체 치수 + 자세별 다각도 이미지"가 한 인물 폴더 안에서 모두 연결된다.

AI Hub(aihub.or.kr)에서 배포한 **kpose** 라이선스 데이터이며, 우리 프로젝트에서는 **사용자 체형 기반 사이즈/핏 추천**의 근거 데이터로 활용 가치가 높다.

## 2. S3 위치

기준 버킷:

```powershell
aws s3 ls s3://skn28-cozy/
```

10번 데이터 최상위:

```powershell
aws s3 ls 's3://skn28-cozy/10.한국_신체_3D_스캐닝_데이터/'
```

Training 폴더:

```text
s3://skn28-cozy/10.한국_신체_3D_스캐닝_데이터/01-1.정식개방데이터/Training/
├── 01.원천데이터/TS/                 # 3D mesh+texture (424명)
└── 02.라벨링데이터/TL/               # keypoint+실측치 (424명)
```

Validation 폴더:

```text
s3://skn28-cozy/10.한국_신체_3D_스캐닝_데이터/01-1.정식개방데이터/Validation/
├── 01.원천데이터/VS/
└── 02.라벨링데이터/VL/
```

## 3. 전체 폴더 구조

`01-1.정식개방데이터` 단일 최상위 폴더 아래에 Training과 Validation이 동일한 골격으로 들어 있다.

```text
10.한국_신체_3D_스캐닝_데이터/
└── 01-1.정식개방데이터/
    ├── Training/
    │   ├── 01.원천데이터/TS/                         ← 3D 메시+텍스처
    │   │   └── {actor_id}/                          예: 3001M, 3108M(남) / 7001F, 7209F(여)
    │   │       └── {a~t}/                           포즈 20종 (a, b, c … t)
    │   │           ├── {actor}_BD_{POSE}.obj         실측 평균 ≈ 14.5MB
    │   │           ├── {actor}_BD_{POSE}.mtl         수십 바이트 재질 정의
    │   │           └── {actor}_BD_{POSE}.png         실측 평균 ≈ 16MB 텍스처
    │   └── 02.라벨링데이터/TL/                       ← 1:1 매칭 라벨
    │       └── {actor_id}/
    │           ├── 0 META/
    │           │   └── {actor}_MD_CP.txt            카메라 캘리브레이션
    │           └── {a~t}/
    │               ├── {actor}_BD_{POSE}.json        3D keypoint 32점 + 실측치
    │               └── 2D/
    │                   └── {actor}_BD_{POSE}.A{방위각}-H{고도각}.{json,png,anno.png}
    │                   # 36개 카메라 뷰 × 3파일 = 108개
    └── Validation/                                   # 동일 구조, 여성 53명
```

확인 근거(`aws s3api list-objects-v2 --delimiter /`):

- `TS`(Training 원천) 폴더 수 = `TL`(Training 라벨) 폴더 수 = **424**로 1:1 일치
- 접두사 `3` 시작(남성) = 234명, 접두사 `7` 시작(여성) = 190명 → 합계 424명
- Validation의 `VS`/`VL` = 각각 **53**이고 전원이 접두사 `7`(여성) → 남성 0명

## 4. 폴더별 의미

### TS/{actor_id}/{a~t}/*.obj · .mtl · .png

인물 1명 × 포즈 1개당 3파일:

- `*.obj`: 메인 형상. 평균 ≈ 14.5MB
- `*.mtl`: 재질 정의(텍스처 매핑 참조)
- `*.png`: 텍스처 이미지. 평균 ≈ 16MB

obj + mtl + png 세트라면 일반적인 3D 정적 메시 워크플로(Blender/MeshLab/Three.js)에서 그대로 렌더링 가능하다.

### TS/ 의 한 사람당 용량

`aws s3 ls --recursive --summarize`로 한 사람(3001M)을 전수 확인: **총 60 파일, 616.9 MiB** = 20포즈 × (obj + mtl + png). 즉 1인 원천만 ≈ 0.6GB.

### TL/{actor_id}/0 META/{actor}_MD_CP.txt

카메라 캘리브레이션 파일. 카메라 기종(Canon EOS 100D), 렌즈, 초점거리, ISO, 노출값 + 3D→2D 투영에 필요한 내부 파라미터(초점거리 Fx/Fy, 주점 Cx/Cy, 방사왜곡 K1/K2, 접선왜곡 P1/P2, Skew).

### TL/{actor_id}/{a~t}/*.json

3D keypoint + 신체 실측치의 **핵심 라벨 파일**. 파일명 예시 `3108M_BD_A.json`. 자세한 필드는 5절에서 다룬다.

### TL/{actor_id}/{a~t}/2D/

사람 1명 × 포즈 1개당 **108 파일**:

- `*.A{000|120|240|???}-H{000|030|060|...|330}.json` — 2D keypoint, 픽셀 (x, y)
- `*.A…-H….png` — 해당 뷰의 2D 투영 이미지
- `*.A…-H….anno.png` — keypoint가 그려진 어노테이션 이미지(추정, 미확인)

3D json과 거의 같은 구조이지만 `keypoints`가 `(x, y)` 픽셀 좌표이며 `picture`(이미지 width/height = 288×384 등), `camera.heading`(방위각) / `camera.altitude`(고도각) 필드가 추가된다. 방위각 3종 × 고도각 12종(0~330°, 30° 간격) = 36 뷰.

### TL/ 의 한 사람당 용량

한 사람(3108M)을 전수 확인: **총 2,181 파일, 19.2 MiB** = 20포즈 × (1 json + 108 2D 파일) + META 1개.

## 5. 가장 중요한 파일: keypoint JSON

`TL/3108M/a/3108M_BD_A.json` 한 파일이 다음을 한 번에 담는다.

- 32개 3D keypoint의 (x, y, z) 좌표
- 그 keypoint가 어떤 .obj/.png와 짝인지(`mesh`)
- 인물의 실측 신체 정보(`actor`)
- 자세 정보(`pose`)
- 라이선스/카메라 경로

실제 발췌 (3108M, 포즈 A = T포즈):

```json
{
  "category": {"type": "person", "type_id": 1},
  "annotation": {"id": "3108M_BD_A", "num_keypoints": 32},
  "keypoints": [
    {"id": 0, "name": "Head",        "x": -1.7497, "y": 174.8222, "z":   2.3142},
    {"id": 1, "name": "Neck",        "x": -0.4579, "y": 157.6790, "z":  -0.2104},
    ...
    {"id": 5, "name": "Nose",        "x":  0.4787, "y": 165.8009, "z":  13.9847},
    {"id": 10, "name": "Right shoulder", "x": 19.8641, "y": 148.5050, "z": -3.4540},
    ...
  ],
  "mesh": {
    "mesh_id": "3108M_A",
    "actor_id": "3108M",
    "pose_id": "A",
    "obj_file_name": "3108M_BD_A.obj",
    "png_file_name": "3108M_BD_A.png"
  },
  "actor": {
    "id": "3108M", "sex": "male", "age": 27,
    "height": 184.8, "weight": 98.6, "BMI": 28.9, "BMI Class": "overweight",
    "chest length": 107.0, "waist length": 107.0, "hip": 110.0,
    "inseam": 72.0, "outseam": 90.0, "arm length": 60.0
  },
  "pose": {"id": "3108M_A", "name": "T포즈"},
  "license": {"id": "kpose01", "name": "kpose", "url": "https://www.aihub.or.kr/"},
  "camera": {"filename": "3108M/0 META/3108M_MD_CP.txt"}
}
```

확인된 32개 keypoint(id 0~31):

```
0 Head, 1 Neck, 2 Thorax, 3 Spine, 4 Pelvis, 5 Nose,
6 Right eye, 7 Left eye, 8 Right ear, 9 Left ear,
10 Right shoulder, 11 Left shoulder, 12 Right elbow, 13 Left elbow,
14 Right wrist, 15 Left wrist, 16 Right pinky, 17 Left pinky,
18 Right index, 19 Left index, 20 Right thumb, 21 Left thumb,
22 Right hip, 23 Left hip, 24 Right knee, 25 Left knee,
26 Right ankle, 27 Left ankle, 28 Right heel, 29 Left heel,
30 Right foot index, 31 Left foot index
```

`actor` 필드는 **체형 추천의 핵심** — 키/몸무게/BMI/가슴·허리·엉덩이 둘레/인심·아웃심·팔길이가 한 줄로 들어 있다.

## 6. 샘플 하나를 보는 순서

`actor_id = 3108M`, 포즈 A(T포즈) 한 샘플을 본다.

1. S3에서 `TL/3108M/a/3108M_BD_A.json`을 내려받는다.
2. `actor.id == "3108M"`, `actor.sex == "male"`, `actor.age == 27`을 확인한다.
3. `actor` 필드에서 `height = 184.8`, `weight = 98.6`, `BMI = 28.9`, `BMI Class = "overweight"`, `chest length = 107.0`, `waist length = 107.0`, `hip = 110.0`, `inseam = 72.0`, `arm length = 60.0`을 본다 — 이 한 줄이 "체형 프로필 1건"이다.
4. `keypoints`를 한 줄 훑어 32개가 다 들어 있는지 확인하고, id 5(Nose), id 10(Right shoulder), id 22(Right hip) 등의 좌표로 신체가 어떻게 세워져 있는지 감을 잡는다.
5. `mesh.obj_file_name = "3108M_BD_A.obj"`, `mesh.png_file_name = "3108M_BD_A.png"`를 보고 `TS/3108M/a/`로 가서 obj+mtl+png를 받는다.
6. `pose.name == "T포즈"`로 자세가 어떤 것인지 본다. 20개 포즈의 한글 이름이 들어 있다.
7. (선택) `2D/3108M_BD_A.A000-H000.json`을 받아 keypoint가 (x, y)로 다시 표현된 것(2D 투영)을 본다.
8. `0 META/3108M_MD_CP.txt`를 받아 카메라 보정값을 본다.

이 한 사람 한 자세의 5~8 단계를 끝내면 "한국인 3D 스캔 데이터 한 라벨"의 전모가 잡힌다.

## 7. SQL로 보면 쉬운 이유

이 데이터는 `keypoints[]` 배열이 길 뿐, 본질은 한 사람 × 한 자세 = 한 행이다.

```sql
-- 인물 마스터
CREATE TABLE actors (
    actor_id       TEXT PRIMARY KEY,   -- 예: '3108M'
    sex            TEXT,               -- 'male' | 'female'
    age            INTEGER,
    height         REAL,               -- cm
    weight         REAL,               -- kg
    bmi            REAL,
    bmi_class      TEXT,               -- 'overweight' 등
    chest_length   REAL,    -- JSON 키: "chest length" (공백 포함)
    waist_length   REAL,    -- JSON 키: "waist length" (공백 포함)
    hip            REAL,
    inseam         REAL,
    outseam        REAL,
    arm_length     REAL  -- JSON 키: "arm length" (공백 포함)
);

-- 한 사람의 한 포즈
CREATE TABLE poses (
    actor_id      TEXT,
    pose_id       TEXT,                -- 'A' ~ 'T'
    pose_name     TEXT,                -- 'T포즈' 등
    obj_key       TEXT,                -- S3 키
    png_key       TEXT,
    label_key     TEXT,                -- 본 keypoint json 키
    PRIMARY KEY (actor_id, pose_id),
    FOREIGN KEY (actor_id) REFERENCES actors(actor_id)
);

-- 한 자세당 32개 keypoint
CREATE TABLE keypoints_3d (
    actor_id  TEXT,
    pose_id   TEXT,
    kp_id     INTEGER,                -- 0~31
    kp_name   TEXT,                   -- 'Nose', 'Right shoulder' ...
    x_cm      REAL,                   -- 단위는 cm 추정(3D 좌표)
    y_cm      REAL,
    z_cm      REAL,
    PRIMARY KEY (actor_id, pose_id, kp_id)
);

-- 한 자세당 36 카메라 뷰의 2D 투영
CREATE TABLE keypoints_2d_views (
    actor_id   TEXT,
    pose_id    TEXT,
    heading    INTEGER,               -- 0/120/240 (방위각)
    altitude   INTEGER,               -- 0~330 (고도각, 30° 간격)
    image_key  TEXT,                  -- png 경로
    json_key   TEXT,                  -- 2D keypoint 라벨 경로
    PRIMARY KEY (actor_id, pose_id, heading, altitude)
);
```

이렇게 넣으면 질의가 SQL이 된다.

특정 연령·성별·BMI대 분포 보기:

```sql
SELECT
    CASE
      WHEN bmi < 18.5 THEN 'underweight'
      WHEN bmi < 25   THEN 'normal'
      WHEN bmi < 30   THEN 'overweight'
      ELSE                 'obese'
    END AS bmi_band,
    sex,
    COUNT(*) AS n,
    AVG(height) AS avg_h,
    AVG(chest_length) AS avg_chest,
    AVG(waist_length) AS avg_waist
FROM actors
GROUP BY bmi_band, sex
ORDER BY bmi_band, sex;
```

특정 인물의 32 keypoint 좌표 매트릭스:

```sql
SELECT kp_name, x_cm, y_cm, z_cm
FROM keypoints_3d
WHERE actor_id = '3108M' AND pose_id = 'A'
ORDER BY kp_id;
```

두 사람 사이 어깨너비 차이(신체비율 비교):

```sql
WITH measure AS (
    SELECT actor_id,
           ABS(k.x_cm) AS right_shoulder_x
    FROM keypoints_3d k
    WHERE k.kp_name = 'Right shoulder' AND k.pose_id = 'A'
)
SELECT (m_a.right_shoulder_x - m_b.right_shoulder_x) * 2 AS shoulder_width_diff_cm
FROM measure m_a JOIN measure m_b ON m_a.actor_id = '3108M' AND m_b.actor_id = '3001M';
```

즉 JSON 한 덩어리가 아니라 **행 = keypoint** 테이블로 풀어두면 체형 분석이 쉬워진다.

## 8. 이 데이터로 알 수 있는 것

이 데이터로 바로 알 수 있는 것:

- 한국인 성인 477명의 키·몸무게·BMI·가슴·허리·엉덩이 둘레·인심·팔길이 **실측 분포**
- 32개 3D keypoint의 (x, y, z) — 어깨너비, 골반너비, 상체/하체 비율, 팔다리 길이
- 같은 인물의 20가지 자세(T포즈, 허리 회전 자세 등)에서 관절 가동 범위
- 36개 카메라 각도에서 본 2D 투영과 3D→2D 정합(ground truth)

조금 더 분석하면 알 수 있는 것:

- BMI Class("underweight" / "normal" / "overweight" / "obese") 별 체형 군집
- 성별·연령대·BMI Class에 따른 어깨너비 ↔ 허리둘레 비율 같은 **체형 지표**
- 특정 포즈(예: T포즈)에서 추정한 어깨폭이 옷 패턴 치수와 어떻게 매칭되는가
- 20가지 포즈의 관절 좌표 변화로 본 "가동 범위 군집"
- 사진 1장으로부터 신체를 추정하는 모델의 학습 데이터로 쓸 수 있는 36-view + 32-keypoint 정답지

체형 추천/사이즈 추천의 **정답 데이터 그 자체**라는 점에서 활용 가치가 매우 높다.

## 9. 추천 시스템에 활용하는 방법

### 체형 유사도 기반 추천의 기초 데이터

`actor` 필드의 키·몸무게·BMI·가슴둘레·허리둘레·엉덩이둘레·인심·팔길이는 사람마다 세트로 존재하는 "실측 체형 프로필"이다. 사용자가 입력(또는 추정)한 체형 정보를 477명의 실측 분포와 비교해 가장 가까운 체형 군집을 찾고, 그 군집에서 선호되는 실루엣·핏 특성을 추천 로직에 반영할 수 있다.

### BMI Class 기반 자동 체형 분류기

이미 라벨링된 `BMI Class`를 지도학습 타깃으로 삼아, 사용자가 입력한 키·몸무게만으로 체형 클래스를 예측하는 경량 분류기를 만들 수 있다. 예측된 체형 클래스에 따라 오버사이즈/슬림핏 등 실루엣이 다른 카테고리를 우선 추천하는 규칙과 연결 가능.

### 신체 비율(keypoint) 기반 사이즈 매칭

32개 3D keypoint(어깨·골반·상체·하체 비율 등)로부터 "신체 비율 벡터"를 계산해두면, 상품별 사이즈 표(가슴단면·허리단면 등)와 매칭해 "이 체형이면 M보다 L이 잘 맞는다" 같은 사이즈 추천에 쓸 수 있다. `chest length` / `waist length` / `hip` (모두 JSON 필드명) 은 의류 사이즈 표와 단위가 그대로 대응된다.

### 사용자 사진 → 신체 치수 추정 모델의 학습·검증 데이터

`2D/` 폴더의 36개 각도 사진과 대응되는 2D keypoint, 그리고 진짜 정답인 3D 실측 치수가 한 세트로 묶여 있다는 것은, "사진 → keypoint 추정 → 실측 치수 역산" 파이프라인의 정답 데이터라는 뜻이다. 사용자가 전신 사진을 올렸을 때 신체 치수를 자동 추정하는 모델을 만들기에 이상적이다.

### 20. 한국인 전신 형상 데이터(폴더 20)와의 보완

20번 데이터셋도 비슷한 체형 정보를 제공한다(39개 실측 항목 CSV). 10번은 keypoint·2D 투영 + 자세 다양성이 강점, 20번은 CSV 실측 항목 수와 3D mesh 활용(OBJ+MTL+JPG)이 강점이다. 두 데이터셋을 결합해 학습 데이터로 쓸 경우 컬럼명·단위(cm/kg) 통일 작업이 필요하다.

### 성별 편중 유의사항

Validation 세트가 전원 여성(53명, 남성 0명)이다. 성별 구분 없는 공용 체형 모델을 학습/검증하면 편향이 생길 수 있으므로, 성별 분리 검증 또는 Training의 여성 190명을 함께 활용하는 식의 보정이 필요하다.

## 10. 초보자용 최소 분석 루틴

처음에는 이것만 하면 된다.

1. 한 사람 한 자세의 JSON **하나**만 받는다 (예: `3108M/a/3108M_BD_A.json`, 약 4KB).
2. `actor` 필드의 키/몸무게/BMI/가슴·허리·엉덩이 둘레/팔길이를 본다 — 이 한 줄이 체형 프로필.
3. `keypoints` 길이가 32인지 확인하고 id 0(Head)와 id 22(Right hip) 정도만 본다.
4. `mesh.obj_file_name` 값으로 obj 파일을 받아 같은 이름의 mtl/png도 받는다 (세트 = 약 30MB).
5. 받은 obj+mtl+png를 MeshLab/Blender에서 열어 실제로 메시가 그려지는지 본다.
6. (선택) `2D/` 폴더에서 같은 포즈의 png 한 장과 json 한 개를 받아 2D keypoint가 어디 찍혀 있는지 본다.
7. (선택) 다른 한 사람(`3001M`) 한 자세도 받아 같은 7단계를 반복한다 — 두 명만 보면 분포의 분위기를 잡을 수 있다.

```text
keypoint json 1개 (≈ 4KB)
→ actor 필드 = 체형 프로필 확인
→ keypoints[] = 32개 좌표 확인
→ mesh.obj_file_name = obj 다운로드
→ obj+mtl+png 세트로 렌더링
→ (선택) 2D 한 뷰도 비교
```

obj+png 안 받고 keypoint json만 읽어도 체형 데이터 자체는 충분히 활용 가능하다.

## 11. 규모와 주의사항

S3 실측치(표본 기반 환산, 추정치임을 밝힘):

| 항목 | 값 |
|---|---|
| Training 원천(TS) 인물 폴더 수 | **424** (남 234 + 여 190, 직접 카운트) |
| Training 라벨(TL) 인물 폴더 수 | **424** (1:1 일치) |
| Validation 원천(VS) / 라벨(VL) | **각 53** (전원 여성) |
| 1명당 원천 파일 수 | **60** (20포즈 × 3파일) |
| 1명당 라벨 파일 수 | **2,181** (20포즈 × 109 + META 1개) |
| 1명당 원천 용량 | **616.9 MiB** (3001M 실측) |
| 1명당 라벨 용량 | **19.2 MiB** (3108M 실측) |
| 전체 환산 (477명, 원천만) | **≈ 287 GiB** |
| 전체 환산 (라벨만) | **≈ 9 GiB** |

용량 추정에는 메타 정보·캘리브레이션 txt 등이 포함되지 않은 단순 곱셈 값이므로 실제와 오차 가능. 일부는 결번/중복 가능성도 미확인.

주의사항:

- **3D 좌표 단위** — `keypoints[].x/y/z` 값이 cm인지 mm인지 본 분석 단계에서는 확정하지 않았다. 실제 학습에 쓰기 전에 한 사람 obj와 비교해 단위 결정 필요.
- **카메라 캘리브레이션** — 2D와의 정합에 반드시 필요한 파일이지만 한 사람당 1개라 빠뜨리기 쉬움. 같은 `actor_id` 안 `0 META/{actor}_MD_CP.txt`에 있다.
- **Validation 전원 여성** — 성별 분리 검증 또는 Training의 여성 190명 활용 필요.
- **인물 결번 가능** — 폴더명 범위 안의 모든 번호가 실재한다고 단정할 수 없다(`aws s3 ls`로 확인해 봐야 함).
- **obj 파일 단일 용량이 큼** — 한 사람 한 자세당 ≈ 14.5MB, 477명 × 20포즈면 수백 GB. Streaming/점진 다운로드 도구(`aws s3 cp`의 `--range`) 고려.
- **병렬 다운로드 시 IAM 권한** — bucket region과 자격증명(region = ap-northeast-2)에 맞는지 확인.

## 12. 이번에 내려받은 샘플

작업 폴더:

```text
C:\Users\Playdata\AppData\Local\Temp
```

파일:

```text
10_sample_keypoint.json          # 4,217 bytes (3108M, 포즈 A, T포즈)
```

이 한 파일로 다음을 확인했다:

- `category.type == "person"`, `annotation.num_keypoints == 32` — 정식 스키마와 일치
- `keypoints[]` 32개 id·name·x/y/z 좌표
- `actor`: 성별 male, 나이 27, 키 184.8cm, 몸무게 98.6kg, BMI 28.9, BMI Class "overweight", 가슴·허리·엉덩이 둘레·인심·아웃심·팔길이
- `pose.name == "T포즈"`
- `mesh.obj_file_name == "3108M_BD_A.obj"`, `png_file_name == "3108M_BD_A.png"`

`*.obj` / `*.mtl` / `*.png` (메시·텍스처)와 `2D/` 폴더의 png는 이번 세션에서 내려받지 않았다(평균 obj ≈ 14.5MB, png ≈ 16MB).

## 13. 출처 및 확인 근거

출처:

- S3: `s3://skn28-cozy/10.한국_신체_3D_스캐닝_데이터/`
- AI Hub: https://www.aihub.or.kr/ (정식 개방 데이터, kpose 라이선스)
- Confluence: https://jjeoe0317.atlassian.net/wiki/spaces/SKN281team/pages/8847566
- 시각화 아티팩트: https://claude.ai/code/artifact/77a75ed4-d56d-4df8-aaed-06904641e2ce (구 버전)
- 시각화 아티팩트 (통일 디자인): `data/10_한국인_3D스캐닝/artifact.html` — 11번 아티팩트 CSS로 재작성 (2026-07-09)

확인 근거:

- `aws s3 ls`, `aws s3 ls --recursive --summarize`로 폴더 구조와 객체 수/용량 실측.
- `aws s3api list-objects-v2 --delimiter /`로 TS/TL의 인물 폴더 수 카운트: Training 424, Validation 53.
- 접두사 기반 인물 수: `3` 시작(남) 234명, `7` 시작(여) 190명(Training), Validation은 전원 여성 53명.
- 3001M 한 사람의 원천 데이터 `--recursive --summarize` 결과 60 파일 / 616.9 MiB 확인.
- 3108M 한 사람의 라벨 데이터 `--recursive --summarize` 결과 2,181 파일 / 19.2 MiB 확인.
- `TL/3108M/a/3108M_BD_A.json`을 직접 내려받아 필드(`category` / `annotation` / `keypoints[]` 32개 / `mesh` / `actor` / `pose` / `license` / `camera`) 실측.
- `keypoints[]` 32개 id·name·x/y/z 좌표, `actor` 필드의 8개 실측치(`height`, `weight`, `BMI`, `BMI Class`, `chest length`, `waist length`, `hip`, `inseam`, `outseam`, `arm length`) 실측 확인. (필드명에 공백 포함, 밑줄 아님.)
