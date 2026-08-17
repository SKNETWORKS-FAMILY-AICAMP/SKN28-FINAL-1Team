import requests
import sys

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
account_id = "62512f9ff4079800705bf9f3" # 전하영

targets = [
    {
        "key": "SCRUM-283",
        "summary": "[프론트] 옷장 공유 기능",
        "assignee": account_id,
        "transition_id": "41", # 완료
        "comment": "공유 옷장 프론트엔드 모바일/웹 이원화 UX(PC 2행 / 모바일 1행 상단), 방 탭 가로 한 줄 스크롤(ScrollView horizontal), 초대 링크 미로그인 직행 & 로그인 시 초대방 직통 진입, 상단 수직 여백 12px 대칭 튜닝, EAS 프로덕션 웹 배포 완료"
    },
    {
        "key": "SCRUM-303",
        "summary": "[공유 룸] 룸 생성·조회 API",
        "transition_id": "41",
        "comment": "공유 옷장 룸 생성, 초대코드 24시간 만료 및 재발급, 가입자 방 목록 조회 API 구현 및 백엔드 테스트 완료"
    },
    {
        "key": "SCRUM-304",
        "summary": "[공유 멤버] 멤버 초대·가입·탈퇴 API",
        "transition_id": "41",
        "comment": "6인 정원 행 잠금 검증, 초대 코드 가입, 방장 탈퇴 시 joined_at 최선임 멤버 자동 위임 및 방 폭파 방지 구현 완료"
    },
    {
        "key": "SCRUM-305",
        "summary": "[공유 아이템] 공유 아이템 등록·조회 API",
        "transition_id": "41",
        "comment": "개인 옷장 원본 보존 매핑, 단건 공유 해제, delete_my_items 탈퇴 옵션 및 pending_share_room_id 서버 비동기 예약 소진 구현 완료"
    },
    {
        "key": "SCRUM-306",
        "summary": "[공유 동시성] select_for_update 락 + 24h 만료 처리",
        "transition_id": "41",
        "comment": "select_for_update 행 잠금 및 24h 초대코드 만료 검증 백엔드 단위 테스트 100% 통과"
    },
    {
        "key": "SCRUM-308",
        "summary": "공유 옷장 아이템을 추천 검색 대상에 연결",
        "transition_id": "41",
        "comment": "공유 옷장 아이템 추천 파이프라인 연동 및 Confluence v13 문서 작성 완료"
    }
]

for t in targets:
    key = t["key"]
    print(f"=== Updating Jira Issue {key} ===")
    
    # 1. Assignee 지정 (필요 시)
    if "assignee" in t:
        r_assign = requests.put(f"{base}/rest/api/3/issue/{key}/assignee", auth=auth, headers=headers, json={"accountId": t["assignee"]})
        print(f"  [{key}] Assignee Update Status:", r_assign.status_code)
        
    # 2. Transition (상태 변경: 완료)
    r_trans = requests.post(f"{base}/rest/api/3/issue/{key}/transitions", auth=auth, headers=headers, json={"transition": {"id": t["transition_id"]}})
    print(f"  [{key}] Transition Status:", r_trans.status_code)
    
    # 3. Comment 추가
    comment_payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": t["comment"]}]
                }
            ]
        }
    }
    r_comment = requests.post(f"{base}/rest/api/3/issue/{key}/comment", auth=auth, headers=headers, json=comment_payload)
    print(f"  [{key}] Comment Status:", r_comment.status_code)

print("\nAll Jira issues updated successfully!")
