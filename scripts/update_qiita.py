#!/usr/bin/env python3
"""Rewrite the Qiita sections of README.md between marker comments.

Markers:
  <!-- QIITA:START --> ... <!-- QIITA:END -->              latest articles (required)
  <!-- QIITA_STATS:START --> ... <!-- QIITA_STATS:END -->  totals (optional)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://qiita.com/api/v2"
PER_PAGE = 100
MAX_PAGES = 10

QIITA_USER = os.environ.get("QIITA_USER", "jqit-yukiono")
QIITA_TOKEN = os.environ.get("QIITA_TOKEN", "")
QIITA_TAG = os.environ.get("QIITA_TAG", "")
ARTICLE_COUNT = int(os.environ.get("QIITA_ARTICLE_COUNT", "5"))
README_PATH = os.environ.get("README_PATH", "README.md")


def fetch_items():
    # Only the authenticated endpoint returns page_views_count.
    if QIITA_TOKEN:
        base = f"{API}/authenticated_user/items"
    else:
        base = f"{API}/users/{QIITA_USER}/items"

    items = []
    for page in range(1, MAX_PAGES + 1):
        req = urllib.request.Request(
            f"{base}?page={page}&per_page={PER_PAGE}",
            headers={"User-Agent": "github-profile-readme"},
        )
        if QIITA_TOKEN:
            req.add_header("Authorization", f"Bearer {QIITA_TOKEN}")
        with urllib.request.urlopen(req, timeout=30) as res:
            batch = json.load(res)
        items.extend(batch)
        if len(batch) < PER_PAGE:
            break

    # The authenticated endpoint also returns limited-share articles; never publish them.
    return [i for i in items if not i.get("private")]


def escape_title(title):
    return re.sub(r"([\[\]])", r"\\\1", title)


def render_articles(items):
    if QIITA_TAG:
        items = [i for i in items if any(t["name"] == QIITA_TAG for t in i["tags"])]
    if not items:
        return "- (no articles yet)"
    lines = []
    for item in items[:ARTICLE_COUNT]:
        date = item["created_at"][:10]
        title = escape_title(item["title"])
        lines.append(f"- [{title}]({item['url']}) <sub>{date} · 👍 {item['likes_count']}</sub>")
    return "\n".join(lines)


def render_stats(items):
    likes = sum(i["likes_count"] for i in items)
    parts = [f"📝 **{len(items)}** articles", f"👍 **{likes:,}** likes"]
    views = [i.get("page_views_count") for i in items]
    if items and all(v is not None for v in views):
        parts.append(f"👀 **{sum(views):,}** views")
    return " · ".join(parts)


def replace_section(text, name, body, required):
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.DOTALL)
    if not pattern.search(text):
        if required:
            raise ValueError(f"marker <!-- {name}:START/END --> not found in {README_PATH}")
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text, count=1)


def main():
    try:
        items = fetch_items()
    except urllib.error.HTTPError as e:
        print(f"Qiita API error: {e.code} {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Qiita API unreachable: {e.reason}", file=sys.stderr)
        return 1

    items.sort(key=lambda i: i["created_at"], reverse=True)

    with open(README_PATH, encoding="utf-8") as f:
        original = f.read()
    try:
        updated = replace_section(original, "QIITA", render_articles(items), required=True)
        updated = replace_section(updated, "QIITA_STATS", render_stats(items), required=False)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    if updated == original:
        print("README is up to date")
        return 0
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"README updated ({len(items)} articles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
