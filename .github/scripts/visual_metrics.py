#!/usr/bin/env python3
"""Local SVG trophies, isometric contribution calendar, and banner using GitHub API."""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
DEST = "images/metrics"
os.makedirs(DEST, exist_ok=True)

QUERY = """
query($login:String!,$from:DateTime!,$to:DateTime!) {
 user(login:$login) {
  repositories(first:1,ownerAffiliations:OWNER) { totalCount }
  contributionsCollection(from:$from,to:$to) {
   totalCommitContributions totalPullRequestContributions totalIssueContributions
   contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
  }
 }
}
"""
STARS_QUERY = """
query($login:String!,$cursor:String) {
 user(login:$login) {
  repositories(first:100,after:$cursor,ownerAffiliations:OWNER) {
   nodes { stargazerCount isFork }
   pageInfo { hasNextPage endCursor }
  }
 }
}
"""


def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql", data=payload, method="POST",
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "User-Agent": "wolwerr-metrics"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]


def label(x, y, value, size=16, color="#e6edf3", anchor="middle"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-size="{size}" fill="{color}">{escape(str(value))}</text>')


def svg(width, height, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="Segoe UI,Arial,sans-serif">'
            f'{defs}{body}</svg>')


def save(filename, content):
    output = os.path.join(DEST, filename)
    with open(output, "w", encoding="utf-8") as file:
        file.write(content + "\n")
    print("Generated", output)


def stars():
    count = 0
    cursor = None
    while True:
        repos = graphql(STARS_QUERY, {"login": USER, "cursor": cursor})["user"]["repositories"]
        count += sum(r["stargazerCount"] for r in repos["nodes"] if not r["isFork"])
        if not repos["pageInfo"]["hasNextPage"]:
            return count
        cursor = repos["pageInfo"]["endCursor"]


def make_trophies(collection, repositories):
    entries = [
        ("★", "Stars", stars()),
        ("◆", "Contributions", collection["contributionCalendar"]["totalContributions"]),
        ("⌘", "Commits", collection["totalCommitContributions"]),
        ("⑂", "Pull Requests", collection["totalPullRequestContributions"]),
        ("●", "Issues", collection["totalIssueContributions"]),
        ("▣", "Repositories", repositories),
    ]
    body = '<rect width="1080" height="184" rx="10" fill="#151a21"/>'
    body += label(18, 30, "GitHub Trophies", 21, "#7fff00", "start")
    for index, (glyph, caption, value) in enumerate(entries):
        x = 12 + 178 * index
        body += f'<rect x="{x}" y="43" width="164" height="128" rx="10" fill="#1b2430" stroke="#33404d"/>'
        body += label(x + 82, 73, glyph, 22, "#7fff00")
        body += label(x + 82, 116, f"{value:,}", 27, "#ffffff")
        body += label(x + 82, 148, caption, 13, "#c2cad4")
    save("github-trophies.svg", svg(1080, 184, body))


def polygon(points, color):
    coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{coords}" fill="{color}"/>'


def make_isometric(collection, today):
    records = {}
    for week in collection["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            records[day["date"]] = day["contributionCount"]
    start = today - timedelta(days=364)
    origin = start - timedelta(days=(start.weekday() + 1) % 7)
    body = '<rect width="1130" height="470" rx="10" fill="#151a21"/>'
    body += label(30, 46, "GitHub Contributions", 25, "#7fff00", "start")
    body += label(30, 72, "Last 365 days | Isometric contribution calendar", 13, "#a3afbd", "start")
    colors = ("#26312b", "#326b31", "#458f27", "#67c72c", "#9aff45")
    for index in range(365):
        day = start + timedelta(days=index)
        offset = (day - origin).days
        week, weekday = divmod(offset, 7)
        count = records.get(day.isoformat(), 0)
        level = 0 if count == 0 else min(4, 1 + int(count >= 3) + int(count >= 7) + int(count >= 12))
        x = 155 + (week - weekday) * 14.2
        y = 143 + (week + weekday) * 6.5
        rise = 2 + level * 5
        a = (x, y)
        b = (x + 13.2, y + 6)
        c = (x, y + 12)
        d = (x - 13.2, y + 6)
        body += polygon((d, c, (c[0], c[1] + rise), (d[0], d[1] + rise)),
                        "#28462e" if level else "#202a2d")
        body += polygon((c, b, (b[0], b[1] + rise), (c[0], c[1] + rise)),
                        "#37683a" if level else "#27343b")
        body += polygon((a, b, c, d), colors[level])
    body += label(30, 443, "Less", 12, "#a3afbd", "start")
    for i, color in enumerate(colors):
        body += f'<rect x="{75 + i * 19}" y="433" width="14" height="14" fill="{color}"/>'
    body += label(180, 443, "More", 12, "#a3afbd", "start")
    save("github-contributions-3d.svg", svg(1130, 470, body))


def make_banner():
    defs = ('<defs><linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="#183b24"/>'
            '<stop offset=".52" stop-color="#4e9e2a"/>'
            '<stop offset="1" stop-color="#7fff00"/></linearGradient></defs>')
    body = ('<path d="M0 50 C150 4 280 90 430 48 S720 10 840 45 S1040 75 1200 25 '
            'L1200 100 L0 100Z" fill="url(#wave)"/>')
    save("github-footer.svg", svg(1200, 100, body, defs))


def main():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    response = graphql(QUERY, {
        "login": USER,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    })
    user = response["user"]
    if user is None:
        raise RuntimeError("GitHub user not found")
    collection = user["contributionsCollection"]
    make_trophies(collection, user["repositories"]["totalCount"])
    make_isometric(collection, today)
    make_banner()


if __name__ == "__main__":
    main()
