# n8n 셀프호스팅 — 데이터 분석 파이프라인

S3(`s3://skn28-cozy`) 패션 데이터셋의 스캔 → 정제 → 임베딩 파이프라인을 n8n으로 오케스트레이션하기 위한 준비물.
작성: 2026-07-09, 담당: 전하영(데이터)

> **현재 상태**: 이 EC2에는 docker가 없고(무암호 sudo도 불가), 서버 자체가 비용 문제로 사용 중단 예정이다.
> **결론: 윈도우/맥 로컬(Docker Desktop)에서 띄우는 것을 권장한다.** 아래 (b)는 만약을 위한 EC2 절차.

---

## (a) 윈도우 Docker Desktop 기동 절차 — 권장 (단계별)

데이터 처리는 파이썬(`python3`)이 하고 n8n은 트리거·순서·알림을 담당한다.
Execute Command 노드가 컨테이너 안에서 `python3 /repo/...` 를 돌릴 수 있도록,
compose 는 (1) 레포 루트를 `/repo` 로 마운트하고 (2) `Dockerfile` 로 python3·uv·aws-cli 를 넣은 이미지를 빌드한다.

### 0. 준비물 확인
- **Docker Desktop 실행 중** (WSL2 백엔드 활성화). 트레이 아이콘이 초록/실행 상태인지 확인.
  - 확인: PowerShell 에서 `docker version` 이 서버(Server) 정보까지 출력되면 OK.
- **Infisical CLI 로그인**. (설치: `scoop install infisical` 또는 `winget install Infisical.infisical-cli`)
  - 확인: `infisical user` 로 로그인 계정이 보이면 OK. 아니면 `infisical login`.
  - 프로젝트에 비밀값이 등록돼 있어야 함: `AWS_ACCESS_KEY_ID`,
    `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (**팀 계정 071853465256** 키). → [(c)](#c-infisical로-환경변수-주입해-실행) 참조.
    (`N8N_USER`/`N8N_PASSWORD` 는 더 이상 불필요 — n8n 2.x 에서 basic auth 제거됨)

### 1. 워크스페이스 폴더로 이동
```powershell
cd <repo>\data\pipeline\n8n
```
(`<repo>` = SKN28-FINAL-1Team 레포 루트. compose 가 `../../..` 를 `/repo` 로 마운트하므로 반드시 이 폴더에서 실행.)

### 2. 환경변수 주입해 기동 (첫 실행은 이미지 빌드 때문에 수 분 소요)
```powershell
infisical run --env=dev -- docker compose up -d --build
docker compose logs -f n8n   # "Editor is now accessible" 뜨면 기동 완료 (Ctrl+C 로 로그 빠져나옴)
```

### 3. 접속·로그인
- 브라우저에서 http://localhost:5678 → **첫 접속 시 오너 계정 생성** 화면이 뜬다 (이메일/이름/비밀번호 입력).
  n8n 2.x 부터 basic auth 가 제거되어 이 방식만 지원. 계정 정보는 named volume(`n8n_data`)에 저장돼 재기동 후에도 유지된다.

### 4. 워크플로 3종 Import
- 좌측 상단 **Workflows → Import from File** (또는 `⋯` 메뉴 → Import from File)
- `data/pipeline/`에 있는 워크플로 JSON을 순서대로 불러온다:
  1. `01_workflow_s3_scan.json`
  2. `02_workflow_cleaning.json`
  3. `03_workflow_embedding.json`
- Import 후 **워크플로 ID 연결**: 워크플로 1의 *Trigger Cleaning Workflow* 노드와
  워크플로 2의 *Trigger Embedding Workflow* 노드의 `workflowId` 자리표시자
  (`WORKFLOW_ID_CLEAN`, `WORKFLOW_ID_EMBED`)를 Import된 실제 워크플로로 다시 선택해준다.
- **Credentials 등록**: Slack 알림을 쓸 때만 Slack 자격증명을 각 노드에 연결한다.
  AWS 자격증명은 Infisical 환경변수로 `s3_scan.py`와 AWS CLI에 직접 주입된다.

### 5. 수동 1회 실행으로 검증
- 워크플로 1(S3 스캔)을 열고 우측 상단 **Execute Workflow** → S3 리스트/ diff / Slack 알림까지 도는지 확인.
- 워크플로 2·3 은 Webhook 트리거이므로, 각 노드를 **Execute step** 으로 하나씩 눌러
  `python3 /repo/...` 명령이 컨테이너 안에서 실행되는지(경로·권한) 확인.
  - Execute Command 노드 실패 시: `docker compose exec n8n python3 --version` / `docker compose exec n8n ls /repo/data/pipeline/scripts` 로 파이썬·마운트 상태 점검.
- 워크플로 3의 실제 임베딩에는 `torch`, `transformers`, `Pillow`, `qdrant-client`와 모델 실행 환경이 필요하다.
  현재 경량 n8n 이미지에는 이 의존성을 넣지 않았으므로 GPU 워커를 연결하기 전에는 워크플로 1·2까지만 실행 검증한다.

### 6. 중지
```powershell
docker compose down          # 컨테이너 정지·삭제 (워크플로는 named volume 에 유지)
# 데이터까지 완전 삭제하려면: docker compose down -v
```
워크플로 데이터는 named volume `n8n_data` 에 저장되어 컨테이너를 지워도 유지된다.

## (b) 이 EC2에서 띄울 경우 (비권장 — 서버 중단 예정)

1. docker 설치 필요 (sudo 필요 — 현재 이 계정은 무암호 sudo 불가, 관리자에게 요청):
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER   # 재로그인 필요
   ```
