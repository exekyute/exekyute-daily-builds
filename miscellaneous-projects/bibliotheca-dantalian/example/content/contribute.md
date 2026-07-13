---
title: How to Contribute
type: meta
summary: How editing works on a git-backed wiki, and how to add or fix a page.
categories: Wiki Governance
---
This wiki has no edit button that saves directly. Every page is a Markdown file in a git repository, and every change arrives as a pull request. That trade is deliberate: no vandalism cleanup, full history on every page, and review before publish.

## Fixing a page

1. Click **Edit this page on GitHub** at the foot of any page.
2. Make the change in GitHub's editor and propose it. That opens a pull request automatically.
3. A maintainer reviews it against the [[Editorial Policy]] and merges. The site rebuilds from the merged file.

## Adding a page

1. Pick a red link, the amber ones; each is a page someone already wanted. The build's red-link report lists them all.
2. Create a new file in the wiki's content folder. The file name becomes the page address.
3. Start from this skeleton:

```
---
title: Page Title
type: character
summary: One line, spoiler-free, shown in search and previews.
categories: Characters
infobox:
  Japanese: 日本語
  Debut: Chapter 1
sources:
  - Official site | https://example.com
---
Opening section, safe for premise-level readers.

::: spoiler manga Manga spoilers through volume 11
Scoped material.
:::
```

4. Link generously with `[[Wikilinks]]`. Links to pages that do not exist yet are fine; that is how the to-do list grows.

## House style

Write plainly, cite what you claim, and keep summaries and infoboxes spoiler-free. The [[Editorial Policy]] has the full rules, including the naming and spoiler-scoping conventions reviewers check first.
