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
headers = {"Accept": "application/json"}

page_id = "45744129"

# version 7의 내용을 조회
url = f"{base}/wiki/rest/api/content/{page_id}/version/7?expand=body.storage"
r = requests.get(url, auth=auth, headers=headers)
print("GET v7 Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    val = data.get('body', {}).get('storage', {}).get('value', '')
    with open(r"C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\scripts\v7_body.html", "w", encoding="utf-8") as out:
        out.write(val)
    print("v7 body saved to v7_body.html, length:", len(val))
else:
    print("Error:", r.text)
