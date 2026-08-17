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

# 1. v6_body.html 읽기 (v6/v7 Confluence 문서 원본 구조)
with open(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\scripts\v6_body.html", "r", encoding="utf-8") as f:
    v6_html = f.read()

# 2. 초대 -> 참여 흐름 갱신
v6_html = v6_html.replace("preview (구경만)", "/login?redirect=... 로그인 페이지 즉시 직행")
v6_html = v6_html.replace("· 서버에 기록 안 남김", "· 로그인 완료 시 원래 초대 링크로 자동 복귀하여 가입 처리")
v6_html = v6_html.replace("├─ 로그인 O ─▶ 가입", "├─ 로그인 O ─▶ 수동 버튼 누름 없이 자동 joinSharedRoom 수락 후 초대방(room=roomId) 직통 진입")

# 3. 탈퇴 처리 ASCII 흐름도 및 설명 명확화 갱신
old_leave_flow = """  탈퇴 요청
32:    │
33:    ├─ 내 옷을 어떻게? ──┬─ delete_my_items=true  ─▶ 내가 올린 공유 옷 일괄 삭제
34:    │                    └─ delete_my_items=false ─▶ 옷은 방에 남기고
35:    │                                                registered_by = NULL  (기부)
36:    │
37:    └─ 내가 owner였나? ──┬─ 아니오 ─▶ 나만 빠짐
38:                         └─ 예 ─────▶ joined_at 가장 빠른 멤버에게 owner 자동 위임
39:                                       (남은 인원 0명일 때만 방 삭제)"""

new_leave_flow = """  공유 옷장 아이템 공유 해제 및 방 삭제(탈퇴) 요청
   │
   ├─ 아이템 단건 공유 해제 ──▶ 개인 옷장 원본 보존 + 해당 방의 SharedWardrobeItem 관계 행만 DELETE
   │
   └─ 공유한 방 삭제(탈퇴) ─▶ 사용자 멤버 탈퇴 처리 (DELETE /leave/) — ★ 방을 폭파하지 않는 것이 핵심
        │
        ├─ 내 옷 처리 ────┬─ delete_my_items=true  ─▶ 이 방에 내가 올린 공유 옷 일괄 공유 해제
        │                 └─ delete_my_items=false ─▶ 옷은 방에 남겨두고 registered_by = NULL (기부)
        │
        └─ 방장(owner)인가? ──┬─ 아니오 (일반 멤버) ─▶ 나만 멤버십 삭제 후 탈퇴 완료 (방 유지)
                              └─ 예 (방장) ──────────▶ joined_at 가장 빠른 멤버에게 owner 자동 위임
                                                       (남은 멤버가 0명일 때만 방 자동 삭제)"""

v6_html = v6_html.replace(
    "<strong>탈퇴 처리</strong> &mdash; 방을 폭파하지 않는 것이 핵심이다.",
    "<strong>아이템 공유 해제 및 방 삭제(탈퇴) 처리</strong> &mdash; 옷은 단건 공유 해제 가능하며, 방 삭제 시 방을 폭파하지 않고 멤버만 탈퇴하는 것이 핵심이다."
)

if "32:    │" in v6_html:
    v6_html = v6_html.replace(old_leave_flow, new_leave_flow)
else:
    # 텍스트 치환
    v6_html = v6_html.replace(
        "내가 올린 공유 옷 일괄 삭제",
        "내가 올린 공유 옷 일괄 공유 해제 (개인 옷장 원본은 안전 보존)"
    )

# 4. 정책 요약 표 항목 갱신 및 확인
v6_html = v6_html.replace(
    "영대문자+숫자 6자리(약 21억 조합) &middot; <strong>24시간</strong> 만료 &middot; owner만 재발급",
    "영대문자+숫자 6자리 &middot; <strong>24시간</strong> 만료 &middot; owner만 재발급 &middot; <strong>미로그인 시 로그인 페이지 직행 &amp; 로그인 시 해당 초대방 직통 진입</strong>"
)

v6_html = v6_html.replace(
    "방 유지 + <code>joined_at</code> 최선임에게 자동 위임. 0명일 때만 삭제",
    "<strong>멤버 탈퇴 처리 (방 폭파 안 함)</strong> + <code>joined_at</code> 최선임에게 owner 자동 위임. 남은 인원 0명일 때만 방 삭제"
)

v6_html = v6_html.replace(
    "원본 <code>WardrobeItem</code> 불변. 관계 레코드만 생성/삭제",
    "<strong>단단 공유 해제 가능</strong> &middot; 원본 <code>WardrobeItem</code> 안전 보존 &middot; <code>SharedWardrobeItem</code> 관계 레코드만 생성/삭제"
)

# 상단 수직 레이아웃 간격 12px 대칭 추가
old_policy_end = "</tbody></table><h2 local-id=\"5309d7d46526\">3. API</h2>"
new_policy_end = """<tr ac:local-id="spacing_policy_tr"><td ac:local-id="spacing_policy_td1"><p local-id="spacing_policy_p1">상단 레이아웃</p></td><td ac:local-id="spacing_policy_td2"><p local-id="spacing_policy_p2">필터&rarr;방목록(12px) = 방목록&rarr;초대행(12px) <strong>1:1 대칭 수직 간격 튜닝</strong> &middot; 방 목록 <strong>가로 한 줄 스크롤(ScrollView horizontal)</strong> 적용</p></td></tr>""" + old_policy_end

if "상단 레이아웃" not in v6_html:
    v6_html = v6_html.replace(old_policy_end, new_policy_end)

# 상태 표 갱신
v6_html = v6_html.replace(
    "<code>feature/shared-wardrobe</code> (검증 기준 커밋 <code>4cc6e71</code>)",
    "<code>feature/shared-wardrobe-mybuild</code> (최신 커밋 <code>83202f3</code> &middot; EAS 프로덕션 배포 완료)"
)

# 5. Confluence PUT API 호출 (버전 11 -> 12)
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
        "message": "Update leave and item unshare policy based on backend code verification: single item unshare vs member leave room, owner auto delegation"
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
    print(f"Successfully verified code and updated Confluence page '{title}' to version {new_version}!")
else:
    print("PUT Error:", r_put.text)
