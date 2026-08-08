# 골든셋 판단 지식 + 보조 점수 앵커 파일럿

골든 이미지를 추천 예시로 직접 노출하지 않고, 이미지에서 확인되는 관계를 사람이
검수한 뒤 조건부 패션 판단 지식으로 만드는 오프라인 파이프라인이다. 메인 산출물은
설명 가능한 조건부 원칙이며, 쌍대 비교에서 얻는 `Q` 상대 점수는 보조 앵커다.

```text
이미지 → VLM 관찰·claim 초안 → 2인 선택형 검수 → 승인 claim
      → 텍스트 LLM 원칙 합성 → 2인 원칙 검수 → 설명 지식 RAG
      └→ 2인 쌍대 비교 → Q 보조 점수 앵커
```

## 빠른 실행 (컨테이너)

원본 코디 사진의 소유자는 S3 버킷이다. 컨테이너는 기동하자마자 지정 prefix를
훑어 아직 처리되지 않은 사진을 찾고, 코디 임베딩 → 아이템 분리·태깅·임베딩 →
Qdrant 적재까지 한 번에 진행한다.

```bash
docker compose -f docker-compose.gpu.yml up -d --build golden-set
docker compose -f docker-compose.gpu.yml logs -f golden-set
```

`GOLDEN_SCAN_INTERVAL_SECONDS=0`(기본)이면 1회 처리 후 종료하므로 배치 잡처럼
필요할 때만 올리면 되고, 양수로 두면 그 간격으로 상주 스캔한다.

"미처리" 판단은 두 층이다.

- 코디 임베딩: `image_embeddings.npz`의 sha 캐시 (로컬 run 볼륨)
- 아이템: `{GOLDEN_S3_OUTPUT_PREFIX}/{version}/{golden_id}/manifest.json` (S3)

로컬 run 볼륨이 날아가도 가장 비싼 단계(아이템별 이미지 편집 호출)는 다시 돌지
않는다.

리포에서 직접 돌릴 때는 아래와 같다.

```bash
python -m ml.golden_set.runner --once
```

## 설계 경계

- 한 이미지는 구조화 멀티모달 호출 한 번으로 관찰·영역·관계·최소 수정 가설을 함께 만든다.
- 사람은 좋은 이유를 처음부터 서술하지 않는다. 모델의 최대 3개 claim을 선택형으로 판정한다.
- 모델 confidence는 사람 검수표에서 숨겨 독립 판단이 끌려가지 않게 한다.
- 단일 이미지의 claim은 곧바로 일반 원칙이나 채점 기준이 될 수 없다.
- `P` 개인 취향, `C` 상황 적합도, `Q` 스타일 의도 내 실행 품질을 섞지 않는다.
- 이미지 쌍대 비교는 `Q_OVERALL_STYLE_EXECUTION`만 측정한다. 사용자 `P`와 `C`는 별도 입력이다.
- 이미지 원본은 Git에 커밋하지 않고 비공개 S3 또는 무시된 로컬 경로에 둔다.
- 파일럿 이미지와 앵커는 사용자 응답에 노출하지 않는다.

## A1~A8 판단 축

| 축 | 의미 | 이미지 단독 기본 처리 |
|---|---|---|
| A1 | 색 조화 | 판정 |
| A2 | 실루엣·비율 | 판정 |
| A3 | TPO 적합성 | 명시 컨텍스트 없으면 보류 |
| A4 | 계절 적합성 | 명시 컨텍스트 없으면 보류 |
| A5 | 보이는 소재·패턴 | 판정, 촉감·정확한 소재는 추정 금지 |
| A6 | 스타일 응집성 | 판정 |
| A7 | 완결성·디테일 | 판정 |
| A8 | 착용자 적합성 | 신체·선호 정보 없으면 보류 |

## 사람 검수량

10장, 이미지당 claim 최대 3개, 비교 쌍 12개를 기준으로 검수자 한 명이 처리하는
선택형 판단은 다음과 같다.

- 이미지 관찰 10행
- claim 최대 30행
- 최소 수정 가설 최대 10행(반례 후보 실험용, 원칙 승인 필수 항목 아님)
- 쌍대 비교 12행
- 합성된 원칙 수만큼의 원칙 검수

