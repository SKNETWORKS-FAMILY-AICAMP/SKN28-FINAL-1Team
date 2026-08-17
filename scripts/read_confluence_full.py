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
url = f"{base}/wiki/rest/api/content/{page_id}?expand=body.storage,version"

r = requests.get(url, auth=auth, headers=headers)
if r.status_code == 200:
    data = r.json()
    print("=== Page Title ===")
    print(data.get('title'))
    print("=== Version ===")
    print(data.get('version', {}).get('number'))
    print("=== Body Content ===")
    print(data.get('body', {}).get('storage', {}).get('value'))
else:
    print("Error:", r.status_code, r.text)
