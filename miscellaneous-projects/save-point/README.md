# Save Point

A fast, no-bloat guide and blog template for game guide sites. Completion guides,
collectible checklists, and achievement roadmaps that load in under a second and never
fight the reader.

Built with [Astro](https://astro.build): static output, zero client JavaScript by default,
and content components that go well beyond what BBCode or a forum wiki can do.

Made by [Kevin Yu](https://github.com/exekyute).

## Features

- **Interactive checklists** that save progress to the reader's browser, no login
- **Sortable, filterable tables** for stat lines, drop tables, and profit ledgers
- **Image galleries** in four views (rolling carousel, grid, masonry, filmstrip) with a
  full-screen lightbox
- **Guide components** you drop into any page: roadmap stat blocks, infoboxes, version
  tabs, spoiler toggles, and callouts
- **Sticky table of contents** with scroll-spy on every long guide
- **Reader-visible update history** per guide, driven by frontmatter
- **Per-game hubs**, a filterable guide library, tags, RSS, and a sitemap, all generated
  from frontmatter
- **Three themes** with a soft cross-fade: printed-guide paper, graph-paper grid, and a
  dark RPG-menu mode
- Responsive and accessible, with nothing tracking the reader and nothing autoplaying

## Quick start

```bash
npm install
npm run dev        # http://localhost:4321
```

```bash
npm run build      # static site to ./dist
npm run preview    # preview the production build

npm run new:guide -- --title "Guide title" --game "Game"   # scaffold a draft guide
npm run new:post  -- --title "Post title"                  # scaffold a draft post
```

`scripts/generate-placeholders.mjs` regenerates the demo images.

## Project layout

```
src/
  components/    Gallery, Checklist, StatBlock, DataTable, Infobox, Tabs, Spoiler, Callout, TableOfContents
  content/
    guides/      one .mdx file per guide
    blog/        one .mdx file per post
    config.ts    typed frontmatter schema
  layouts/       BaseLayout, GuideLayout, BlogLayout
  pages/         routes (home, guides, blog, games, about, support, rss, 404)
  styles/        global.css (design tokens and the three themes)
  consts.ts      site name, nav, category labels
docs/
  AUTHORING.md   how to add and update content
public/
  images/        gallery and inline images
```

## Adding content

Publishing a guide is one Markdown file. See [docs/AUTHORING.md](docs/AUTHORING.md) for the
frontmatter reference and the component cheat sheet.

## Demo content

The games in the sample guides and images (Whistlewood, Banners of Ashvale) are fictional,
invented for this template. Any resemblance to real games is coincidental. Replace the
sample content with your own guides.

## Deploy

The site is static, so it hosts free on Cloudflare Pages, Netlify, or GitHub Pages. Set
`site` in `astro.config.mjs` and `SITE.url` in `src/consts.ts` to your domain before building.

## License

MIT. Copyright Kevin Yu ([github.com/exekyute](https://github.com/exekyute)).
