# 색상 조합 규칙

- **작성일**: 2026-08-06
- **판단 원천**: [`rules/color_rules.json`](../color/rules/color_rules.json) — 이 문서의 숫자는 전부 거기서 인용한 것이다
- **아이템 태그 연결**: [`rules/color_taxonomy_map.json`](../color/rules/color_taxonomy_map.json)
- **생성 스크립트**: [`tools/compute_color_attributes.py`](../color/tools/compute_color_attributes.py) → [`tools/build_color_rules.py`](../color/tools/build_color_rules.py)
- **v1(한국어 17색)**: [`rules/v1_backup/`](../color/rules/_archive/) 에 보존

---

## 1. 왜 표를 손으로 안 적었나

색 조합표는 153쌍이다. 손으로 적으면 두 가지가 반드시 일어난다.

1. **모순** — "A+B 기피"라고 써놓고 다른 줄에서 "B+A 허용"이 나온다.
2. **설명 불가** — "왜 이게 기피인가"에 "원래 그렇다" 말고 답할 게 없다.

그래서 **색 속성과 규칙 6개만 정의하고 등급 153쌍은 전부 계산**했다.
규칙을 하나 바꾸면 표 전체가 일관되게 다시 만들어진다.

---

## 2. 팔레트 교체

| | v1 (구) | v2 (현행) |
|---|---|---|
| 색 이름 | 한국어 17색 (`taxonomy.py::COLORS`) | 영문 18색 |
| 출처 | 옷장·상품 태그 체계 | Pinterest 코디 색조합 레퍼런스 |
| 색 공간 | HSL + RGB chroma | **CIELCh** (sRGB → XYZ(D65) → CIELAB → LCh) |
| 등급 | 권장 80 · 허용 31 · 주의 23 · 기피 2 (136쌍) | 권장 125 · 허용 7 · 주의 19 · 기피 2 (153쌍) |

**CIELCh로 바꾼 이유**: HSL의 색상각은 지각 거리와 맞지 않는다. 같은 30° 차이라도
파랑 구간과 초록 구간에서 눈이 느끼는 차이가 다르다. CIELAB 기반 LCh는 색상각과 채도가
지각 거리에 비례하므로, "색상차 150° = 보색" 같은 임계값이 색 전체에서 일관되게 작동한다.

> ⚠️ **팔레트가 아이템 태그와 다르다.** v2 색 이름은 실제 옷장·상품 아이템에 붙는 태그가 아니다.
> 아이템의 `color`(한국어)로 v2 등급을 조회하려면 반드시 §6의 매핑표를 거쳐야 한다.

### 레퍼런스 출처와 취급

`assets/pinterest_ref.jpg`는 규칙을 **유도하는 데만** 쓴 제3자 이미지다.
`fashion-rag-s3-datasets_3.md` §9의 라이선스 격리 원칙에 따라, 이 이미지와 그 파생물은
**추천 결과로 사용자에게 노출되지 않는다.** 노출되는 것은 산출된 규칙과 그 설명뿐이다.

### 코디 예시 이미지 시각화

계산된 규칙을 바탕으로 생성한 코디 조합 예시 이미지가 아래 경로에 저장되어 타당성 검토에 활용됩니다. 이들 이미지는 판단의 원천이 아니라 시각화 결과물입니다.

* **일반 코디 그리드:** `outfits/v6_grids/outfit_v6_[color].png` (Beige, Black, Cream 등 17개 색상별 코디 조합 이미지)
* **퍼스널 컬러별 연출 (Personal Color):** `outfits/personal_color/outfit_pc_*.png` (Spring, Summer, Autumn, Winter 계절별 연출 시각화)
* **실용 매칭 (Practical Outfits):** `outfits/practical/outfit_practical_*.png` (실제 착용을 고려한 코디 이미지)
* **차트:** `outfits/combination_charts/chart_*.png` (4 카테고리별 Michael 84 차트)


---

## 3. 색 속성 (계산값)

