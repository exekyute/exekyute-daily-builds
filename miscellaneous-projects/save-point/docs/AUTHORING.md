# Authoring guide

How to add and update content. Publishing a guide is one file. No database, no admin panel.

## Add a guide

The fast way, from the project folder:

```bash
npm run new:guide -- --title "Whistlewood: 100% Walkthrough" --game "Whistlewood"
npm run new:post  -- --title "Backlog notes, July"
```

That creates a draft `.mdx` with the frontmatter filled in. Or by hand:

1. Create `src/content/guides/my-guide-slug.mdx`. The filename becomes the URL:
   `/guides/my-guide-slug/`.
2. Fill in the frontmatter (see the reference below).
3. Write the body in Markdown, dropping in components where you want them.
4. Run `npm run dev` and open the page. Save the file and it hot-reloads.

That is it. The homepage, the guide library, the per-game hub, the category grouping, the
related-guides block, the RSS feed, and the sitemap all update themselves from the frontmatter.

## Update a guide (the edit trail)

Every guide is one plain-text file in git, so every edit is visible, reversible, and
trackable by default. The routine:

1. Edit the file. Check it in `npm run dev`.
2. Bump `updated:` and add a line to `changelog:` describing what changed. The changelog
   renders as an "Update history" panel on the page, so readers see it too.
3. Commit with a message that says what changed and why
   (`git commit -am "whistlewood: fix Bellowbat spawn window"`).
4. Push. Once the repo is wired to Cloudflare Pages or Netlify, pushing deploys the site
   automatically, and every previous deployment stays available for one-click rollback.

Useful git moves: `git log --follow -- src/content/guides/foo.mdx` shows a guide's full
history, `git diff` shows exactly what changed before you commit, and `git revert` undoes
any published mistake without losing history.

## Guide frontmatter reference

```yaml
---
title: "Game Name: 100% Completion Walkthrough"   # required
summary: "One-line description used on cards and in search."  # required
game: "Game Name"            # required, drives the per-game hub
platforms: ["PC", "Console"] # optional
category: "walkthrough"      # walkthrough | boss | collectibles | builds |
                             # trophies | beginner | endgame | secrets | reference
tags: ["100%", "missable"]   # optional
cover: ../../assets/my-cover.png   # optional, optimized automatically
coverAlt: "Describe the cover"     # optional but recommended
spoilers: "minor"            # none | minor | major, drives the spoiler banner
difficulty: "medium"         # easy | medium | hard, optional
author: "Kevin Yu"           # defaults to the site author (src/content/config.ts)
published: 2025-06-20        # required
updated: 2025-06-29          # optional, shown as the "Updated" date
draft: false                 # true keeps it out of production builds
featured: false              # true surfaces it on the homepage
order: 1                     # optional sort order within a game hub
changelog:                   # optional, renders as "Update history" on the page
  - date: 2025-06-20
    note: First published.
  - date: 2025-06-29
    note: Added the duet damage table.
---
```

Blog posts live in `src/content/blog/` and use a smaller frontmatter set (no game,
category, platforms, spoilers, or difficulty).

## Components cheat sheet

Import what you use at the top of the MDX file, then drop the tag inline.

```mdx
import Gallery from "../../components/Gallery.astro";
import Checklist from "../../components/Checklist.astro";
import StatBlock from "../../components/StatBlock.astro";
import DataTable from "../../components/DataTable.astro";
import Callout from "../../components/Callout.astro";
import Spoiler from "../../components/Spoiler.astro";
import Infobox from "../../components/Infobox.astro";
import Tabs from "../../components/Tabs.astro";
```

**Gallery** (rolling carousel by default; also grid, masonry, filmstrip). Images live in
`public/images/` and are referenced by path.

```mdx
<Gallery view="carousel" images={[
  { src: "/images/gallery/shot-1.png", alt: "Area name", caption: "Optional caption." },
]} />
```

**Checklist** (persistent, saves to the reader's browser). Give it a unique `id`.

```mdx
<Checklist id="spirits" title="Spirits to record" items={[
  { id: "cinderpuff", label: "Cinderpuff - Bellport rooftops" },
  { id: "gloamoth", label: "Gloamoth - shrine", missable: true, note: "Closes after the boss." },
]} />
```

**StatBlock** (roadmap summary). Every field is optional.

```mdx
<StatBlock difficulty="6 / 10" time="35-45 hours" playthroughs="1"
  missable="3 missable" trophies="42 achievements"
  note="No difficulty-locked achievements." />
```

**DataTable** (sortable, filterable). List which column indexes are numeric.

```mdx
<DataTable caption="Profits" columns={["Crop", "Season", "Profit"]} numeric={[2]} rows={[
  ["Glowberry", "Spring", "47"],
]} />
```

**Callout** (`info | tip | warn | danger | missable`):

```mdx
<Callout type="missable" title="Do not skip this">Grab it before the boss.</Callout>
```

**Spoiler** (click to reveal):

```mdx
<Spoiler label="Final boss weakness">It is weak to Fire.</Spoiler>
```

**Infobox** (data panel; floats right by default):

```mdx
<Infobox title="Cinderpuff" subtitle="Ember type" image="/images/gallery/shot-3.png"
  fields={[["Type", "Ember"], ["Found", "Bellport rooftops"]]} />
```

**Tabs** (version content; slots are `tab1`..`tab6`):

```mdx
<Tabs tabs={["PC", "Console"]}>
  <Fragment slot="tab1">PC notes.</Fragment>
  <Fragment slot="tab2">Console notes.</Fragment>
</Tabs>
```

## Images

- Guide and post **covers** go in `src/assets/` and are referenced in frontmatter with a
  relative path. Astro optimizes them to WebP automatically.
- **Gallery and inline images** go in `public/images/` and are referenced by absolute path
  like `/images/gallery/shot-1.png`. There is no unique-name requirement and no storage cap.

## Turn on comments

Comments use giscus (GitHub Discussions, no tracking, no database). To enable, create a
`Comments.astro` component with your giscus repo settings and render it in
`src/layouts/GuideLayout.astro` where the comments placeholder note currently sits.

## Demo content

Every game, character, and place in the sample guides (Whistlewood, Banners of Ashvale)
is fictional. Replace the sample content with your own guides and keep writing.
