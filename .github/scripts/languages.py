#!/usr/bin/env python3
"""Gera um SVG com as linguagens mais escritas pelo autor.

Clona os repositórios, filtra os commits do autor (git log --author) e soma as
linhas adicionadas por linguagem, ignorando dependências e arquivos gerados.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter
from html import escape

USER = os.environ["GH_USER"]
TOKEN = os.environ["GH_TOKEN"]
AUTHORS = [a.strip() for a in os.environ.get("AUTHORS", USER).split(",") if a.strip()]
OUTPUT = os.environ.get("OUTPUT", "images/metrics/github-metrics-languages.svg")
LIMIT = int(os.environ.get("LIMIT", "8"))
TITLE = os.environ.get("TITLE", "Most Used Languages")
AFFILIATION = os.environ.get("AFFILIATION", "owner")
INCLUDE_FORKS = os.environ.get("INCLUDE_FORKS", "0") == "1"

EXT = {
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".py": "Python",
    ".php": "PHP", ".sql": "SQL", ".sh": "Shell", ".bash": "Shell",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".cs": "C#", ".go": "Go", ".rs": "Rust", ".dart": "Dart", ".swift": "Swift",
    ".rb": "Ruby", ".vue": "Vue", ".svelte": "Svelte", ".lua": "Lua",
    ".scala": "Scala", ".groovy": "Groovy", ".gradle": "Groovy", ".ps1": "PowerShell",
}

COLORS = {
    "Java": "#b07219", "Kotlin": "#A97BFF", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Python": "#3572A5", "PHP": "#4F5D95", "SQL": "#e38c00", "Shell": "#89e051",
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Go": "#00ADD8", "Rust": "#dea584",
    "Dart": "#00B4AB", "Swift": "#F05138", "Ruby": "#701516", "Vue": "#41b883",
    "Svelte": "#ff3e00", "Lua": "#000080", "Scala": "#c22d40", "Groovy": "#4298b8",
    "PowerShell": "#012456", "Dockerfile": "#384d54",
}

SKIP_DIRS = {
    "node_modules", "vendor", "dist", "build", "target", "bower_components",
    ".next", "out", "coverage", "__pycache__", "venv", ".venv", "Pods", ".gradle",
}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
SKIP_SUFFIXES = (".min.js", ".min.css", ".lock", ".map")


def api(url):
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def list_repos():
    repos, page = [], 1
    while True:
        data = api(
            f"https://api.github.com/user/repos?affiliation={AFFILIATION}&per_page=100&page={page}"
        )
        if not data:
            break
        repos += data
        page += 1
    return [r for r in repos if INCLUDE_FORKS or not r["fork"]]


def language_of(path):
    parts = path.split("/")
    name = parts[-1]
    lower = name.lower()
    if any(p in SKIP_DIRS for p in parts[:-1]) or lower in SKIP_NAMES or lower.endswith(SKIP_SUFFIXES):
        return None
    if name == "Dockerfile":
        return "Dockerfile"
    return EXT.get(os.path.splitext(lower)[1])


def count_repo(path):
    cmd = [
        "git", "-c", "core.quotepath=off", "-C", path,
        "log", "--all", "--no-merges", "--no-renames",
        "--regexp-ignore-case", "--numstat", "--format=",
    ]
    for author in AUTHORS:
        cmd.extend(["--author", author])

    result = subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", check=True,
    )
    stats = Counter()
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        lang = language_of(parts[2])
        if lang:
            stats[lang] += int(parts[0])
    return stats


def top_authors(path, n=3):
    out = subprocess.run(
        ["git", "-C", path, "log", "--all", "--format=%an <%ae>"],
        capture_output=True, text=True, errors="replace",
    ).stdout
    found = Counter(out.splitlines()).most_common(n)
    return [f"{name} ({count} commits)" for name, count in found] or ["sem commits"]


def render(stats):
    total = sum(stats.values())
    top = stats.most_common(LIMIT)
    width, bar_x, bar_w = 325, 25, 275
    rows = math.ceil(len(top) / 2)
    height = max(155, 82 + rows * 22 - 8)

    segments, x = [], bar_x
    for lang, n in top:
        w = bar_w * n / total
        segments.append(f'<rect x="{x:.2f}" y="48" width="{w:.2f}" height="8" fill="{COLORS.get(lang, "#8b949e")}"/>')
        x += w

    legend = []
    for i, (lang, n) in enumerate(top):
        lx = 25 + (i % 2) * 140
        ly = 82 + (i // 2) * 22
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{COLORS.get(lang, "#8b949e")}"/>'
            f'<text x="{lx + 16}" y="{ly}" font-size="11" fill="#ffffff">{escape(lang)} {100 * n / total:.2f}%</text>'
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
    repos = list_repos()
    print(f"{len(repos)} repositórios encontrados; autores: {AUTHORS}")
    total = Counter()
    with tempfile.TemporaryDirectory() as tmp:
        for repo in repos:
            dest = os.path.join(tmp, repo["name"] + ".git")
            url = f"https://x-access-token:{TOKEN}@github.com/{repo['full_name']}.git"
            res = subprocess.run(["git", "clone", "--bare", "--quiet", url, dest], capture_output=True)
            if res.returncode != 0:
                print(f"  ! falha ao clonar {repo['full_name']}")
                continue
            stats = count_repo(dest)
            print(f"  {repo['full_name']}: {sum(stats.values())} linhas")
            if not stats:
                print("      autores no repositório: " + "; ".join(top_authors(dest)))
            total += stats
    print("Ranking completo de linguagens:", dict(total.most_common()))
    print(f"C# contabilizado: {total.get('C#', 0)} linhas adicionadas")
    if not total:
        sys.exit("Nenhuma linha encontrada para esses autores. Confira a variável AUTHORS.")
    os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(render(total))
    print(f"Gerado {OUTPUT}: {dict(total.most_common(LIMIT))}")


if __name__ == "__main__":
    main()
