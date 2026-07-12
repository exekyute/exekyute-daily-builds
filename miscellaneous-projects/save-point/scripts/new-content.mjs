// Scaffold a new guide or blog post with ready-to-fill frontmatter.
// New content starts as a draft so it never leaks into a production build.
//
// Usage:
//   npm run new:guide -- --title "Whistlewood: 100% Walkthrough" --game "Whistlewood" [--category walkthrough]
//   npm run new:post  -- --title "Why tactics games rule"
import { writeFileSync, existsSync } from "node:fs";

const args = process.argv.slice(2);
const kind = args[0];

function opt(name, fallback = "") {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
}

const title = opt("title");
if (!["guide", "post"].includes(kind) || !title) {
  console.error('Usage: npm run new:guide -- --title "..." --game "..." [--category walkthrough]');
  console.error('       npm run new:post  -- --title "..."');
  process.exit(1);
}

const slug = title
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/(^-|-$)/g, "");
const today = new Date().toISOString().slice(0, 10);

let path, body;

if (kind === "guide") {
  const game = opt("game", "Game Name");
  const category = opt("category", "walkthrough");
  path = `src/content/guides/${slug}.mdx`;
  body = `---
title: "${title}"
summary: "One-line description used on cards and in search."
game: "${game}"
platforms: ["PC"]
category: "${category}"
tags: []
spoilers: "minor"
published: ${today}
draft: true
changelog:
  - date: ${today}
    note: First published.
---
import Callout from "../../components/Callout.astro";

Opening paragraph. What this guide covers and who it is for.

<Callout type="tip" title="Read this first">
Anything the reader should know before starting.
</Callout>

## First section

Write the guide. See docs/AUTHORING.md for the component cheat sheet
(Gallery, Checklist, StatBlock, DataTable, Infobox, Tabs, Spoiler).
`;
} else {
  path = `src/content/blog/${slug}.mdx`;
  body = `---
title: "${title}"
summary: "One-line description used on cards and in search."
tags: []
published: ${today}
draft: true
---

Opening paragraph.

## First section

Write the post.
`;
}

if (existsSync(path)) {
  console.error(`Refusing to overwrite: ${path} already exists.`);
  process.exit(1);
}

writeFileSync(path, body);
console.log(`Created ${path}`);
console.log(`URL when published: /${kind === "guide" ? "guides" : "blog"}/${slug}/`);
console.log("Next: write it, flip draft: false, commit.");
