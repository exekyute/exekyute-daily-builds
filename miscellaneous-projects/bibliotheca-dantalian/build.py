#!/usr/bin/env python3
"""Bibliotheca Dantalian: a zero-dependency static wiki engine.

Builds a wiki from a directory containing wiki.json and content/*.md:

    python build.py [wiki_dir] [--out DIR]

wiki_dir defaults to example/ (the bundled example wiki). --out defaults
to docs/, which GitHub Pages can serve directly from the main branch.
Standard library only, no pip installs.

Authoring format (content/*.md):

    ---
    title: Page Title
    type: series | character | world | episode | meta | home
    summary: One line used for search results and link previews.
    categories: Comma, Separated, Categories
    infobox:
      Label: Value (wikilinks allowed)
    sources:
      - Label | https://example.com
    ---
    Markdown body. Supports ## / ### / #### headings, paragraphs,
    **bold**, *italic*, `code`, fenced code blocks, [label](https://url),
    [[Wikilinks]], [[Target|custom label]], - lists, 1. lists, > quotes,
    | tables |, --- rules, and spoiler blocks scoped to the ids declared
    in wiki.json:

    ::: spoiler manga
    Hidden until the reader opts in to that spoiler scope.
    :::

Page types and their nav grouping, spoiler scopes, site name, footer,
and edit-link base are all declared in the wiki's wiki.json, so the
engine itself contains nothing about any particular series.
"""

import argparse
import json
import re
import html
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"

# Populated from wiki.json in build(); defaults keep the renderer importable
# (and unit-testable) without a config.
CONFIG = {}
SPOILER_LABELS = {"anime": "Anime spoilers", "manga": "Manga spoilers"}

DEFAULT_TYPE_LABELS = {
    "home": "Home",
    "series": "Series",
    "character": "Character",
    "world": "World",
    "episode": "Episode",
    "meta": "Meta",
}
DEFAULT_NAV = [
    {"group": "Series", "types": ["series"]},
    {"group": "Characters", "types": ["character"]},
    {"group": "World", "types": ["world"]},
    {"group": "Episodes", "types": ["episode"]},
    {"group": "Meta", "types": ["meta"]},
]


