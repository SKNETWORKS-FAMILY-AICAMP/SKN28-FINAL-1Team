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
headers = {"Accept": "application/json"}

r = requests.get(f"{base}/rest/api/3/issue/SCRUM-283/transitions", auth=auth, headers=headers)
print("SCRUM-283 Transitions Status:", r.status_code)
if r.status_code == 200:
    for t in r.json().get("transitions", []):
        print(f"ID: {t.get('id')} | Name: {t.get('name')}")
