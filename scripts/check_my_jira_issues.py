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
my_account_id = "62512f9ff4079800705bf9f3"

jql = f"project = SCRUM AND assignee = '{my_account_id}' ORDER BY updated DESC"
search_url = f"{base}/rest/api/3/search/jql"

payload = {
    "jql": jql,
    "maxResults": 50,
    "fields": ["summary", "status", "issuetype", "updated", "created"]
}

r = requests.post(search_url, auth=auth, headers=headers, json=payload)
if r.status_code == 200:
    issues = r.json().get("issues", [])
    print(f"=== 전하영 본인 Jira 이슈 총 {len(issues)}건 ===")
    for issue in issues:
        key = issue.get("key")
        summary = issue.get("fields", {}).get("summary")
        status = issue.get("fields", {}).get("status", {}).get("name")
        print(f"[{key}] {summary} | Status: {status}")