서술은 `EDIT` 또는 판단 보류 사유가 있을 때만 작성한다. 같은 템플릿을 검수자마다
별도로 작성한 뒤 행을 합치며, claim·쌍대 비교·원칙 승격은 서로 다른 검수자 2명을
요구한다. 각 질문과 선택지의 정확한 뜻은 실행 시 생성되는 `review_guide.json`이
버전된 계약이다. 다른 검수자에게 전달할 사람용 절차와 작성 예시는
`HUMAN_REVIEW_GUIDE.md`를 사용한다.

## 실행 환경과 입력

```powershell
conda activate final
python -m pip install -r ml/golden_set/requirements.txt
```

`.env.example`의 `GEMINI_API_KEY`, `GOLDEN_*`, `QDRANT_*`, `AWS_*`를 로컬 `.env`,
Infisical 또는 배포 시크릿으로 주입한다. 키를 CSV나 명령행에 적지 않는다.

원본 위치는 환경변수가 정한다.

| 변수 | 뜻 |
|---|---|
| `GOLDEN_S3_BUCKET` | 원본·파생물 버킷 (필수) |
| `GOLDEN_S3_SOURCE_PREFIX` | 코디 원본 prefix |
| `GOLDEN_S3_OUTPUT_PREFIX` | 아이템 이미지·완료 manifest가 쌓이는 prefix |
| `GOLDEN_S3_METADATA_KEY` | 선택. 스타일·계절·TPO 메타데이터 CSV 키 |
| `GOLDEN_DATASET_VERSION` | run 디렉터리와 파생 prefix를 가르는 버전 |
| `GOLDEN_ITEM_PIPELINE` | 아이템 분리 구현 (image-processor 레지스트리 키) |

`metadata.example.csv`를 복사해 입력 메타데이터를 만들고 `GOLDEN_S3_METADATA_KEY`
위치에 올린다. 없으면 메타데이터 없이 진행하며, 이 경우 A3(TPO)·A4(계절)는
보류로 처리된다.

- `usage_scope`: `INTERNAL`, `EVALUATION`, `UNKNOWN`
- `original_exposable`: 파일럿 기본값 `false`
- `presentation_group`: 품질 기준이 아니라 분포·공정성 점검용
- `style`, `season`, `occasion` 등의 다중 값: 세미콜론으로 구분
- `split`: `KNOWLEDGE`, `VALIDATION`, `TEST`
- 확실하지 않은 값은 비워둔다.

10장 파일럿은 성별 표현 그룹 5장씩, 스타일 3종 이상, 유사 비교 쌍 2개 이상,
평가가 갈릴 수 있는 경계 사례 2개 이상을 권장한다.

## 1. manifest·임베딩·클러스터 생성

```powershell
python -m ml.golden_set prepare --limit 10
```

입력은 기본적으로 `GOLDEN_S3_*`가 가리키는 S3 prefix다. run 디렉터리·데이터셋
이름도 환경변수에서 가져오며, 필요하면 `--run-dir`/`--dataset-version`으로
덮어쓴다. 테스트나 오프라인 실험에서는 `--input-dir`로 로컬 디렉터리를 쓸 수
있다.

같은 sha의 코디는 다시 임베딩하지 않는다(모델 버전이 바뀌면 전량 재계산).

GPU·모델 다운로드 없이 구조만 검사할 때는 `--embedding-backend deterministic`을
사용한다. 이 벡터는 테스트 전용이므로 실제 Qdrant에 적재하지 않는다.

## 1-1. 의상 아이템 분리·태깅·임베딩

```powershell
python -m ml.golden_set extract-items
```

image-processor의 `WardrobePipeline`을 그대로 호출한다(열거 → 아이템 이미지
생성 → taxonomy 태깅 → 임베딩). 구현 선택은 `GOLDEN_ITEM_PIPELINE`이 하므로
image-processor에 `sam3-crop`이 등록되면 값만 바꿔 교체된다.

산출물은 `items.jsonl`, `item_embeddings.npz`, 그리고 코디별 S3 manifest다.
아이템 태그 축은 `apps.wardrobe.WardrobeItem`과 동일하다 — 코디의 상의를 옷장
아이템이나 네이버 상품으로 교체하려면 세 저장소가 같은 필터 언어를 써야 한다.

## 2. 이미지 통합 분석

