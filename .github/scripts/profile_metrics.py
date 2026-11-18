#!/usr/bin/env python3
"""Gera cards SVG de contribuições e estatísticas usando somente a API GitHub.

Sem bibliotecas de terceiros. As métricas seguem as regras de contribuição do GitHub.
"""
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
YEAR = int(os.environ.get("METRICS_YEAR", str(date.today().year)))
TODAY = datetime.now(timezone.utc).date()

QUERY_USER = """
query($login: String!) {
  user(login: $login) { createdAt }
}
"""

QUERY_YEAR = """
query($login: String!, $start: DateTime!, $end: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $start, to: $end) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

QUERY_STARS = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
      nodes { stargazerCount isFork }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def graphql(query, variables):
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "wolwerr-profile-metrics",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
    if body.get("errors"):
        raise RuntimeError(f"GitHub GraphQL: {body['errors']}")
    return body["data"]


def get_year(year):
    start = f"{year}-01-01T00:00:00Z"
    end_date = min(date(year, 12, 31), TODAY)
    end = f"{end_date.isoformat()}T23:59:59Z"
    user = graphql(QUERY_YEAR, {"login": USER, "start": start, "end": end})["user"]
    if user is None:
        raise RuntimeError(f"Usuário GitHub não encontrado: {USER}")
    return user["contributionsCollection"]


def stars_count():
    count = 0
    cursor = None
    while True:
        result = graphql(QUERY_STARS, {"login": USER, "cursor": cursor})
        repos = result["user"]["repositories"]
        count += sum(r["stargazerCount"] for r in repos["nodes"] if not r["isFork"])
        page = repos["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]
    return count


def fmt_number(value):
    return f"{value:,}".replace(",", ".")


def fmt_date(value):
    return value.strftime("%d/%m/%Y")


def svg_text(x, y, value, size=11, fill="#ffffff", weight="normal", anchor="middle"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}">{escape(str(value))}</text>')


def save_svg(filename, inner):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="325" height="155" '
        'viewBox="0 0 325 155" font-family="Segoe UI,Arial,sans-serif">'
        '<rect width="325" height="155" rx="7" fill="#151a21"/>'
        f'{inner}</svg>\n'
    )
    with open(filename, "w", encoding="utf-8") as output:
        output.write(svg)
    print(f"Gerado {filename}")


def streaks(days):
    """Obtém streak atual e maior streak a partir de um calendário diário contínuo."""
    active = {d for d, count in days.items() if count > 0}
    longest = (0, None, None)
    count = 0
    start = None
    previous = None
    for day in sorted(active):
        if previous is not None and day - previous == timedelta(days=1):
            count += 1
        else:
            count, start = 1, day
        if count > longest[0]:
            longest = (count, start, day)
        previous = day

    last_day = TODAY if TODAY in active else TODAY - timedelta(days=1)
    current = 0
    current_start = None
    while last_day in active:
        current += 1
        current_start = last_day
        last_day -= timedelta(days=1)
    return (current, current_start, TODAY if current else None), longest


def render_streak(total, first, current, longest):
    current_count, current_start, current_end = current
    long_count, long_start, long_end = longest
    text = [
        '<line x1="108" y1="32" x2="108" y2="125" stroke="#8b949e"/>',
        '<line x1="216" y1="32" x2="216" y2="125" stroke="#8b949e"/>',
        '<circle cx="162" cy="62" r="27" fill="none" stroke="#7fff00" stroke-width="3"/>',
        svg_text(54, 63, fmt_number(total), 19, "#7fff00", "bold"),
        svg_text(54, 91, "Contribuições", 10, "#7fff00", "bold"),
        svg_text(162, 63, str(current_count), 19, "#00bfff", "bold"),
        svg_text(162, 112, "Sequência atual", 10, "#00bfff", "bold"),
        svg_text(271, 63, str(long_count), 19, "#7fff00", "bold"),
        svg_text(271, 91, "Maior sequência", 10, "#7fff00", "bold"),
        svg_text(54, 111, f"Desde {fmt_date(first)}", 9),
    ]
    if current_start:
        text.append(svg_text(162, 130, f"Desde {fmt_date(current_start)}", 9))
    else:
        text.append(svg_text(162, 130, "Sem sequência ativa", 9))
    if long_start:
        text.append(svg_text(271, 111, fmt_date(long_start), 9))
        text.append(svg_text(271, 125, f"até {fmt_date(long_end)}", 9))
    return "".join(text)


def render_stats(year, stars, commits, prs, issues, contributions):
    rows = [
        ("Estrelas recebidas", fmt_number(stars)),
        ("Commits no ano", fmt_number(commits)),
        ("PRs no ano", fmt_number(prs)),
        ("Issues no ano", fmt_number(issues)),
        ("Contribuições no ano", fmt_number(contributions)),
    ]
    parts = [svg_text(20, 29, f"Estatísticas de {year}", 17, "#7fff00", "bold", "start")]
    for index, (label, value) in enumerate(rows):
        y = 52 + index * 21
        parts.append(svg_text(21, y, label, 11, "#ffffff", "normal", "start"))
        parts.append(svg_text(247, y, value, 12, "#ffffff", "bold", "end"))
    parts.extend([
        '<circle cx="286" cy="96" r="26" fill="none" stroke="#32482a" stroke-width="4"/>',
        '<path d="M 286 70 A 26 26 0 0 1 310 86" fill="none" '
        'stroke="#7fff00" stroke-width="4" stroke-linecap="round"/>',
        svg_text(286, 101, str(year), 12, "#7fff00", "bold"),
    ])
    return "".join(parts)


def main():
    if YEAR > TODAY.year:
        raise ValueError("METRICS_YEAR não pode estar no futuro")
    user = graphql(QUERY_USER, {"login": USER})["user"]
    if user is None:
        raise RuntimeError(f"Usuário GitHub não encontrado: {USER}")
    created = date.fromisoformat(user["createdAt"][:10])
    first_year = created.year
    daily = {}
    total = 0
    selected = None

    for year in range(first_year, TODAY.year + 1):
        collection = get_year(year)
        calendar = collection["contributionCalendar"]
        total += calendar["totalContributions"]
        for week in calendar["weeks"]:
            for day in week["contributionDays"]:
                d = date.fromisoformat(day["date"])
                # Os intervalos são anuais, com proteção para dias de borda.
                if first_year <= d.year <= TODAY.year and d <= TODAY:
                    daily[d] = day["contributionCount"]
        if year == YEAR:
            selected = collection
        print(f"{year}: {calendar['totalContributions']} contribuições")

    if selected is None:
        selected = get_year(YEAR)

    current, longest = streaks(daily)
    save_svg(
        "github-metrics-streak.svg",
        render_streak(total, created, current, longest),
    )
    stars = stars_count()
    save_svg(
        "github-metrics-stats.svg",
        render_stats(
            YEAR,
            stars,
            selected["totalCommitContributions"],
            selected["totalPullRequestContributions"],
            selected["totalIssueContributions"],
            selected["contributionCalendar"]["totalContributions"],
        ),
    )


if __name__ == "__main__":
    main()