| 색 | hex | 색상각(LCh °) | chroma(C*) | 명도(L*) | 역할 | 온도 | 시각 효과 |
|---|---|---|---|---|---|---|---|
| Black | `#000000` | — | 0.0 | 0.0 | neutral | neutral | 축소 |
| White | `#FFFFFF` | — | 0.0 | 100.0 | neutral | neutral | 확장 |
| Gray | `#808080` | — | 0.0 | 53.6 | neutral | neutral | 중립 |
| Charcoal | `#36454F` | 247.8 | 8.6 | 28.4 | neutral | cool | 축소 |
| Navy | `#1B2444` | 288.5 | 22.6 | 15.0 | neutral | cool | 축소 |
| Beige | `#E8DCC4` | 89.2 | 13.3 | 88.1 | neutral | warm | 확장 |
| Cream | `#F5E6CC` | 86.3 | 14.5 | 91.8 | neutral | warm | 확장 |
| Olive | `#6B6B45` | 106.9 | 22.3 | 44.3 | semi_neutral | warm | 축소 |
| Brown | `#6B4A2F` | 63.8 | 24.1 | 34.5 | semi_neutral | warm | 축소 |
| Burgundy | `#800020` | 23.5 | 53.3 | 25.8 | accent | warm | 중립 |
| Rust | `#B7410E` | 48.2 | 68.6 | 44.1 | accent | warm | 중립 |
| Mustard | `#D4A017` | 83.1 | 69.6 | 68.9 | accent | warm | 중립 |
| Forest Green | `#228B22` | 137.8 | 67.0 | 50.6 | accent | cool | 중립 |
| Teal | `#008080` | 196.4 | 30.1 | 48.3 | accent | cool | 중립 |
| **Blue** | `#2A5CAA` | 283.4 | 48.0 | 39.7 | accent | cool | 중립 |
| Light Blue | `#ADD8E6` | 226.5 | 15.8 | 83.8 | accent | cool | 확장 |
| Lavender | `#B57EDC` | 313.9 | 55.5 | 61.6 | accent | cool | 확장 |
| Blush Pink | `#FFB6C1` | 10.2 | 28.4 | 81.1 | accent | warm | 확장 |

- **역할**: `neutral`(앵커, 색 부담을 흡수) / `semi_neutral`(색은 있으나 낮은 chroma) / `accent`(포인트)
- **시각 효과**: 명도 기준 — [체형 규칙](../body/docs/02-body-proportion-rules.md)이 이 값을 참조한다
  - **확장**: White, Beige, Cream, Lavender, Light Blue, Blush Pink
  - **축소**: Black, Charcoal, Navy, Olive, Brown
  - **중립**: Gray, Burgundy, Rust, Mustard, Forest Green, Teal, **Blue**
- chroma 0인 무채색(Black/White/Gray)은 색상각이 의미 없어 `—` 표기

---

## 4. 규칙 6개와 임계값

등급은 아래 **판정 사다리**로 결정된다. 위에서부터 먼저 걸리는 분기가 이기고,
그 아래는 검사하지 않는다. (원본: `build_color_rules.py::grade_pair`)

| 순서 | 조건 | 결과 | 규칙 | 근거 |
|---|---|---|---|---|
| 1 | 둘 다 `neutral` + 명도차 ≥18 | 권장 | R1 | 색 충돌이 없으니 남는 변수는 명도뿐 |
| 2 | 둘 다 `neutral` + 명도차 <18 | 허용 | R1 | 톤온톤 — 소재로 대비를 만든다 |
| 3 | 한쪽만 `neutral` | 권장 | R2 | 앵커가 색 부담을 흡수한다. 가장 안전한 기본형 |
| 4 | 둘 다 `accent` + **둘 다** chroma ≥45 + 색상차 ≥150° | **기피** | R3 | 고채도 보색은 경계에서 진동이 생긴다 |
| 5 | 둘 다 `accent` + **둘 다** chroma ≥45 + 색상차 ≤35° + 명도차 <18 | 주의 | R4 | 고채도 유사색인데 명도까지 붙어 뭉개진다 |
| 6 | 위와 같되 명도차 ≥18 | 권장 | R4 | 같은 계열의 톤 그라데이션 |
| 7 | 둘 다 `accent` + 색상차 ≥150° + **한쪽** chroma <25 | 허용 | R5 | 낮은 채도가 대비를 완충한다 |
| 8 | 둘 다 `accent` + 색상차 ≥150° + 양쪽 chroma ≥25 | 주의 | R3 | 보색 — 한쪽을 소면적으로 |
| 9 | 둘 다 `accent` + 웜×쿨 | 주의 | R6 | 온도가 다른 두 색이 맞닿으면 서로를 탁하게 만든다 |
| 10 | (역할 무관) 색상차 ≤35° + 명도차 <18 | 주의 | R4 | 두 아이템의 경계가 사라져 한 덩어리로 보인다 |
| 11 | 그 외 전부 | 권장 | R2 | — |

**`semi_neutral`(Olive·Brown)은 4~9번을 모두 건너뛴다.** `neutral`도 `accent`도 아니라서
10번 또는 11번에서만 판정된다. `Forest Green + Olive`와 `Brown + Rust`가 R4(10번)로
떨어지는 이유가 이것이다.

