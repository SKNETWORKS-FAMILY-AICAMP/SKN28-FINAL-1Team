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

# 이전 버전 목록 조회
url = f"{base}/wiki/rest/api/content/{page_id}/version"
r = requests.get(url, auth=auth, headers=headers)
print("Versions Status:", r.status_code)
if r.status_code == 200:
    results = r.json().get('results', [])
    for ver in results:
        print(f"Version {ver.get('number')}: {ver.get('by', {}).get('displayName')} | Message: {ver.get('message')}")
