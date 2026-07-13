# Bibliotheca Dantalian

A zero-dependency static wiki engine for fan wikis. Spoiler-safe by default, git-backed, no ads ever.

The name is borrowed from Dantalion, the 71st spirit of the Ars Goetia, a duke of Hell who teaches all arts and sciences and keeps a book containing every thought. A fitting patron for a fan encyclopedia.

Bibliotheca Dantalian turns a folder of Markdown files into a complete wiki: wikilinks with red-link tracking, per-page backlinks, category indexes, infoboxes, client-side search, dark mode, and scoped spoiler blocks that stay hidden until the reader opts in. The engine is one Python script with no dependencies beyond the standard library; the output is plain static HTML you can host anywhere, including free on GitHub Pages.

I built this after digging through the documented failures of the big wiki farms: spoilers by ambush, autoplay ads, romanization chaos, unsourced speculation, and stub sprawl. The research behind every design decision, and the receipts, are in [DESIGN-RESEARCH.md](DESIGN-RESEARCH.md).

## The example wiki

The engine ships with a complete working example: the **Veilharbor Archive**, a 20-page fan wiki for *Lanternfall* (ランタンフォール), a manga and mid-airing 2026 anime that do not exist. The series, its author, and its publisher are all invented for this demo, so the repo ships nothing owned by anyone, while the wiki itself plays it straight: premise-safe summaries, sourced claims, and dual spoiler scopes (anime and manga) for an adaptation mid-run. Its editorial-policy and contribution pages show how a wiki built on this engine governs itself. Everything under `example/` is content; nothing in it is required by the engine.

## Features

- **Scoped spoiler blocks.** Declare any spoiler scopes in `wiki.json` (the example uses `anime` and `manga`; a game wiki might use `dlc`). Blocks stay hidden until the reader opts in from the header menu or reveals one in place, and the choice persists per device. It works identically on mobile, with no server involved.
- **Real wiki linking.** `[[Wikilinks]]` between pages, amber red links for pages that do not exist yet, and an automatic "What links here" section on every page. The build prints a red-link report, which doubles as the contributor to-do list.
- **Instant search.** A client-side index over titles, summaries, categories, and headings. Press `/` anywhere. Works even when the site is opened straight from disk.
- **Infoboxes and categories** from front matter, with automatic category index pages.
- **Git-backed editing.** Every page carries an "Edit this page on GitHub" link; edits arrive as pull requests, so publishing means review, history, and structurally zero vandalism.
- **Self-contained output.** No external fonts, no CDN calls, no trackers. Two-tone design with dark mode.

## Quick start

Build and serve the example wiki:

```
cd miscellaneous-projects/bibliotheca-dantalian
python build.py
python -m http.server 8199 -d docs
```

Then open http://localhost:8199. Python 3.9+ is the only requirement.

## Start your own wiki

A wiki is a directory containing `wiki.json` and a `content/` folder:

```
my-wiki/
  wiki.json
  content/
    index.md
    some-page.md
```

Build it with `python build.py my-wiki --out docs`.

### wiki.json

```json
{
  "name": "My Wiki",
  "tagline": "Shown in page metadata and as the default description.",
  "repo_url": "https://github.com/you/my-wiki",
  "edit_base": "https://github.com/you/my-wiki/edit/main/content/",
  "spoiler_scopes": [
    { "id": "anime", "label": "Anime spoilers", "menu_label": "Show anime spoilers" }
  ],
  "nav": [
    { "group": "Characters", "types": ["character"] },
    { "group": "Meta", "types": ["meta"] }
  ],
  "type_labels": { "home": "Home", "character": "Character", "meta": "Meta" },
  "footer": ["Any lines you want in the site footer. Markdown links work."]
}
```

`name` and `tagline` are required. Page types, their nav grouping, spoiler scopes, and the footer are all yours to define; the engine contains nothing about any particular series.

### Pages

Pages are Markdown files with a small front matter block. The file name becomes the page address.

```
---
title: Page Title
type: character
summary: One line shown in search results and link previews.
categories: Characters
infobox:
  Japanese: 日本語名
  Debut: Chapter 1
sources:
  - Official site | https://example.com
---
Introduction that is safe for spoiler-free readers.

## A section

::: spoiler anime Anime spoilers through episode 7
Hidden until the reader opts in to that scope.
:::
```

Supported syntax: `##`/`###`/`####` headings, `**bold**`, `*italic*`, `` `code` ``, fenced code blocks, lists, tables, blockquotes, `[[Wikilinks]]`, `[[Target|custom label]]`, external links, and scoped spoiler blocks. The example's [How to Contribute](example/content/contribute.md) and [Editorial Policy](example/content/editorial-policy.md) pages show the house rules a wiki can build on top.

## Deploy

The build writes to `docs/` by default, which GitHub Pages can serve straight from the main branch (Settings, Pages, deploy from branch, `/docs`). Any static host works.

## Repository layout

```
build.py        the entire engine
assets/         style.css and wiki.js, copied into every build
example/        the Veilharbor Archive example wiki (a fictional series, invented for the demo)
docs/           the built example site
```

## License

Engine code is MIT licensed (see LICENSE). The example wiki's text is CC BY-SA 4.0, and all of it is original fiction written for this repo; no copyrighted series content or artwork ships here.
