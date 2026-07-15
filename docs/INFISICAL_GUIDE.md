# Infisical 온보딩 가이드 (SKN28-FINAL-1Team)

> LLM 대화형 패션 상품 추천 시스템 프로젝트의 시크릿(API 키, DB 비밀번호 등) 관리 가이드입니다.
> Infisical을 처음 쓰는 팀원도 이 문서만 따라 하면 10분 안에 세팅이 끝납니다.

---

## 목차

1. [Infisical이 뭔가요?](#1-infisical이-뭔가요)
2. [사전 준비](#2-사전-준비)
3. [CLI 설치 (OS별)](#3-cli-설치-os별)
4. [로그인](#4-로그인)
5. [프로젝트 연결 — clone하면 끝](#5-프로젝트-연결--clone하면-끝)
6. [환경변수 주입해서 실행하기](#6-환경변수-주입해서-실행하기)
7. [필요한 값 & 찾는 곳](#7-필요한-값--찾는-곳)
8. [트러블슈팅](#8-트러블슈팅)
9. [보안 수칙](#9-보안-수칙)

---

## 1. Infisical이 뭔가요?

지금까지 팀 프로젝트에서 `.env` 파일을 이렇게 주고받았을 겁니다.

> "OO님 .env 파일 카톡으로 보내주세요~"

이 방식에는 문제가 많습니다.

- **유출 위험** — 채팅방에 올라간 API 키는 사실상 영구히 남습니다. 실수로 스크린샷에 찍히거나, 깃허브에 커밋되면 바로 사고입니다.
- **버전 어긋남** — 누군가 키를 하나 추가하면 6명 전원에게 다시 뿌려야 합니다. 한 명이라도 놓치면 "저는 되는데요?" 지옥이 시작됩니다.
- **온보딩 번거로움** — 새 팀원이 오면 어떤 키가 필요한지 일일이 찾아서 전달해야 합니다.

**Infisical**은 이 문제를 해결하는 시크릿 중앙 저장소입니다.

- 시크릿을 웹 대시보드(app.infisical.com)에 한 곳에 저장하고,
- 각자 로컬에서는 CLI가 실행 시점에 환경변수로 **주입**해 줍니다.
- `.env` 파일을 만들 필요도, 주고받을 필요도 없습니다.
- 키가 바뀌면 대시보드에서 한 번만 수정하면 전원에게 즉시 반영됩니다.

```text
[기존]  .env 파일 → 카톡 전송 → 각자 복사 → 버전 어긋남

[이제]  Infisical 대시보드 (중앙 저장)
              │
              ▼
        infisical run --env=dev -- <명령>   ← 실행할 때마다 최신 값 자동 주입
```

---

## 2. 사전 준비

1. **초대 메일 수락** — 팀원 전원이 이미 Infisical 조직에 초대되어 있습니다. 메일함에서 Infisical 초대 메일을 찾아 **Accept**를 누르고 계정을 만드세요. (스팸함도 확인!)
2. **웹 로그인 확인** — [https://app.infisical.com](https://app.infisical.com) 에 접속해서 로그인이 되는지, 우리 팀 프로젝트가 보이는지 확인합니다.

> **중요**: 우리 팀은 Infisical Cloud **US 리전**(`https://app.infisical.com`)을 사용합니다. EU 리전(`eu.infisical.com`)이 아닙니다. 이 사실은 뒤의 로그인 단계에서 다시 나옵니다.

---

## 3. CLI 설치 (OS별)

### macOS (Homebrew)

```bash
brew install infisical/get-cli/infisical
```

나중에 업데이트할 때:

```bash
brew update && brew upgrade infisical
```

### Windows — 방법 A: Scoop

```powershell
scoop bucket add org https://github.com/Infisical/scoop-infisical.git
scoop install infisical
```

### Windows — 방법 B: Winget

```powershell
winget install infisical
```

### 공통 대안: NPM (Node.js가 있다면 OS 무관)

```bash
npm install -g @infisical/cli
```

### Debian / Ubuntu (WSL 포함)

```bash
curl -1sLf 'https://artifacts-cli.infisical.com/setup.deb.sh' | sudo -E bash
sudo apt-get update && sudo apt-get install -y infisical
```

### 설치 확인

```bash
infisical --version
```

버전 번호가 출력되면 성공입니다.

---

## 4. 로그인

터미널에서 아래 명령을 실행합니다.

```bash
infisical login
```

브라우저가 자동으로 열리면서 로그인 화면이 나옵니다.

> **가장 많이 하는 실수 주의!**
> 로그인 과정에서 **리전(region) 선택**이 나오면 반드시 **US (Infisical Cloud, app.infisical.com)** 를 선택하세요.
> **EU를 선택하면 우리 프로젝트가 아예 보이지 않습니다.** ("프로젝트가 없어요"의 원인 1위)

### 브라우저를 못 여는 환경이라면 (WSL2, 컨테이너, Codespaces 등)

```bash
infisical login -i
```

`-i` 플래그로 브라우저 없이 터미널에서 인터랙티브 로그인을 할 수 있습니다.

---

## 5. 프로젝트 연결 — clone하면 끝

레포를 clone하면 루트에 `.infisical.json` 파일이 이미 들어 있습니다.

```bash
git clone https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN28-FINAL-1Team.git
cd SKN28-FINAL-1Team
```

`.infisical.json`의 내용은 이렇습니다.

```json
{
    "workspaceId": "38702d5a-31b6-422b-85c6-21270c2c1d36",
    "defaultEnvironment": "dev",
    "gitBranchToEnvironmentMapping": null
}
```

- 이 파일이 있으면 CLI가 **어느 Infisical 프로젝트에 연결할지 자동으로 인식**합니다.
- 따라서 **`infisical init`을 다시 실행할 필요가 없습니다.** clone → login → 끝.
- 이 파일에는 프로젝트 식별자만 있고 민감정보가 없으므로 **커밋해도 안전**합니다. (실제로 커밋되어 있습니다.)

> `infisical init`은 **완전히 새로운 프로젝트**에서 `.infisical.json`을 처음 만들 때만 사용합니다. 우리 레포에서는 실행하지 마세요.

---

## 6. 환경변수 주입해서 실행하기

핵심 패턴은 하나입니다.

```bash
infisical run --env=<환경> -- <실행할 명령>
```

`--` 뒤에 평소 쓰던 명령을 그대로 붙이면, Infisical이 시크릿을 환경변수로 주입한 상태로 그 명령을 실행해 줍니다.

### 예시

Python 스크립트 실행 (우리 팀은 uv 사용):

```bash
infisical run --env=dev -- uv run python main.py
```

프론트엔드 개발 서버:

```bash
infisical run --env=dev -- npm run dev
```

Docker Compose로 DB 띄우기:

```bash
infisical run --env=dev -- docker compose up -d db
```

### 알아두기

- `--env`의 기본값은 `dev`라서 생략해도 동작하지만, **습관적으로 명시하는 것을 권장**합니다. 나중에 staging/prod 환경이 분리되면 실수를 막아 줍니다.
- 현재 어떤 시크릿이 들어 있는지 확인하려면:

```bash
infisical secrets
```

- 정말 `.env` 파일이 필요한 비상 상황(예: Infisical을 지원하지 않는 툴)에서만:

```bash
infisical export --format=dotenv > .env
```

  사용이 끝나면 **반드시 삭제**하고, `.env`가 `.gitignore`에 있는지 확인하세요.

---

## 7. 필요한 값 & 찾는 곳

| 값 | 어디서 찾나 | 언제 필요 |
|---|---|---|
| **Organization ID** | 우리 팀 값: `695b1587-8992-48fa-900a-617097766342`. 직접 확인하려면 app.infisical.com 접속 → 좌측 하단 조직 메뉴 → **Organization Settings**에서 복사. 브라우저 주소창 URL `app.infisical.com/organization/...` 경로에서도 확인 가능 | 비대화형 로그인(`infisical login --organization-id ...`)이나 CI/CD에서만. **일반 팀원의 브라우저 로그인에는 불필요** |
| **Project ID** (= workspaceId) | 우리 팀 값: `38702d5a-31b6-422b-85c6-21270c2c1d36` (레포의 `.infisical.json`과 동일). 직접 확인하려면 프로젝트 → **Settings** 탭에서 Project ID 복사 | `--projectId` 플래그를 쓸 때. 레포 안에서는 `.infisical.json`이 있어 자동 인식되므로 보통 불필요 |
| **Environment slug** | 프로젝트 대시보드 상단의 환경 탭 (dev / staging / prod) | `infisical run --env=<slug>` |
| **Machine Identity Client ID/Secret** | 조직 → **Access Control** → **Identities**에서 생성 | CI/CD, 서버 배포용. **개인 로컬 개발에는 불필요** |

요약: **일반 팀원은 아무 ID도 외울 필요 없습니다.** 브라우저 로그인 + 레포의 `.infisical.json`이 전부 처리해 줍니다.

---

## 8. 트러블슈팅

### (a) 로그인했는데 프로젝트가 안 보여요

두 가지 원인이 대부분입니다.

1. **EU 리전으로 로그인함** — `infisical login`을 다시 실행하고 리전 선택에서 **US (app.infisical.com)** 를 선택하세요.
2. **조직 초대를 아직 수락하지 않음** — 메일함(스팸함 포함)에서 초대 메일을 찾아 수락한 뒤 다시 로그인하세요.

### (b) 시크릿이 안 보이거나 빈 값으로 나와요

1. **환경 슬러그 확인** — `--env=dev`처럼 올바른 환경을 지정했는지 확인하세요. 시크릿은 환경별로 따로 저장됩니다. `infisical secrets --env=dev`로 실제 값 목록을 확인해 보세요.
2. **프로젝트 멤버 권한 확인** — 조직에는 들어왔지만 프로젝트 멤버로 추가되지 않았을 수 있습니다. 데이터 담당자(관리자)에게 프로젝트 멤버 추가를 요청하세요.

### (c) WSL에서 브라우저가 안 열려요

WSL2, 컨테이너, 원격 서버 등에서는 브라우저 자동 실행이 안 될 수 있습니다. 인터랙티브 모드를 사용하세요.

```bash
infisical login -i
```

### (d) 예전 로그인이 꼬인 것 같아요

다른 계정/리전으로 로그인했던 흔적이 남아 이상하게 동작할 때는, 그냥 다시 로그인하면 됩니다.

```bash
infisical login
```

재로그인 시 리전(US)과 계정을 올바르게 선택하세요.

---

## 9. 보안 수칙

1. **시크릿 원문을 카톡/디스코드/커밋에 올리지 않기** — 값 공유가 필요하면 "Infisical 대시보드의 dev 환경에 추가했어요"라고 알리는 것으로 충분합니다.
2. **`infisical export`로 만든 `.env`는 쓰고 바로 삭제** — 그리고 `.env`가 `.gitignore`에 포함되어 있는지 항상 확인하세요.
3. **`.infisical.json`은 커밋해도 됩니다** — 프로젝트 식별자만 들어 있고 비밀값이 없습니다. 실수로 지우지 마세요.
4. 실수로 시크릿을 유출했다면 숨기지 말고 **즉시 팀에 알리고 해당 키를 재발급(rotate)** 하세요. 유출된 키는 되돌릴 수 없고, 교체만이 답입니다.

---

궁금한 점이 있으면 데이터 담당자에게 문의하세요. 즐거운 개발 되세요!
