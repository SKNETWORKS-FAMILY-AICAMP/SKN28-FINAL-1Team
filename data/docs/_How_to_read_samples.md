# 샘플 데이터 보는 법

`S3 skn28-cozy` 버킷에서 11개 데이터셋마다 대표 샘플 1~2개(가능하면 원본 파일 + 매칭 라벨/메타데이터 쌍)를 각 `data/<폴더>/_sample_images/`에 받아뒀다. 여기 등장하는 포맷별로 파이썬에서 여는 법을 정리한다. `.wst.dev`/`.p`(pickle)/`.obj`+`.mtl`은 실제로 받은 샘플 파일을 직접 열어서 확인한 내용이고, `.jpg`/`.json`/`.csv`/`.xlsx`는 표준 포맷이라 별도 검증 없이 적었다.

## 어디에 뭐가 있는지

| 폴더 | 샘플 파일 |
| --- | --- |
| `01_의류통합데이터` | `*.jpg` + `*.json` (의류 이미지 + 66필드 어노테이션) |
| `03_패션상품_착용영상` | `0928015_B.jpg` + `0928015_B.json` (아이템 이미지 + Item-Parse 라벨) |
| `04_HM_추천데이터` | `0108775044.jpg` + `articles_sample_head.csv` (상품 이미지 + 메타 앞부분) |
| `05_polyvore_outfits` | `categories.csv` + `typespaces.p` (카테고리 정의 + pickle) |
| `10_한국인_3D스캐닝` | `3001M_BD_A.obj` + `.mtl` (3D mesh, 텍스처 png는 용량 문제로 생략) |
| `11_PoC_패션코디` | `BL-001.jpg` + `ac_eval_t1.wst.dev` (아이템 이미지 + 코디 대화 데이터) |
| `12_FASCODE` | `BO00001-1.jpg` + `Fashion-How24_sub1_val.csv` (이미지 + 속성 csv) |
| `20_전신형상치수` | `01_01_F009_01.jpg` + `.json` (인체 사진 + 치수/라벨) |
| `22_사이즈코리아` | `7차_인체치수조사_2015_치수데이터.xlsx` (인체 치수 원본 xlsx) |
| `23_공공데이터_의류생활체육` | `T_16791_70_hippie_M.jpg` + `_030286.json` (스타일 사진 + 라벨) |
| `26_K_Fashion` | `1092253.jpg` + `.json` (이미지 + bbox/polygon/속성 라벨) |

## jpg (이미지)

```python
from PIL import Image
img = Image.open("01_의류통합데이터/_sample_images/01_sou_000254_001266_front_02top_01blouse_woman.jpg")
img.show()          # 또는 노트북이면 img 그대로 출력
print(img.size, img.mode)
```

## json (라벨/어노테이션)

```python
import json
with open("03_패션상품_착용영상/_sample_images/0928015_B.json", encoding="utf-8") as f:
    data = json.load(f)
print(data.keys())
```

## csv

표준 csv는 그대로 `pandas.read_csv`. 다만 `04_HM_추천데이터/_sample_images/articles_sample_head.csv`는 원본 34.5MB 파일에서 앞부분만 바이트 단위로 잘라 받은 것이라 **마지막 줄이 중간에 끊겨 있다** — `on_bad_lines='skip'`으로 깨진 마지막 줄만 버리고 읽으면 된다 (확인 결과 658행 정상 로드됨).

```python
import pandas as pd
df = pd.read_csv("04_HM_추천데이터/_sample_images/articles_sample_head.csv", on_bad_lines="skip")

# 잘림 없는 표준 csv는 그냥:
df2 = pd.read_csv("12_FASCODE/_sample_images/Fashion-How24_sub1_val.csv")
```

## xlsx (엑셀)

```python
import pandas as pd
df = pd.read_excel("22_사이즈코리아/_sample_images/7차_인체치수조사_2015_치수데이터.xlsx", sheet_name=0)
# sheet_name=None 이면 전체 시트를 dict로 반환
```

## pickle (.p)

`polyvore_outfits`의 `typespaces.p`는 `(카테고리, 카테고리)` 튜플들의 리스트다 — 아이템 카테고리 쌍 간 호환성/타입스페이스 정의로 보인다. 특별한 라이브러리 없이 표준 `pickle`만으로 열린다 (직접 로드해서 확인함).

```python
import pickle
with open("05_polyvore_outfits/_sample_images/typespaces.p", "rb") as f:
    typespaces = pickle.load(f)
print(typespaces[:5])
# 예: [('bags', 'shoes'), ('bags', 'jewellery'), ...]
```

## obj + mtl (3D mesh)

`10_한국인_3D스캐닝`의 3D 스캔 데이터. `.obj`는 표준 Wavefront 지오메트리(v/vn/vt), `.mtl`은 텍스처(png) 경로만 담은 짧은 재질 정의다. 이 환경엔 `trimesh`/`open3d`가 안 깔려 있어 (`pip install trimesh` 또는 `pip install open3d` 필요) 직접 렌더링 검증은 못했지만, obj 자체는 일반 텍스트라 헤더만 봐도 정상 포맷임을 확인했다.

```python
# pip install trimesh 필요
import trimesh
mesh = trimesh.load("10_한국인_3D스캐닝/_sample_images/3001M_BD_A.obj")
print(mesh.vertices.shape, mesh.faces.shape)
mesh.show()  # 뷰어 창 필요
```

주의: 텍스처 png(`3001M_BD_A.png`, 16.1MB)는 용량 때문에 안 받아뒀다. `mtl`이 이 png를 참조하므로, 지오메트리(형상)는 바로 보이지만 텍스처 없이 무채색으로 렌더링된다. 텍스처까지 보려면 같은 S3 폴더(`10.한국_신체_3D_스캐닝_데이터/.../3001M/a/`)에서 png를 추가로 받으면 된다.

## wst / wst.dev (ETRI PoC 코디 대화 데이터, 커스텀 포맷)

`11_PoC_패션코디`의 `.wst.dev`는 **EUC-KR(=CP949)로 인코딩된 텍스트**다 (UTF-8로 읽으면 깨진다 — 직접 열어서 확인함). 형식은 탭으로 구분된 대화 로그:

- `; N` — N번째 대화(에피소드) 시작 구분선
- `US` — 사용자 발화 (형태소 단위로 띄어쓰기됨, 예: `가을 축제 에 입고 갈 스타일 로 코디 해 주 세 요`)
- `CO` — 코디네이터(시스템) 응답
- `R1`/`R2`/`R3` — 그 시점에 추천된 아이템 조합 (예: `JP-137 KN-008 SK-047 SE-042` — JP=재킷류, KN=니트, SK=스커트, SE=신발 등 카테고리 코드로 추정, 뒤 숫자는 아이템 ID)

```python
with open("11_PoC_패션코디/_sample_images/ac_eval_t1.wst.dev", encoding="euc-kr", errors="replace") as f:
    lines = f.readlines()
print("".join(lines[:10]))

# 파싱 예시: 대화(에피소드) 단위로 자르기
episodes, current = [], []
for line in lines:
    if line.startswith("; "):
        if current:
            episodes.append(current)
        current = []
    else:
        current.append(line.rstrip("\n").split("\t"))
if current:
    episodes.append(current)
print(len(episodes), "episodes")
```