> 4번과 8번이 둘 다 R3인 점에 주의. **양쪽 다 고채도**여야 기피(4번)이고,
> 한쪽이라도 chroma <45면 보색이어도 주의(8번)에 그친다.
> 예: `Burgundy(53.3) + Teal(30.1)`은 색상차 173°지만 Teal이 45 미만이라 기피가 아니라 주의다.

| 상수 | 값 | 쓰이는 곳 |
|---|---|---|
| `chroma_high` | 45.0 | 4·5·6번의 "고채도" |
| `lightness_contrast_min` | 18.0 | 1·2·5·6·10번의 명도차 |
| `hue_similar_max` | 35.0° | 5·6·10번의 "유사색" |
| `hue_complement_min` | 150.0° | 4·7·8번의 "보색" |
| (하드코딩) | chroma 25 | 7번의 "한쪽 채도가 낮음" |

---

## 5. 등급 결과

153쌍(고유): **권장 125 · 허용 7 · 주의 19 · 기피 2**

> JSON의 `pair_grades`는 양방향 306건이다(`A|B`와 `B|A`를 모두 담아 조회를 단순화).
> 고유 조합 수는 그 절반인 153이다.

### 기피(✕) — 대면적 동시 사용 금지

| 조합 | 사유 |
|---|---|
| Forest Green + Lavender | 고채도 보색 176° `[R3]` |
| **Blue + Mustard** | 고채도 보색 160° `[R3]` |

기피가 2개뿐인 것은 규칙이 느슨해서가 아니라, **v2 팔레트가 이미 톤다운된 실용 색 체계**이기 때문이다.
chroma ≥45인 색이 6개(Burgundy·Rust·Mustard·Forest Green·Lavender·Blue)뿐이고,
그중 보색 관계까지 성립하는 쌍이 둘이다.

> `Blue + Mustard`는 Blue 추가로 새로 생긴 기피다. 파랑–노랑은 색상환 정반대라
> 둘 다 대면적이면 경계에서 진동이 생긴다. 데님(블루) + 머스터드 니트 조합이 여기 해당한다.

### 주의(△) — 소면적으로 쓰거나 뉴트럴로 완충 (19쌍)

| 유형 | 조합 | 처방 |
|---|---|---|
| **유사색·명도 뭉개짐** `[R4]` | Forest Green+Olive (31°), Brown+Rust (16°) | 소재 대비로 층을 만들거나 사이에 뉴트럴 |
| **보색 대비** `[R3]` | Burgundy+Teal (173°), Blush Pink+Teal (174°) | 한쪽을 가방·신발 같은 소면적으로 |
| **웜·쿨 혼합** `[R6]` (15쌍) | **Blue+Burgundy, Blue+Rust, Blue+Blush Pink**, Burgundy+Forest Green, Burgundy+Lavender, Forest Green+Mustard, Forest Green+Rust, Lavender+Mustard, Lavender+Rust, Light Blue+Mustard, Mustard+Teal, Rust+Teal, Blush Pink+Forest Green, Blush Pink+Lavender, Blush Pink+Light Blue | 사이에 White/Gray/Black을 넣어 분리 |

전체 153쌍의 등급은 `rules/color_rules.json`의 `matrix` 키에 있다.

---

## 6. 아이템 태그(한국어) → v2 조회

옷장·상품 아이템의 `color`는 `taxonomy.py::COLORS`의 한국어 17색이다.
v2 등급을 조회하려면 [`rules/color_taxonomy_map.json`](../color/rules/color_taxonomy_map.json)을 거친다.

```
item.color("레드") → map["레드"].v2 == "Burgundy" → pair_grades["Burgundy|Navy"]
```

`python golden-set/color/tools/validate_color_map.py`로 정합성을 검증한다
(taxonomy나 v2 팔레트가 바뀌면 이 스크립트가 먼저 실패한다).

### 손실이 있는 매핑 5건

| 태그 | → v2 | 등급 | 무엇이 달라지나 |
|---|---|---|---|
| 옐로우 | Mustard | lossy | 밝은 원색 노랑이 톤다운 노랑으로 판정 — chroma 과소평가 |
| 오렌지 | Rust | lossy | 선명한 오렌지가 적갈색으로 판정 — 보색 충돌 과소평가 |
| 레드 | Burgundy | lossy | v2에 순수 레드가 없다. 색상각이 가까운 Burgundy 선택 |
| 퍼플 | Lavender | lossy | **`visual_effect`가 중립 → 확장으로 뒤집힌다.** 어두운 퍼플 아이템에는 틀린 값이다 |
| 멀티 | (없음) | **unrepresented** | v1의 R0가 v2에서 빠졌다. 등급 조회 대신 `multi_rule`(MULTI_ANCHOR) 적용 |