def load_config(wiki_dir):
    cfg_path = wiki_dir / "wiki.json"
    if not cfg_path.is_file():
        sys.exit(f"No wiki.json found in {wiki_dir}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    for key in ("name", "tagline"):
        if not cfg.get(key):
            sys.exit(f"wiki.json: missing required field '{key}'")
    cfg.setdefault("repo_url", "")
    cfg.setdefault("edit_base", "")
    cfg.setdefault("footer", [])
    cfg.setdefault("spoiler_scopes", [])
    cfg.setdefault("type_labels", DEFAULT_TYPE_LABELS)
    cfg.setdefault("nav", DEFAULT_NAV)
    for scope in cfg["spoiler_scopes"]:
        if not re.fullmatch(r"[a-z][a-z0-9]*", scope.get("id", "")):
            sys.exit(f"wiki.json: spoiler scope id '{scope.get('id')}' must be lowercase letters and digits")
        scope.setdefault("label", scope["id"].title() + " spoilers")
        scope.setdefault("menu_label", "Show " + scope["label"].lower())
    if "home" not in cfg["type_labels"]:
        sys.exit("wiki.json: type_labels must include 'home'")
    return cfg


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[’']", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------- parsing

FRONT_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)


def parse_page(path, valid_types):
    raw = path.read_text(encoding="utf-8")
    m = FRONT_RE.match(raw)
    if not m:
        raise ValueError(f"{path.name}: missing front matter block")
    head, body = m.groups()

    page = {
        "file": path.name,
        "slug": slugify(path.stem),
        "title": path.stem,
        "type": "meta",
        "summary": "",
        "categories": [],
        "infobox": [],
        "sources": [],
        "body": body,
        "headings": [],
        "links": set(),
    }

    current_list = None
    for line in head.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and current_list:
            item = line.strip()
            if item.startswith("- "):
                item = item[2:]
            if current_list == "sources":
                label, _, url = item.partition("|")
                page["sources"].append((label.strip(), url.strip()))
            else:
                k, _, v = item.partition(":")
                page["infobox"].append((k.strip(), v.strip()))
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in ("infobox", "sources") and not value:
            current_list = key
            continue
        current_list = None
        if key == "categories":
            page["categories"] = [c.strip() for c in value.split(",") if c.strip()]
        elif key == "nav_order":
            page["nav_order"] = int(value)
        elif key in ("title", "type", "summary", "slug"):
            page[key] = value
    if page["type"] not in valid_types:
        raise ValueError(f"{path.name}: unknown type '{page['type']}' (declare it in wiki.json type_labels)")
    return page


# ---------------------------------------------------------------- inline markdown

CODE_RE = re.compile(r"`([^`]+)`")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
# URL may contain balanced (...) groups (common in Wikipedia links); quotes and
# angle brackets are excluded so the URL is safe inside an HTML attribute.
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s()\"'<>]+(?:\([^\s()\"'<>]*\)[^\s()\"'<>]*)*)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITAL_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def render_inline(text, ctx):
    text = html.escape(text, quote=False)
    codes = []

    def stash_code(m):
        codes.append(m.group(1))
        return f"\x00C{len(codes) - 1}\x00"

    text = CODE_RE.sub(stash_code, text)

    def wikilink(m):
        target = m.group(1).strip()
        label = (m.group(2) or target).strip()
        slug = ctx["resolve"].get(slugify(target))
        if slug:
            ctx["links"].add(slug)
            return f'<a class="wl" href="{slug}.html">{label}</a>'
        ctx["redlinks"].add(target)
        return (
            f'<a class="wl redlink" href="contribute.html" '
            f'title="This page has not been written yet">{label}</a>'
        )

    text = WIKILINK_RE.sub(wikilink, text)

    def ext_link(m):
        url = html.escape(m.group(2), quote=True)
        return f'<a href="{url}" rel="noopener">{m.group(1)}</a>'

    text = LINK_RE.sub(ext_link, text)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITAL_RE.sub(r"<em>\1</em>", text)
    for i, c in enumerate(codes):
        text = text.replace(f"\x00C{i}\x00", f"<code>{c}</code>")
    return text


# ---------------------------------------------------------------- block markdown

TABLE_SEP_RE = re.compile(r"^\|?[\s:\-|]+\|?$")
OL_RE = re.compile(r"^\d+\.\s+")


def split_table_row(line, ctx):
    """Split a table row on pipes, protecting pipes inside wikilinks and code spans."""
    protected = []

    def stash(m):
        protected.append(m.group(0))
        return f"\x00T{len(protected) - 1}\x00"

    line = WIKILINK_RE.sub(stash, line.strip().strip("|"))
    line = CODE_RE.sub(stash, line)
    cells = line.split("|")
    out = []
    for cell in cells:
        for i, p in enumerate(protected):
            cell = cell.replace(f"\x00T{i}\x00", p)
        out.append(render_inline(cell.strip(), ctx))
    return out


def render_blocks(lines, ctx):
    out = []
    para = []
    i = 0

    def flush():
        if para:
            out.append(f"<p>{render_inline(' '.join(para), ctx)}</p>")
            para.clear()

    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped:
            flush()
            i += 1
            continue

        if stripped.startswith("#### ") or stripped.startswith("### ") or stripped.startswith("## "):
            flush()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped.lstrip("#").strip()
            hid = slugify(text)
            if level <= 3:
                ctx["headings"].append((level, text, hid))
            out.append(f'<h{level} id="{hid}">{render_inline(text, ctx)}</h{level}>')
            i += 1
            continue

        if stripped.startswith("```"):
            flush()
            j = i + 1
            code = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                code.append(lines[j])
                j += 1
            escaped = html.escape("\n".join(code))
            out.append(f"<pre><code>{escaped}</code></pre>")
            i = j + 1
            continue

        if stripped.startswith("::: spoiler"):
            flush()
            parts = stripped.split(None, 3)
            scope = parts[2] if len(parts) > 2 else ""
            if scope not in SPOILER_LABELS:
                fallback = next(iter(SPOILER_LABELS), "")
                print(f"  warning: unknown spoiler scope '{scope}', using '{fallback}'")
                scope = fallback
            label = parts[3] if len(parts) > 3 else SPOILER_LABELS.get(scope, "Spoilers")
            j = i + 1
            inner = []
            depth = 1
            while j < len(lines):
                s = lines[j].strip()
                if s.startswith("::: spoiler"):
                    depth += 1
                elif s == ":::":
                    depth -= 1
                    if depth == 0:
                        break
                inner.append(lines[j])
                j += 1
            body = render_blocks(inner, ctx)
            out.append(
                f'<div class="spoiler" data-scope="{scope}">'
                f'<div class="spoiler-head"><span class="spoiler-tag">{html.escape(label)}</span>'
                f'<button class="spoiler-btn" type="button">Show</button></div>'
                f'<div class="spoiler-body">{body}</div></div>'
            )
            i = j + 1
            continue

        if stripped.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            header = split_table_row(rows[0], ctx)
            body_rows = rows[1:]
            if body_rows and TABLE_SEP_RE.match(body_rows[0]) and "-" in body_rows[0]:
                body_rows = body_rows[1:]
            t = ['<div class="table-wrap"><table><thead><tr>']
            t += [f"<th>{c}</th>" for c in header]
            t.append("</tr></thead><tbody>")
            for r in body_rows:
                t.append("<tr>" + "".join(f"<td>{c}</td>" for c in split_table_row(r, ctx)) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue

        if stripped.startswith("- "):
            flush()
            items = []
            while i < len(lines):
                s = lines[i].strip()
                raw = lines[i]
                if not s.startswith("- "):
                    break
                if raw.startswith("  ") and items:
                    items[-1][1].append(s[2:])
                else:
                    items.append([s[2:], []])
                i += 1
            t = ["<ul>"]
            for text, subs in items:
                li = f"<li>{render_inline(text, ctx)}"
                if subs:
                    li += "<ul>" + "".join(f"<li>{render_inline(s, ctx)}</li>" for s in subs) + "</ul>"
                t.append(li + "</li>")
            t.append("</ul>")
            out.append("".join(t))
            continue

        if OL_RE.match(stripped):
            flush()
            items = []
            while i < len(lines) and OL_RE.match(lines[i].strip()):
                items.append(OL_RE.sub("", lines[i].strip()))
                i += 1
            out.append("<ol>" + "".join(f"<li>{render_inline(s, ctx)}</li>" for s in items) + "</ol>")
            continue

        if stripped.startswith("> "):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote.append(lines[i].strip()[2:])
                i += 1
            out.append(f"<blockquote><p>{render_inline(' '.join(quote), ctx)}</p></blockquote>")
            continue

        if stripped in ("---", "***"):
            flush()
            out.append("<hr>")
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush()
    return "".join(out)


# ---------------------------------------------------------------- page shell

def nav_html(pages, current_slug):
    groups = []
    for entry in CONFIG["nav"]:
        types = tuple(entry["types"])
        members = sorted(
            (p for p in pages if p["type"] in types),
            key=lambda p: (p.get("nav_order", 0), p["title"]),
        )
        if not members:
            continue
        items = []
        for p in members:
            cls = ' class="current"' if p["slug"] == current_slug else ""
            items.append(f'<li{cls}><a href="{p["slug"]}.html">{html.escape(p["title"])}</a></li>')
        groups.append(
            f'<section class="nav-group"><h2>{html.escape(entry["group"])}</h2><ul>{"".join(items)}</ul></section>'
        )
    return "".join(groups)


def infobox_html(page, ctx):
    if not page["infobox"]:
        return ""
    rows = "".join(
        f"<div class='ib-row'><dt>{html.escape(k)}</dt><dd>{render_inline(v, ctx)}</dd></div>"
        for k, v in page["infobox"]
    )
    return (
        f'<aside class="infobox"><h2>{html.escape(page["title"])}</h2>'
        f"<dl>{rows}</dl></aside>"
    )


def toc_html(headings):
    if len(headings) < 3:
        return ""
    items = []
    for level, text, hid in headings:
        cls = ' class="toc-sub"' if level == 3 else ""
        items.append(f'<li{cls}><a href="#{hid}">{html.escape(text)}</a></li>')
    return f'<nav class="toc"><h2>Contents</h2><ol>{"".join(items)}</ol></nav>'


def shell(page, pages, backlinks, body_html, infobox, toc):
    type_labels = CONFIG["type_labels"]
    scopes = CONFIG["spoiler_scopes"]

    cats = ""
    if page["categories"]:
        chips = "".join(
            f'<a class="chip" href="category-{slugify(c)}.html">{html.escape(c)}</a>'
            for c in page["categories"]
        )
        cats = f'<div class="chips">{chips}</div>'

    back = ""
    linkers = sorted(backlinks.get(page["slug"], set()))
    if linkers:
        by_slug = {p["slug"]: p for p in pages}
        items = "".join(
            f'<li><a class="wl" href="{s}.html">{html.escape(by_slug[s]["title"])}</a></li>'
            for s in linkers if s in by_slug
        )
        back = f'<section class="backlinks"><h2>What links here</h2><ul>{items}</ul></section>'

    refs = ""
    if page["sources"]:
        items = "".join(
            f'<li><a href="{html.escape(u)}" rel="noopener">{html.escape(l)}</a></li>'
            for l, u in page["sources"]
        )
        refs = f'<section class="refs"><h2>References</h2><ol>{items}</ol></section>'

    badge = ""
    if page["type"] != "home":
        label = type_labels.get(page["type"], page["type"].title())
        badge = f'<span class="type-badge">{html.escape(label)}</span>'

    summary = f'<p class="page-summary">{html.escape(page["summary"])}</p>' if page["summary"] else ""

    edit = ""
    if page["file"] and CONFIG["edit_base"]:
        edit_url = html.escape(CONFIG["edit_base"] + page["file"], quote=True)
        edit = f'<a href="{edit_url}" rel="noopener">Edit this page on GitHub</a>'

    spoiler_menu = ""
    if scopes:
        boxes = "".join(
            f'<label><input type="checkbox" class="spoil-pref" data-scope="{s["id"]}"> '
            f'{html.escape(s["menu_label"])}</label>'
            for s in scopes
        )
        spoiler_menu = f"""<details class="spoiler-menu">
    <summary>Spoilers</summary>
    <div class="spoiler-panel">
      {boxes}
      <p>Hidden by default. Your choice is remembered on this device.</p>
    </div>
  </details>"""

    scope_css = "".join(
        f'html[data-spoil-{s["id"]}="on"] .spoiler[data-scope="{s["id"]}"] .spoiler-body{{display:block}}'
        for s in scopes
    )

    empty_ctx = {"resolve": {}, "links": set(), "headings": [], "redlinks": set()}
    footer_lines = "".join(f"<p>{render_inline(line, empty_ctx)}</p>" for line in CONFIG["footer"])

    wiki_name = html.escape(CONFIG["name"])
    title = html.escape(page["title"])
    desc = html.escape(page["summary"] or CONFIG["tagline"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | {wiki_name}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title} | {wiki_name}">
<meta property="og:description" content="{desc}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='11' cy='16' r='8' fill='%23a33327'/%3E%3Ccircle cx='21' cy='16' r='8' fill='none' stroke='%23a33327' stroke-width='2.5'/%3E%3C/svg%3E">
<link rel="stylesheet" href="style.css">
<style>{scope_css}</style>
<script>
(function () {{
  var t = null;
  try {{ t = localStorage.getItem("dantalian-theme"); }} catch (e) {{}}
  if (!t) t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = t;
  try {{
    var s = JSON.parse(localStorage.getItem("dantalian-spoilers") || "{{}}");
    for (var k in s) if (s[k]) document.documentElement.setAttribute("data-spoil-" + k, "on");
  }} catch (e) {{}}
}})();
</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <a class="brand" href="index.html"><span class="brand-mark"></span>{wiki_name}</a>
  <div class="search-wrap">
    <input id="search" type="search" placeholder="Search the wiki  ( / )" autocomplete="off"
           aria-label="Search the wiki">
    <div id="search-results" hidden></div>
  </div>
  {spoiler_menu}
  <button id="theme-toggle" type="button" aria-label="Toggle dark mode">◐</button>
</header>
<div class="layout">
  <nav class="sidebar" aria-label="Wiki navigation"><details class="nav-fold" open><summary>Browse</summary>{nav_html(pages, page["slug"])}</details></nav>
  <main id="main">
    <article>
      <div class="page-meta">{badge}{cats}</div>
      <h1>{title}</h1>
      {summary}
      {infobox}
      {toc}
      <div class="page-body">{body_html}</div>
      {back}
      {refs}
      <div class="page-foot">
        {edit}
        <span>Last built {date.today().isoformat()}</span>
      </div>
    </article>
  </main>
</div>
<footer class="site-foot">
{footer_lines}
</footer>
<script src="search-index.js" defer></script>
<script src="wiki.js" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- build

def build(wiki_dir, out_dir):
    global CONFIG, SPOILER_LABELS
    CONFIG = load_config(wiki_dir)
    SPOILER_LABELS = {s["id"]: s["label"] for s in CONFIG["spoiler_scopes"]}

    content_dir = wiki_dir / "content"
    if not content_dir.is_dir():
        sys.exit(f"No content/ directory found in {wiki_dir}")

    valid_types = set(CONFIG["type_labels"])
    pages = [parse_page(p, valid_types) for p in sorted(content_dir.glob("*.md"))]

    slugs = {}
    for p in pages:
        if p["slug"] in slugs:
            sys.exit(f"Duplicate slug '{p['slug']}' ({p['file']} vs {slugs[p['slug']]})")
        slugs[p["slug"]] = p["file"]

    resolve = {}
    for p in pages:
        resolve[p["slug"]] = p["slug"]
        resolve[slugify(p["title"])] = p["slug"]

    # pass 1: render bodies, collect links + headings + redlinks
    all_redlinks = {}
    for p in pages:
        ctx = {
            "resolve": resolve,
            "links": p["links"],
            "headings": p["headings"],
            "redlinks": set(),
        }
        p["body_html"] = render_blocks(p["body"].splitlines(), ctx)
        p["infobox_html"] = infobox_html(p, ctx)
        if ctx["redlinks"]:
            all_redlinks[p["file"]] = sorted(ctx["redlinks"])

    backlinks = {}
    for p in pages:
        for target in p["links"]:
            if target != p["slug"]:
                backlinks.setdefault(target, set()).add(p["slug"])

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    emitted = set()

    def emit(name, content):
        if name in emitted:
            sys.exit(f"Output collision: {name} would be written twice")
        emitted.add(name)
        (out_dir / name).write_text(content, encoding="utf-8")

    # pass 2: write pages
    for p in pages:
        out_name = "index.html" if p["type"] == "home" else f"{p['slug']}.html"
        page_html = shell(p, pages, backlinks, p["body_html"], p["infobox_html"], toc_html(p["headings"]))
        emit(out_name, page_html)
        if p["type"] == "home" and f"{p['slug']}.html" != out_name:
            # also emit under its slug so wikilinks to it resolve
            emit(f"{p['slug']}.html", page_html)

    # category pages
    cats = {}
    for p in pages:
        for c in p["categories"]:
            cats.setdefault(c, []).append(p)
    for cat, members in sorted(cats.items()):
        items = "".join(
            f'<li><a class="wl" href="{m["slug"]}.html">{html.escape(m["title"])}</a>'
            f'<span class="cat-sum">{html.escape(m["summary"])}</span></li>'
            for m in sorted(members, key=lambda m: m["title"])
        )
        cat_page = {
            "file": "",
            "slug": f"category-{slugify(cat)}",
            "title": f"Category: {cat}",
            "type": "category",
            "summary": f"All pages filed under {cat}.",
            "categories": [],
            "infobox": [],
            "sources": [],
            "headings": [],
        }
        body = f'<ul class="cat-list">{items}</ul>'
        emit(f"{cat_page['slug']}.html", shell(cat_page, pages, backlinks, body, "", ""))

    # search index (as JS so it works from file:// too)
    type_labels = CONFIG["type_labels"]
    index = [
        {
            "t": p["title"],
            "s": p["slug"],
            "y": type_labels[p["type"]],
            "d": p["summary"],
            "c": " ".join(p["categories"]),
            "h": " ".join(h[1] for h in p["headings"]),
        }
        for p in pages
    ]
    (out_dir / "search-index.js").write_text(
        "window.SEARCH_INDEX=" + json.dumps(index, ensure_ascii=False) + ";",
        encoding="utf-8",
    )

    for asset in ("style.css", "wiki.js"):
        shutil.copy(ASSETS / asset, out_dir / asset)

    print(f"Built {len(pages)} pages + {len(cats)} category pages into {out_dir}/")
    if all_redlinks:
        print("Red links (pages referenced but not yet written):")
        for f, targets in all_redlinks.items():
            print(f"  {f}: {', '.join(targets)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build a Bibliotheca Dantalian wiki.")
    ap.add_argument("wiki_dir", nargs="?", default="example",
                    help="directory containing wiki.json and content/ (default: example)")
    ap.add_argument("--out", default="docs",
                    help="output directory (default: docs)")
    args = ap.parse_args()
    build(Path(args.wiki_dir), Path(args.out))
