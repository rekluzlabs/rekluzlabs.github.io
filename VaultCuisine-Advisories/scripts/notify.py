"""Idempotent GitHub issue notifications for review and API risks."""
import hashlib
import argparse
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "rekluzlabs/rekluzlabs.github.io"
BASE = f"https://api.github.com/repos/{REPO}/issues"


def api(method, url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def issue_plan(notices):
    planned = []
    for group in ("failures", "review"):
        if notices.get(group):
            planned.append((f"VaultCuisine advisory {group} require attention", "\n".join("- " + x for x in notices[group][:100])))
    for announcement in notices.get("api", [])[:50]:
        value = announcement["date"] + "\n" + announcement["summary"]
        digest = hashlib.sha256(value.encode()).hexdigest()[:12]
        body = (f"Announcement date: {announcement['date']}\n"
                f"Official source: {announcement.get('source', 'https://aistudio.google.com/docs/changelog')}\n"
                "Affected API: inspect announcement; VaultCuisine uses v1beta Model List and GenerateContent.\n"
                "Potential features: Gemini model refresh and seven generation profiles (including image input and JSON).\n"
                f"Deadline: {announcement.get('deadline', 'inspect announcement; no date inferred')}\n"
                "Action: investigate official migration notice and test the app; do not auto-migrate.\n\n"
                f"Excerpt: {announcement['summary']}\n")
        planned.append((f"VaultCuisine Gemini API notice [{digest}]", body))
        deadline = announcement.get("deadline")
        if deadline:
            from datetime import date
            days = (date.fromisoformat(deadline) - date.today()).days
            if 0 <= days <= 30:
                planned.append((f"VaultCuisine Gemini API deadline {deadline} [{digest}]", body))
    return planned


def notify(path, token):
    notices = json.loads(Path(path).read_text(encoding="utf-8")) if path else {"failures": ["Workflow failed before a report was produced; inspect the failed run and prior advisories."]}
    existing = []
    for page in range(1, 6):
        batch = api("GET", f"{BASE}?state=all&per_page=100&page={page}", token)
        existing += [x for x in batch if "pull_request" not in x]
        if len(batch) < 100:
            break
    by_title = {x["title"]: x for x in existing}
    failure_title = "VaultCuisine advisory failures require attention"
    if not notices.get("failures") and failure_title in by_title and by_title[failure_title]["state"] == "open":
        api("PATCH", by_title[failure_title]["url"], token, {"state": "closed", "body": "Recovered on a later successful documentation check."})
    for title, body in issue_plan(notices):
        if title == failure_title:
            old = by_title.get(title)
            previous = re.search(r"Occurrences in current failure streak: (\d+)", old.get("body") or "") if old and old["state"] == "open" else None
            count = int(previous.group(1)) + 1 if previous else 1
            body += f"\nOccurrences in current failure streak: {count}\n"
        if title in by_title:
            old = by_title[title]
            if old["state"] == "closed" and title == failure_title:
                api("PATCH", old["url"], token, {"state": "open", "body": body})
                continue
            if old["state"] == "open" and old["body"] != body and title.endswith("require attention"):
                api("PATCH", old["url"], token, {"body": body})
                if title == failure_title and count == 3:
                    api("POST", old["url"] + "/comments", token, {"body": "Three consecutive advisory workflow or extraction failures; investigate the official source and workflow logs."})
        else:
            api("POST", BASE, token, {"title": title, "body": body})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("notices", type=Path, nargs="?")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN required for issue notification")
    notify(args.notices, token)