**`Charcoal`과 `Teal`은 어떤 태그도 매핑되지 않는다** — 아이템 태그로 등장할 수 없는 색이다.

### ✅ 해소된 매핑 — `블루` (2026-08-06)

`블루`는 v2에 중간 명도 파랑이 없어 `Navy`로 폴백했었고, 그 탓에 두 가지가 틀렸다.

| | 폴백 시절 (블루 → Navy) | 현재 (블루 → **Blue**) |
|---|---|---|
| `role` | `neutral` — 앵커로 취급돼 **포인트 색을 하나 더 허용** | `accent` — 정상 |
| `visual_effect` | `축소` — 밝은 워싱 데님이 "가늘어 보이는 색" | `중립` — 정상 |
| chroma | 22.6 (저채도) | **48.0** — 고채도로 잡혀 R3가 정상 작동 |

팔레트에 `Blue`(`#2A5CAA`)를 추가해 `exact` 매핑이 됐다. **데님이 여기 해당해
옷장에서 빈도가 가장 높은 아이템군의 오분류가 사라졌다.**

부수 효과로 `Blue + Mustard`가 새 기피 조합이 됐다(§5). 폴백 시절에는 Navy가
저채도 뉴트럴이라 R3의 고채도 보색 판정에 걸리지 않아 **놓치던 충돌**이다.

---

## 7. 룩 단위 규칙 (쌍 등급으로 표현되지 않는 것)

위 표는 **두 색의 관계**만 본다. 룩 전체에는 다음이 추가로 적용된다.

| # | 규칙 | 근거 |
|---|---|---|
| **L1** | 한 룩의 색은 **최대 3색**. 멀티 아이템은 2색으로 센다 | 색이 4개를 넘으면 시선이 머물 곳이 사라진다 |
| **L2** | 뉴트럴 **1개 이상 필수**, 대면적(상의 또는 하의)에 배치 | R2의 앵커 원칙을 룩 단위로 확장 |
| **L3** | 고채도(chroma ≥45) 아이템은 **1개까지** | R3를 룩 단위로 확장 |
| **L4** | 상·하의 명도차 ≥18 **또는** ≤8 | 중간(9~17)이 가장 나쁘다 — 톤온톤도 아니고 대비도 아닌 애매한 상태 |
| **L5** | 신발·가방 색은 룩의 뉴트럴 중 하나와 맞춘다 | 소면적이 독립 색이면 색 수 카운트가 초과된다 |

> ⚠️ **L1~L5는 아직 JSON에 없다.** `rules/color_rules.json`에 `look_rules` 키로 추가해야
> `filter_rules.py`가 읽을 수 있다. 현재는 문서 수준 초안이다.

---

## 8. 개인 취향과의 우선순위

골든셋은 **취향을 덮어쓰지 않는다.**

```
1순위  style_preferences.avoided_colors  → must_not (절대 유지)
2순위  골든셋 기피(✕)                    → must_not
3순위  골든셋 주의(△)                    → 감점 (should 제외)
4순위  style_preferences.preferred_colors → 가점
5순위  골든셋 권장(◎)                    → 가점
```

사용자가 "올블랙 기피"라고 했으면 R1이 권장해도 올블랙은 나가지 않는다.

---

## 9. 미해결

1. ~~**v2 팔레트에 `Blue` 추가**~~ — ✅ **완료 (2026-08-06)**. §6 참조.
   같은 방식으로 **중간 명도 퍼플** 추가를 검토한다 — `퍼플` → Lavender가 `visual_effect`를
   중립 → 확장으로 뒤집는 문제가 `블루`와 동일한 구조다.
2. **`멀티` 처리 확정** — `color_rules.json`에 1급 항목으로 재도입할지, `multi_rule`로 남길지.
3. **L1~L5의 JSON화** — §7.
4. **`color` 태그가 아이템당 1개다.** 배색 아이템(네이비 바탕 + 화이트 스트라이프)의 보조색을
   표현할 수 없다. `secondary_color` 필드 추가 검토.
5. **면적 가중치 미반영** — R3의 "대면적"을 코드가 판정하려면 `category_large`별 면적 계수가 필요하다
   (상의/하의 = 대면적, 신발/가방/액세서리 = 소면적).
6. **lossy 매핑 4건의 실효 검증** — 레드/오렌지/옐로우/퍼플이 실제 추천에서 오판을 만드는지 평가.
7. **Confluence 색상 규칙 페이지와의 대조** — 미확보(Atlassian 미인증).
