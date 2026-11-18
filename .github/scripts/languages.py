#!/usr/bin/env python3
"""Gera SVG com linguagens das contribuições recentes do GitHub.

Usa o mesmo critério do github-profile-3d-contrib: soma commits atribuídos
à linguagem principal de cada repositório no período de contribuições.
Apenas biblioteca padrão Python e API GraphQL oficial do GitHub.
"""
import json
import os
import urllib.request
from collections import Counter
from html import escape

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
OUTPUT = os.environ.get("OUTPUT", "github-metrics-languages.svg")
LIMIT = int(os.environ.get("LIMIT", "8"))
TITLE = os.environ.get("TITLE", "Linguagens mais usadas")
MAX_REPOS = int(os.environ.get("MAX_REPOS", "100"))

QUERY = """
query($login: String!, $maxRepos: Int!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      commitContributionsByRepository(maxRepositories: $maxRepos) {
        repository { nameWithOwner primaryLanguage { name color } }
        contributions { totalCount }
      }
    }
  }
}
"""

COLORS = {
    "Java": "#b07219", "Kotlin": "#A97BFF",
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Python": "#3572A5", "HTML": "#e34c26", "CSS": "#663399",
    "SCSS": "#c6538c", "PHP": "#4F5D95", "Shell": "#89e051",
    "C": "#555555", "C++": "#f34b7d", "C#": "#7851c9",
    "Go": "#00ADD8", "Rust": "#dea584", "Dart": "#00B4AB",
    "Swift": "#F05138", "Ruby": "#701516", "Vue": "#41b883",
    "Lua": "#000080", "PowerShell": "#012456",
}


def load_stats():
    data = json.dumps({
        "query": QUERY,
        "variables": {"login": USER, "maxRepos": MAX_REPOS},
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "wolwerr-profile-metrics",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL: {result['errors']}")
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"Usuário não encontrado: {USER}")

    collection = user["contributionsCollection"]
    stats = Counter()
    colors = dict(COLORS)
    for item in collection["commitContributionsByRepository"]:
        language = item["repository"]["primaryLanguage"]
        if not language:
            continue
        count = item["contributions"]["totalCount"]
        stats[language["name"]] += count
        if language.get("color"):
            colors[language["name"]] = language["color"]
        print(f"{item['repository']['nameWithOwner']}: {language['name']} ({count} commits)")
    return stats, colors, collection["totalCommitContributions"]


def render(stats, colors, total_commits):
    top = stats.most_common(LIMIT)
    total = sum(stats.values())
    if not total:
        raise RuntimeError("Nenhum commit com linguagem principal identificado no período.")

    # Limite da API: até 100 repositórios. Porcentagens representam os
    # repositórios retornados, sem fingir cobertura de commits não atribuídos.
    width, bar_x, bar_w = 325, 25, 275
    rows = (len(top) + 1) // 2
    height = max(155, 82 + rows * 22 + 8)

    segments = []
    x = bar_x
    for lang, count in stats.most_common():
        bar_part = bar_w * count / total
        segments.append(
            f'<rect x="{x:.2f}" y="48" width="{bar_part:.2f}" height="8" '
            f'fill="{escape(colors.get(lang, "#8b949e"))}"/>'
        )
        x += bar_part

    legend = []
    for i, (lang, count) in enumerate(top):
        lx = 25 + (i % 2) * 140
        ly = 82 + (i // 2) * 22
        color = escape(colors.get(lang, "#8b949e"))
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>'
            f'<text x="{lx + 16}" y="{ly}" font-size="11" fill="#ffffff">'
            f'{escape(lang)} {100 * count / total:.2f}%</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="'Segoe UI', Ubuntu, Sans-Serif">
<rect width="{width}" height="{height}" rx="4.5" fill="#151a21"/>
<text x="25" y="35" font-size="18" font-weight="600" fill="#7fff00">{escape(TITLE)}</text>
<clipPath id="bar"><rect x="{bar_x}" y="48" width="{bar_w}" height="8" rx="4"/></clipPath>
<rect x="{bar_x}" y="48" width="{bar_w}" height="8" rx="4" fill="#333"/>
<g clip-path="url(#bar)">{''.join(segments)}</g>
{''.join(legend)}
</svg>
"""


def main():
    if not 1 <= MAX_REPOS <= 100:
        raise ValueError("MAX_REPOS deve estar entre 1 e 100")
    if LIMIT < 1:
        raise ValueError("LIMIT deve ser positivo")
    stats, colors, total_commits = load_stats()
    print(f"Commits GitHub no período: {total_commits}")
    print(f"Commits atribuídos às linguagens: {sum(stats.values())}")
    with open(OUTPUT, "w", encoding="utf-8") as output:
        output.write(render(stats, colors, total_commits))
    print(f"Gerado {OUTPUT}: {dict(stats.most_common(LIMIT))}")


if __name__ == "__main__":
    main()
