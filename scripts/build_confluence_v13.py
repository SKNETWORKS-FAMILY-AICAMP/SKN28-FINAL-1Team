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

# 가독성 높은 Confluence Storage Format HTML 구성 (v13)
confluence_html = """<ac:structured-macro ac:name="panel" ac:schema-version="1" ac:local-id="8128c78ea513" ac:macro-id="318b013d-d802-4cbf-bd93-d21efd93dd08">
  <ac:parameter ac:name="panelIcon">:rainbow:</ac:parameter>
  <ac:parameter ac:name="panelIconId">1f308</ac:parameter>
  <ac:parameter ac:name="panelIconText">🌈</ac:parameter>
  <ac:parameter ac:name="bgColor">#E6FCFF</ac:parameter>
  <ac:rich-text-body>
    <p><strong>공유 옷장(Shared Wardrobe) 요약</strong></p>
    <p>최대 6명이 각자의 개인 옷장에서 옷을 골라 한 방에 모아 보는 기능.<br />
    옷을 <strong>복사하지 않고 관계만 연결/삭제</strong>하는 것이 설계의 핵심이다.</p>
  </ac:rich-text-body>
</ac:structured-macro>

<table data-table-width="760" data-layout="default">
  <colgroup><col style="width: 113.0px;" /><col style="width: 646.0px;" /></colgroup>
  <tbody>
    <tr><th><p>상태</p></th><td><p>백엔드·프론트엔드 구현 완료 · EAS 프로덕션 웹 배포 완료 · 12px 간격 대칭 &amp; 초대 직통 UX 완성</p></td></tr>
    <tr><th><p>브랜치</p></th><td><p><code>feature/shared-wardrobe-mybuild</code> (최신 커밋 <code>83202f3</code>)</p></td></tr>
    <tr><th><p>담당</p></th><td><p>전하영 · Jira SCRUM-282 / SCRUM-283</p></td></tr>
    <tr><th><p>라이브 배포</p></th><td><p><a href="https://skncozyhy.expo.app">https://skncozyhy.expo.app</a> (EAS Production Web)</p></td></tr>
  </tbody>
</table>

<h2>1. 구조 &amp; 핵심 모델</h2>
<p><strong>데이터 모델 관계도</strong> — 개인 옷장 원본은 불변으로 두고, 방과의 관계만 연결하고 지운다.</p>

<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="breakoutMode">wide</ac:parameter>
  <ac:parameter ac:name="breakoutWidth">760</ac:parameter>
  <ac:plain-text-body><![CDATA[   User
    │
    ├──< SharedWardrobeMember >──── SharedWardrobeRoom
    │       role  : owner / member       invite_code : 6자리, 24h 만료
    │       joined_at ★                  정원        : 최대 6명
    │                                         │
    │                                         │
    └──< WardrobeItem >──< SharedWardrobeItem >
              ▲                    status : available / borrowed / private
              │                    registered_by : 공유한 사람 (SET_NULL)
        개인 옷장 원본
        (공유해도 복사 안 함 · 공유 해제 = 관계 레코드만 DELETE)

  ★ joined_at 이 두 가지의 핵심 기준이 된다
      · 아바타 고정 색상 순서 (0=노랑 1=하늘 2=연두 3=핑크 4=보라 5=주황)
      · 방장 탈퇴 시 위임 순서 (가장 일찍 가입한 멤버에게 자동 승계)]]></ac:plain-text-body>
</ac:structured-macro>

<p><strong>초대 &rarr; 참여 직통 흐름 (Auth Direct Flow)</strong></p>
<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="breakoutMode">wide</ac:parameter>
  <ac:parameter ac:name="breakoutWidth">760</ac:parameter>
  <ac:plain-text-body><![CDATA[  방장                                              받는 사람 (초대 링크 클릭)
   │                                                    │
   │ 방 개설 (개설자가 자동 owner)                      │
   │   └─ 초대코드 6자리 동시 발급 (24시간)             │
   │                                                    │
   ├── 초대 링크 {origin}/invite?code=XXXXXX ──────────▶ │
   │     (카톡 공유 / 링크 복사)                        │
   │                                                    ├─ 로그인 O ─▶ 수동 버튼 누름 없이 자동 joinSharedRoom 수락
   │                                                    │              · 정원 6명 검사 (행 잠금)
   │                                                    │              · 이미 멤버면 즉시 입장
   │                                                    │              · 해당 방 (closet?tab=shared&room=roomId) 직통 진입
   │                                                    │
   │                                                    └─ 로그인 X ─▶ /login?redirect=... 로그인 페이지 즉시 직행
   │                                                                   · 로그인 완료 시 원래 초대 링크로 자동 복귀
   │                                                                   · 복귀 후 자동 수락 및 초대방 직통 입장
   ├── 코드 재발급 (owner만) ─ 기존 코드 즉시 무효화]]></ac:plain-text-body>
</ac:structured-macro>

<p><strong>공유 해제 &amp; 방 삭제(탈퇴) 처리</strong> — 옷은 단건 공유 해제 가능하며, 방 삭제 시 방을 폭파하지 않고 멤버만 탈퇴하는 것이 핵심이다.</p>
<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="breakoutMode">wide</ac:parameter>
  <ac:parameter ac:name="breakoutWidth">760</ac:parameter>
  <ac:plain-text-body><![CDATA[  공유 옷장 아이템 공유 해제 및 방 삭제(탈퇴) 요청
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
                                                       (남은 멤버가 0명일 때만 방 자동 삭제)]]></ac:plain-text-body>
</ac:structured-macro>

<h2>2. 핵심 정책 요약</h2>
<table data-table-width="760" data-layout="default">
  <colgroup><col style="width: 130.0px;" /><col style="width: 630.0px;" /></colgroup>
  <tbody>
    <tr><th><p>항목</p></th><th><p>핵심 규칙</p></th></tr>
    <tr><td><p>정원 제약</p></td><td><p>최대 <strong>6명</strong>. 가입 시 PostgreSQL 행 잠금(<code>select_for_update</code>)으로 동시성 우회 차단</p></td></tr>
    <tr><td><p>초대 링크 직통 UX</p></td><td><p><strong>미로그인</strong>: <code>/login?redirect=...</code> 즉시 직행<br /><strong>로그인</strong>: 버튼 대기 없이 자동 수락 ➔ 해당 초대방(<code>room=roomId</code>) 직통 진입</p></td></tr>
    <tr><td><p>비동기 서버 예약</p></td><td><p>AI 처리 대기 시 DB 컬럼(<code>pending_share_room_id</code>)에 예약 ➔ 확정 시 서버에서 원자적 소진</p></td></tr>
    <tr><td><p>반응형 UI (웹vs모바일)</p></td><td><p><strong>PC웹</strong>: 1행 토글 + 2행 드롭다운 선택<br /><strong>모바일</strong>: 사진 영역 상단 1행 일체형 토글 박스 (사진&rarr;제목 상단)</p></td></tr>
    <tr><td><p>상단 레이아웃 간격</p></td><td><p>필터&rarr;방목록(12px) = 방목록&rarr;초대행(12px) <strong>1:1 대칭 수직 간격 튜닝</strong> · 방 목록 <strong>가로 한 줄 스크롤(ScrollView horizontal)</strong></p></td></tr>
    <tr><td><p>방장 탈퇴 &amp; 기부</p></td><td><p><strong>방 폭파 안 함</strong> · <code>joined_at</code> 최선임 멤버에게 owner 위임 · 남은 인원 0명일 때만 방 삭제 · <code>delete_my_items=false</code> 시 기부(registered_by=NULL)</p></td></tr>
    <tr><td><p>소유자 뱃지 정돈</p></td><td><p>소유자 표시 문구를 <code>'나님'</code> ➔ <code>'나'</code>(사용자 이름 그대로)로 깔끔하게 노출</p></td></tr>
  </tbody>
</table>

<h2>3. API 엔드포인트 요약</h2>
<p>모든 엔드포인트는 <code>/api/v1/shared-wardrobes/</code> 아래에 위치합니다.</p>
<table data-table-width="760" data-layout="default">
  <colgroup><col style="width: 120.0px;" /><col style="width: 640.0px;" /></colgroup>
  <tbody>
    <tr><th><p>구분</p></th><th><p>엔드포인트 및 기능</p></th></tr>
    <tr><td><p>방 관리</p></td><td><p><code>GET /</code> 목록조회 · <code>POST /</code> 개설 · <code>PATCH /{id}</code> 이름수정 · <code>DELETE /{id}</code> 방 삭제(방장)</p></td></tr>
    <tr><td><p>초대 &amp; 탈퇴</p></td><td><p><code>POST /{id}/refresh-code/</code> 코드재발급(owner) · <code>POST join/</code> 참여 · <code>DELETE /{id}/leave/</code> 멤버 탈퇴</p></td></tr>
    <tr><td><p>아이템 공유</p></td><td><p><code>GET /{id}/items/</code> 목록 · <code>POST /{id}/items/</code> 공유 등록 · <code>DELETE /{id}/items/{item_id}/</code> 단건 공유 해제</p></td></tr>
  </tbody>
</table>

<ac:structured-macro ac:name="panel">
  <ac:parameter ac:name="panelType">note</ac:parameter>
  <ac:rich-text-body>
    <p><strong>프론트엔드 API 경로 안내</strong>: 모든 요청에 <code>/api/v1</code> 접두사가 올바르게 포함되어야 404 에러를 방지할 수 있습니다.</p>
  </ac:rich-text-body>
</ac:structured-macro>
"""

# Confluence PUT API 호출 (v12 -> v13)
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
        "message": "Final clear & concise Confluence specification update with high legibility, ASCII diagrams, and key points"
    },
    "body": {
        "storage": {
            "value": confluence_html,
            "representation": "storage"
        }
    }
}

r_put = requests.put(f"{base}/wiki/rest/api/content/{page_id}", auth=auth, headers=headers, json=payload)
print("PUT Status Code:", r_put.status_code)
if r_put.status_code == 200:
    print(f"Successfully updated Confluence page '{title}' to version {new_version} with maximum readability!")
else:
    print("PUT Error:", r_put.text)
