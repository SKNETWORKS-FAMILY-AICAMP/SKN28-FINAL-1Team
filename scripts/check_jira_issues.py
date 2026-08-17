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

# 1. Jira JQL 로 공유 옷장 또는 전하영 관련 최근 이슈 조회
jql = "project = SCRUM AND (summary ~ '공유' OR summary ~ '옷장' OR text ~ 'Shared' OR assignee = '62512f9ff4079800705bf9f3') ORDER BY updated DESC"
search_url = f"{base}/rest/api/3/search/jql"

payload = {
    "jql": jql,
    "maxResults": 50,
    "fields": ["summary", "status", "assignee", "issuetype", "subtasks", "updated", "created"]
}

r = requests.post(search_url, auth=auth, headers=headers, json=payload)
print("Jira Search Status:", r.status_code)
if r.status_code == 200:
    issues = r.json().get("issues", [])
    print(f"Total Found Issues: {len(issues)}")
    for issue in issues:
        key = issue.get("key")
        summary = issue.get("fields", {}).get("summary")
        status = issue.get("fields", {}).get("status", {}).get("name")
        status_id = issue.get("fields", {}).get("status", {}).get("id")
        assignee = issue.get("fields", {}).get("assignee", {}).get("displayName") if issue.get("fields", {}).get("assignee") else "Unassigned"
        print(f"[{key}] {summary} | Status: {status} (ID: {status_id}) | Assignee: {assignee}")
else:
    print("Error:", r.text)
