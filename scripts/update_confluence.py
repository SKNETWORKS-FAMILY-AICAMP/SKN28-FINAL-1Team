import requests
import sys
import json
import markdown

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

# 1. 페이지 현재 정보 조회 (제목, 버전 번호)
get_url = f"{base}/wiki/rest/api/content/{page_id}?expand=version"
r_get = requests.get(get_url, auth=auth, headers=headers)
if r_get.status_code != 200:
    print("GET error:", r_get.text)
    sys.exit(1)

current_data = r_get.json()
current_version = current_data['version']['number']
new_version = current_version + 1
title = current_data['title']

# 2. SHARED_WARDROBE_SPECIFICATION.md 읽기
spec_path = r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\shared-wardrobe\SHARED_WARDROBE_SPECIFICATION.md"
with open(spec_path, "r", encoding="utf-8") as f:
    md_content = f.read()

# 마크다운 -> HTML 변환 (tables, fenced_code 지원)
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

# 3. Confluence PUT API 호출
put_url = f"{base}/wiki/rest/api/content/{page_id}"
payload = {
    "id": page_id,
    "type": "page",
    "title": title,
    "version": {
        "number": new_version,
        "message": "Update Shared Wardrobe specification: direct invite auth flow, responsive PC/mobile UI, equal spacing"
    },
    "body": {
        "storage": {
            "value": html_content,
            "representation": "storage"
        }
    }
}

r_put = requests.put(put_url, auth=auth, headers=headers, json=payload)
print("PUT Status Code:", r_put.status_code)
if r_put.status_code == 200:
    print(f"Successfully updated Confluence page '{title}' (ID: {page_id}) to version {new_version}!")
else:
    print("PUT Error:", r_put.text)
