# SKN28-FINAL-1Team — 데이터 담당자 노트

## 프로젝트

**LLM 활용 대화형 패션 상품 추천 시스템**
사용자의 옷장 데이터, 날씨, 추구미(스타일 레퍼런스)를 분석해 AI 캐릭터와의 대화를 통해 개인화된 패션 상품을 추천하는 대화형 추천 시스템.

- 기획안: https://jjeoe0317.atlassian.net/wiki/x/AwAN

## 내 역할: 데이터 담당자

데이터 수집·정제 및 추천 룰(RAG용 데이터 자산) 설계를 담당한다.

### 작업 체크리스트

- [ ] **날씨별 추천 룰 작성** — 기온, 강수, 계절별 추천 규칙
  - 현황: `data/weather/weather_outfit_rules.json` 초안 존재 (기온 구간 7개 + 비/눈/강풍 조건). 검증·보완 필요.
- [ ] **색상/아이템 조합 룰 작성** — 기본 컬러 매칭, 아이템 조합 규칙 정리
  - 현황: 미착수. `data/style/style_definitions.json`에 스타일별 `color_palette`는 있지만, 범용 컬러 매칭·아이템 조합 규칙은 별도로 없음.

### `data/` 폴더 현황

| 경로 | 내용 | 상태 |
| --- | --- | --- |
| `weather/weather_outfit_rules.json` | 기온·날씨(비/눈/강풍)별 코디 룰 | 초안 |
| `tpo/tpo_outfit_rules.json` | TPO(출근/면접/데이트/결혼식/주말/여행/운동/파티)별 코디 룰 | 초안 |
| `style/style_definitions.json` | 스타일(미니멀/스트릿/캐주얼/시크/페미닌/빈티지/스포티/프레피) 정의 및 컬러 팔레트 | 초안 |
| `upload_to_drive.py` | 위 룰 JSON들을 팀 공유 구글 드라이브(RAG용)로 업로드 | 완료 |

## 에이전트

데이터 정제/룰 작성 작업은 `final` 서브에이전트(`.claude/agents/final.md`)에게 위임할 수 있다.

## S3(`skn28-cozy`) 데이터셋 분석 진행 상황

각 폴더 분석 결과는 `data/<폴더명>/README.md`(또는 `readme.md`)에 저장 (요약 → S3 구조 상세+실측 근거 → 라벨링·메타데이터 기반 추천 시스템 활용 방안 → 출처/Confluence 링크 순서).

| S3 경로 | 로컬 폴더 | readme | 핵심 데이터 | 상태 |
| --- | --- | --- | --- | --- |
| `03_패션 상품 및 착용 영상/` | `data/03_패션상품_착용영상/` | `README.md` (재분석·보완) | winfo 기반 코디 JSON, Item/Model 이미지 + Pose·Parse 라벨 | 재분석(보완) 완료 + 아티팩트 HTML |
| `05_huggingface_polyvore_outfits/` | `data/05_polyvore_outfits/` | `README.md` | 68k 코디 + 261k 아이템 메타, parquet 이미지, compatibility/FITB 라벨 | 완료 + 아티팩트 HTML |
| `10.한국_신체_3D_스캐닝_데이터/` | `data/10_한국인_3D스캐닝/` | `README.md` | 477명 3D mesh + 32 keypoint 3D·2D + 실측치 (`actor` 필드) | 완료 + 아티팩트 HTML |
| `11. 한국전자통신研究院_자율성장 인공지능 기술검증(PoC)을 위한 패션 코디 데이터셋/` | `data/11_PoC_패션코디/` | `README.md` | 대화 7,236건 + 아이템 2,603개(F/M/C/E 속성) + 이미지 3,351장 | 완료 + 아티팩트 HTML |
| `12.한국전자통신연구원_FASCODE/` | `data/12_FASCODE/` | `README.md` | Fashion-How 2024: subtask1·2(속성 분류), subtask3·4(대화형 코디 로그) | 완료 + 아티팩트 HTML |
| `20.한국인_전신_형상_및_치수_측정_데이터/` | `data/20_전신형상치수/` | `README.md` | 992명 3D mesh + 39개 실측치 CSV + 2D 다각도 폴리곤 라벨 | 완료 + 아티팩트 HTML |
| `22.사이즈코리아/` | `data/22_사이즈코리아/` | `data/22_사이즈코리아/README.md` | 한국인 인체 치수 측정 데이터 (S3 실측 기반 분석) | README 완료 + 아티팩트 HTML |
| `23.공공데이터_의류생활체육_추천데이터/` | `data/23_공공데이터_의류생활체육/` | `README.md` | 남성 모델 전신 사진 + 스타일 라벨 (hippie/bold/hiphop), 코호트별 폴더 분리 | 완료 + 아티팩트 HTML |
| `26_K_Fashion/` | `data/26_K_Fashion/` | `README.md` | 한국콘텐츠진흥원 K-Fashion 데이터셋: 263,302 JPG + 393,802 JSON, bbox+polygon+스타일+9종 속성 라벨 | 완료 + 아티팩트 HTML |
| `4_HM_Personalized_Fashion_Recommendations/` | `data/04_HM_추천데이터/` | `data/04_HM_추천데이터/README.md` | H&M 개인화 추천 데이터 (거래·고객·상품 메타, S3 실측 기반 분석) | README 완료 + 아티팩트 HTML |
| `01_의류통합데이터/` | `data/01_의류통합데이터/` | `README.md` | 12카테고리 의류 이미지 ~887k 파일 + 66필드 어노테이션 JSON (의류 속성 + 모델 신체 사이즈) | 완료 + 아티팩트 HTML |
| `fashion-data/` | `data/fashion-data/` | (없음) | 로컬에 미보관, S3: `fashion-data/` (용도 불명, 확인 필요) | 미수령 |
| `sample/` | `data/sample/` | (없음) | 로컬에 미보관, S3: `sample/` (용도 불명, 확인 필요) | 미수령 |

다음 호출 시: "S3 데이터 분석 이어서 해줘" → 이 표에서 "미수령" 또는 "확인 필요" 상태부터 3개씩 배치로 진행. 분석 진행 시점 기준 라인업:

- **완료(상세 readme 보유)**: 03, 05, 10, 11, 12, 20, 22, 23, 26, 01, 04 — 11종. 추천 룰/RAG/SFT 데이터로 즉시 활용 가능.
- **확인 필요**: `fashion-data/`, `sample/` — S3 경로는 존재하나 콘텐츠/용도가 모호.
