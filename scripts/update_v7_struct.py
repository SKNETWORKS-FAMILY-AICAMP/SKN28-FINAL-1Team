import requests
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

env = {}
with open(r"C:\Users\Playdata\atlassian.env", encoding="utf-8") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k] = v.strip().strip("'").strip('"')

auth = (env['ATLASSIAN_EMAIL'], env['ATLASSIAN_API_TOKEN'])
base = env['ATLASSIAN_URL']
headers = {"Accept": "application/json", "Content-Type": "application/json"}

page_id = "45744129"

# 1. v6_body.html 읽기 (원래 v6/v7 Confluence 문서 구조)
with open(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\scripts\v6_body.html", "r", encoding="utf-8") as f:
    v6_html = f.read()

# 2. 초대 -> 참여 흐름 ASCII 및 내용 부분 수정
old_invite_flow = """  방장                                              받는 사람
17:    │
18:    │ 방 개설 (개설자가 자동 owner)
19:    │   └─ 초대코드 6자리 동시 발급 (24시간)
20:    │
21:    ├── 초대 링크 {origin}/invite?code=XXXXXX ──────▶ │
22:    │     (카톡 공유 / 링크 복사)                     │
23:    │                                                 ├─ 로그인 O ─▶ 가입
24:    │                                                 │              · 정원 6명 검사 (행 잠금)
25:    │                                                 │              · 이미 멤버면 그냥 입장
26:    │                                                 │              · 24h 지났으면 거부
27:    │                                                 │
28:    │                                                 └─ 로그인 X ─▶ preview (구경만)
29:    │                                                                · 서버에 기록 안 남김
30:    │                                                                · 실명 대신 익명 라벨
31:    │                                                                · 방·옷 UUID 안 내려줌
32:    ├── 코드 재발급 (owner만) ─ 기존 코드 즉시 무효화"""

new_invite_flow = """  방장                                              받는 사람 (초대 링크 클릭)
 1:    │
 2:    │ 방 개설 (개설자가 자동 owner)
 3:    │   └─ 초대코드 6자리 동시 발급 (24시간)
 4:    │
 5:    ├── 초대 링크 {origin}/invite?code=XXXXXX ──────▶ │
 6:    │     (카톡 공유 / 링크 복사)                     │
 7:    │                                                 ├─ 로그인 O ─▶ 수동 버튼 누름 없이 자동 joinSharedRoom 수락
 8:    │                                                 │              · 정원 6명 검사 (행 잠금)
 9:    │                                                 │              · 이미 멤버면 즉시 입장
10:    │                                                 │              · 해당 방 (closet?tab=shared&room=roomId) 직통 진입
11:    │                                                 │
12:    │                                                 └─ 로그인 X ─▶ /login?redirect=... 로그인 페이지 즉시 직행
13:    │                                                                · 로그인 완료 시 원래 초대 링크로 복귀
14:    │                                                                · 복귀 후 자동 수락 및 초대방 직통 입장
15:    ├── 코드 재발급 (owner만) ─ 기존 코드 즉시 무효화"""

# 만약 line number 포함해서 매칭되지 않는 경우 대안
if old_invite_flow not in v6_html:
    # 부분 치환
    v6_html = v6_html.replace("preview (구경만)", "/login?redirect=... 로그인 페이지 즉시 직행")
    v6_html = v6_html.replace("· 서버에 기록 안 남김", "· 로그인 완료 시 원래 초대 링크로 자동 복귀하여 가입 처리")
    v6_html = v6_html.replace("├─ 로그인 O ─▶ 가입", "├─ 로그인 O ─▶ 버튼 대기 없이 자동 수락 후 해당 초대방(room=roomId) 직통 진입")
else:
    v6_html = v6_html.replace(old_invite_flow, new_invite_flow)

# 정책 요약 표 수정 (초대 코드 및 레이아웃 관련)
v6_html = v6_html.replace(
    "영대문자+숫자 6자리(약 21억 조합) &middot; <strong>24시간</strong> 만료 &middot; owner만 재발급",
    "영대문자+숫자 6자리 &middot; <strong>24시간</strong> 만료 &middot; owner만 재발급 &middot; <strong>미로그인 시 로그인 페이지 직행 &amp; 로그인 시 해당 초대방 직통 진입</strong>"
)

# 상단 여백 대칭 및 가로 스크롤 정책 추가
old_policy_end = "</tbody></table><h2 local-id=\"5309d7d46526\">3. API</h2>"
new_policy_end = """<tr ac:local-id="spacing_policy_tr"><td ac:local-id="spacing_policy_td1"><p local-id="spacing_policy_p1">상단 레이아웃</p></td><td ac:local-id="spacing_policy_td2"><p local-id="spacing_policy_p2">필터&rarr;방목록(12px) = 방목록&rarr;초대행(12px) <strong>1:1 대칭 수직 간격 튜닝</strong> &middot; 방 목록 <strong>가로 한 줄 스크롤(ScrollView horizontal)</strong> 적용</p></td></tr>""" + old_policy_end

v6_html = v6_html.replace(old_policy_end, new_policy_end)

# 상태 표 커밋 및 EAS 배포 갱신
v6_html = v6_html.replace(
    "<code>feature/shared-wardrobe</code> (검증 기준 커밋 <code>4cc6e71</code>)",
    "<code>feature/shared-wardrobe-mybuild</code> (최신 커밋 <code>83202f3</code> &middot; EAS 배포 완료)"
)

# 3. Confluence PUT API 호출 (버전 10 -> 11)
get_url = f"{base}/wiki/rest/api/content/{page_id}?expand=version"
r_get = requests.get(get_url, auth=auth, headers=headers)
current_version = r_get.json()['version']['number']
new_version = current_version + 1
title = r_get.json()['title']

payload = {
    "id": page_id,
    "type": "page",
    "title": title,
    "version": {
        "number": new_version,
        "message": "Update Confluence v7 original layout: direct invite auth flow, 12px equal spacing, horizontal scroll"
    },
    "body": {
        "storage": {
            "value": v6_html,
            "representation": "storage"
        }
    }
}

r_put = requests.put(f"{base}/wiki/rest/api/content/{page_id}", auth=auth, headers=headers, json=payload)
print("PUT Status Code:", r_put.status_code)
if r_put.status_code == 200:
    print(f"Successfully restored v7 layout and updated contents to version {new_version}!")
else:
    print("PUT Error:", r_put.text)
