import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import { SITE } from "../consts";

export async function GET(context) {
  const guides = await getCollection("guides", (d) => !d.data.draft);
  const posts = await getCollection("blog", (d) => !d.data.draft);
  const items = [
    ...guides.map((g) => ({
      title: g.data.title,
      description: g.data.summary,
      pubDate: g.data.updated ?? g.data.published,
      link: `/guides/${g.id}/`,
      categories: [g.data.game, g.data.category],
    })),
    ...posts.map((p) => ({
      title: p.data.title,
      description: p.data.summary,
      pubDate: p.data.published,
      link: `/blog/${p.id}/`,
      categories: p.data.tags,
    })),
  ].sort((a, b) => +new Date(b.pubDate) - +new Date(a.pubDate));

  return rss({
    title: SITE.name,
    description: SITE.description,
    site: context.site ?? SITE.url,
    items,
  });
}