2. 기동: `infisical run --env=dev -- docker compose up -d` (이 폴더에서)
3. **UI 접근은 보안그룹 5678 개방 대신 SSH 터널 권장**:
   ```bash
   # 로컬 PC에서 실행 — 이후 로컬 브라우저에서 http://localhost:5678
   ssh -L 5678:localhost:5678 <user>@<EC2-호스트>
   ```
   보안그룹을 열면 기본 인증만으로 인터넷에 노출되므로 터널이 안전하다.

## (c) Infisical로 환경변수 주입해 실행

비밀값(`N8N_USER`, `N8N_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)은
`.env` 파일이나 셸 히스토리에 남기지 말고 Infisical로 주입한다:

```bash
# 프로젝트에 비밀값 등록 후 (infisical secrets set ... 또는 웹 UI)
infisical run --env=dev -- docker compose up -d

# 내려받기/재시작도 동일하게
infisical run --env=dev -- docker compose restart
docker compose down          # 비밀값 불필요한 명령은 그냥 실행
```

주의: AWS 자격증명은 **팀 계정(071853465256)** 것이어야 한다.
현재 이 EC2의 role(my-server-role, 계정 442650749115)은 `s3://skn28-cozy`에 403이므로, 로컬 실행 시에도 팀 계정 IAM 키를 Infisical에 넣어 쓴다.

---

## 파이프라인 설계 3가지

공통 원칙: **무거운 처리는 파이썬이 하고, n8n은 트리거·순서·알림만 담당한다.** (아래 "정직한 평가" 참조)

### 1. S3 인벤토리 스캔 — 신규 파일 감지

```
[Schedule Trigger: 매일 09:00 KST]
  → [Execute Command: python3 /repo/data/pipeline/01_s3_scan.py]
  → [Code 노드: 스캔 리포트 파싱 → 신규/변경 키 목록 산출]
  → [IF 노드: 신규 파일 있음?]
      ├─ true → [Slack/Discord 노드: "신규 N건" 알림] → [Execute Workflow: 파이프라인 2 트리거]
      └─ false → 종료
```

### 2. 데이터 정제 배치 — EUC-KR 변환, JSON 검증

```
[Execute Workflow Trigger (파이프라인 1에서 호출) 또는 Manual Trigger]
  → [Execute Command: python3 /repo/data/pipeline/02_clean_encoding.py --batch <키 목록>]
     (EUC-KR → UTF-8 변환. 스크립트가 S3 다운로드/업로드까지 담당)
  → [Execute Command: python3 /repo/data/pipeline/02_validate_json.py --batch <로컬 JSON 목록>]
  → [Code 노드: 스크립트 stdout(JSON 리포트) 파싱 → 성공/실패 건수 집계]
  → [IF 노드: 실패 있음?]
      ├─ true → [Slack/Discord 노드: 실패 목록 알림 (수동 확인 필요)]
      └─ false → [Execute Workflow: 파이프라인 3 트리거]
```
※ Execute Command 노드는 n8n **컨테이너 안**에서 실행되므로, 파이썬 스크립트를 쓰려면
   레포 디렉토리를 볼륨 마운트하고 컨테이너에 uv를 넣거나, 대신 **호스트에서 도는 워커를 Webhook으로 호출**하는 방식을 쓴다.
   후자가 깔끔하다: n8n → [HTTP Request 노드] → 호스트의 FastAPI 워커(`uv run uvicorn ...`) → 처리 후 콜백.

### 3. 임베딩 파이프라인 오케스트레이션 — Qdrant 업서트

팀 RAG 스택: **Qdrant + Marqo-FashionSigLIP** (`docs/fashion-rag-embedding-pipeline_1.md` 참조 — origin/main 기준).

```
[Execute Workflow Trigger (파이프라인 2 완료 시)]
  → [Execute Command / HTTP Request: uv run python embed_pipeline.py --keys <정제 완료 키 목록>]
     (Marqo-FashionSigLIP으로 이미지+텍스트 임베딩 — GPU/CPU 무거운 연산은 전부 스크립트 안에서)
  → [Execute Command: uv run python qdrant_upsert.py --collection fashion_items]
     (또는 스크립트 하나가 임베딩→업서트까지 묶어서 처리하고 n8n은 한 번만 호출)
  → [HTTP Request 노드: Qdrant /collections/fashion_items → 포인트 수 검증]
  → [IF 노드: 예상 건수와 일치?]
      ├─ true → [Slack/Discord 노드: "임베딩 N건 업서트 완료"]
      └─ false → [Slack/Discord 노드: 불일치 경고 + 실행 로그 링크]
```

---

## 정직한 평가 — 지금 n8n이 필요한가?

- **무거운 데이터 처리를 n8n 노드로 직접 하지 마라.** 수십 GB 이미지 다운로드, 임베딩 연산을 n8n Code/S3 노드로 돌리면 메모리·타임아웃·재시도 지옥이다. n8n은 "언제 무엇을 실행할지"만 정하고, 실제 처리는 `uv run` 파이썬 스크립트(또는 워커 API)가 한다. 위 설계 3가지가 전부 이 구조인 이유다.
- **지금 단계(탐색적 분석)에서는 n8n 없이도 충분하다.** 현재 작업은 데이터셋별 1회성 분석·README 작성이고, 이건 스크립트 + 수동 실행이 더 빠르고 디버깅도 쉽다.
- **n8n의 가치는 "반복 배치"가 생기는 시점부터다.** 신규 데이터 주기적 감지, 크롤링 스케줄, 정제→임베딩→업서트가 정례화되면 그때 이 compose를 띄우면 된다. 그 전에 미리 띄워두면 유지비(업데이트, 자격증명 관리)만 든다.
- 파이프라인 스크립트 4종(`s3_scan.py`, `clean_encoding.py`, `validate_json.py`, `embed_pipeline.py`)은 `data/pipeline/`에 있다.
  다만 `embed_pipeline.py`의 FashionSigLIP 모델 실행 환경과 Qdrant 업서트 구현은 GPU 워커 쪽에서 완성해야 한다.