```powershell
python -m ml.golden_set analyze `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --all
```

한 이미지의 출력은 다음을 함께 포함한다.

- 실제로 보이는 아이템, 0~1000 bbox, 보이는 속성과 불확실한 속성
- A1~A8의 `FULL/DEGRADED/UNAVAILABLE`
- 이미지 영역을 참조하는 핵심 claim 최대 3개
- 조화·충돌·중립 및 기여·조건부·단순 묘사 구분
- 스타일 의도를 유지하며 속성 하나만 바꾸는 최소 수정 가설
- 사진만으로 판정할 수 없는 항목과 사유

성공 artifact는 이미지 해시, 모델, 프롬프트, 스키마 버전이 모두 같을 때만 재사용한다.
구형 `golden-analysis-v1` 결과가 있어도 v2 분석을 막지 않는다.

## 3. 선택형 검수표 생성

```powershell
python -m ml.golden_set templates `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --pair-count 12
```

생성 파일:

- `image_observation_reviews.template.csv`: 아이템·영역·판정 불가 처리와 선택적 A축 점수
- `claim_reviews.template.csv`: 근거 정확성 및 기여/묘사/조건부/근거 없음/오류 판정
- `minimum_edit_reviews.template.csv`: 반례·경계 사례 제작용 최소 수정 가설 판정
- `pairwise_reviews.template.csv`: 비교 가능한 쌍의 상대 `Q` 판정
- `review_guide.json`: 질문 문구, 선택지 의미, 1~5 점수 기준, 승격 조건

쌍대 비교 결과는 `left`, `right`, `tie`, `context_dependent`, `unassessable` 중
하나다. 컨텍스트가 달라 공정한 비교가 아니면 억지로 승자를 고르지 않는다.

## 4. 이미지·claim 2인 검수 검증

두 검수자의 행을 합친 뒤 먼저 누락·중복·합의 상태를 검사한다.

```powershell
python -m ml.golden_set validate-reviews `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --observation-reviews local/golden-pilot/observation_reviews.csv `
  --claim-reviews local/golden-pilot/claim_reviews.csv
```

`approved_claims.jsonl`에는 이미지 관찰이 승인되고, 근거가 맞으며,
`CONTRIBUTES` 또는 `CONTEXT_DEPENDENT`로 2인 승인된 claim만 남는다.
`DESCRIPTIVE_ONLY`는 관찰 데이터로 보존할 수 있지만 원칙 합성 근거로 승격하지 않는다.

## 5. 보조 Q 앵커 계산

```powershell
python -m ml.golden_set fit-anchors `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --pairwise-reviews local/golden-pilot/pairwise_reviews.csv `
  --observation-reviews local/golden-pilot/observation_reviews.csv
```

검수자 2명이 완료한 쌍만 사용하며, 비교 그래프가 연결돼야 Bradley-Terry 상대 점수를
계산한다. `context_dependent`와 `unassessable` 표는 점수 계산에서 제외한다.
`anchor_scores.jsonl`의 0~100 점수와 high/mid/low는 파일럿 내부 `Q` 상대값이지
보편적인 패션 점수나 개인화 점수가 아니다.

## 6. 승인 claim으로 원칙 합성

```powershell
python -m ml.golden_set synthesize-principles `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --observation-reviews local/golden-pilot/observation_reviews.csv `
  --claim-reviews local/golden-pilot/claim_reviews.csv
```

이 단계는 이미지를 다시 보내지 않고 승인된 텍스트 claim만 LLM에 전달한다. 원칙은
`applies_when`, `exceptions`, 원본 `golden_id/claim_id`, `knowledge_role`을 가진다.

원칙 역할:

- `EXPLANATION_ONLY`: 추천 이유 설명과 RAG 검색에는 사용 가능, 점수에는 미사용
- `NEEDS_COUNTEREXAMPLE`: 지지 사례만 있어 경계·반례 수집이 더 필요
- `SCORE_AND_EXPLANATION`: 충분한 비교·반례까지 검증된 경우에만 점수와 설명에 사용
- `DISCARD`: 잘못된 일반화 또는 활용 가치 없음

채점 승격은 지지 이미지 3장 이상, 비교·반례 근거 2건 이상, 예외 1개 이상,
검수자 2명 이상, 영역 근거를 모두 요구한다. 현재 10장 첫 사이클은 비교·반례가
충분하지 않을 가능성이 높으므로 `EXPLANATION_ONLY` 또는 `NEEDS_COUNTEREXAMPLE`이
정상 결과다.

최소 수정 가설 자체는 반례가 아니다. 동일 조건의 실제 이미지나 한 속성만 바꾼
시각 변형을 만들고 사람이 결과를 비교한 후에만 비교·반례 근거로 등록할 수 있다.

## 7. 원칙 2인 검수 반영

```powershell
python -m ml.golden_set approve `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --principle-reviews local/golden-pilot/principle_reviews.csv
```

원칙도 2인 승인을 요구한다. 두 수정안이 서로 다르면 자동 병합하지 않고 충돌로
중단한다. 승격 조건이 부족한 `SCORE_AND_EXPLANATION` 요청은 자동으로
`EXPLANATION_ONLY`로 낮춘다.

## 8. PostgreSQL SSOT import

```powershell
python api/manage.py migrate
python api/manage.py import_golden_run `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --observation-reviews local/golden-pilot/observation_reviews.csv `
  --claim-reviews local/golden-pilot/claim_reviews.csv `
  --minimum-edit-reviews local/golden-pilot/minimum_edit_reviews.csv `
  --pairwise-reviews local/golden-pilot/pairwise_reviews.csv `
  --principle-reviews local/golden-pilot/principle_reviews.csv
```

PostgreSQL이 원본 manifest·아이템·분석·사람 검수·원칙의 단일 진실 공급원이다.
쌍대 비교는 좌우 이미지, 검수자, 컨텍스트, 결과, 확신도를 별도 테이블에 보존한다.

골든셋 테이블은 전부 `goldenset` 스키마에 만들어진다(`golden_dataset`,
`golden_image`, `golden_outfit_item`, `golden_analysis`, `golden_principle`,
`golden_principle_evidence`, `golden_review`, `golden_pairwise_review`).
마이그레이션 사용자에게 `CREATE SCHEMA` 권한이 필요하다.

## 9. Qdrant 파생 적재

```powershell
python api/manage.py init_qdrant
python -m ml.golden_set index `
  --run-dir ml/golden_set/runs/pilot-v2 `
  --dry-run
```

계획을 확인한 뒤 `--dry-run`을 제거한다. 컬렉션은 셋이다.

| 컬렉션 | 포인트 | 벡터 |
|---|---|---|
| `outfit_goldenset` | 코디 1장 | image + text |
| `goldenset_items` | 분리된 의상 아이템 1개 | image + text |
| `knowledge` | 승인된 조건부 원칙 | text |

코디 payload의 `items[]`가 아이템 포인트(`point_id`)로 가는 다리이고, 아이템
payload의 `outfit_point_id`가 그 역참조다. 아이템 태그 인덱스는
`products`/`wardrobe`와 동일하므로 "이 코디의 상의를 옷장 아이템으로 교체"가
같은 필터 언어로 성립한다.

코디 포인트는 쌍대 비교 앵커가 없어도 만든다 — 앵커 점수는 있으면 얹는 선택
정보다. 노출 여부는 `GOLDEN_ANCHOR_EXPOSABLE`와 이미지별 `original_exposable`을
모두 만족할 때만 참이다. `--allow-draft`는 격리된 개발 Qdrant에서만 사용한다.

## 주요 산출물 계약

```text
images.jsonl                              원본·권리·해시·split manifest (S3 키 포함)
image_embeddings.npz                      FashionSigLIP 파생 벡터 (ids/shas/vectors)
items.jsonl                               분리된 의상 아이템과 taxonomy 태그
item_embeddings.npz                       아이템 이미지·캡션 벡터
clusters.jsonl                            클러스터·대표·경계 역할
analyses.jsonl                            bbox 관찰·관계 claim·최소 수정 가설
image_observation_reviews.csv             사람 관찰 검수와 선택적 Q 축 점수
claim_reviews.csv                         사람 claim 근거·역할 검수
minimum_edit_reviews.csv                  반례 후보 실험 가설 검수
pairwise_reviews.csv                      사람 상대 Q 비교
approved_claims.jsonl                     2인 승인된 합성 입력
anchor_scores.jsonl                       보조 Q 점수 앵커
principles.jsonl                          조건부 원칙과 이미지 claim 근거
principle_reviews.csv                     사람 원칙 검수
review_validation.json                    누락·보류·합의 검증 결과
qdrant_index_plan.json                    파생 적재 전 개수·상태 확인
```
