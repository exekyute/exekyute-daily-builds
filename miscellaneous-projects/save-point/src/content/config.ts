import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

// ---------------------------------------------------------------------------
// Content collections = the "easy to update with metadata" layer.
// To publish a guide, drop an .mdx file in src/content/guides with this
// frontmatter. The site builds indexes, tag pages, related links, and the
// game hub automatically from these fields. No database, no admin panel.
// ---------------------------------------------------------------------------

const guides = defineCollection({
  loader: glob({ base: "./src/content/guides", pattern: "**/*.{md,mdx}" }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      // Short one-liner used on cards and in search.
      summary: z.string(),
      // The game this guide covers; drives the per-game hub pages.
      game: z.string(),
      // Free-form platform tags, e.g. ["PC", "Console"].
      platforms: z.array(z.string()).default([]),
      // Guide type powers filtering: walkthrough, boss, collectibles, builds...
      category: z
        .enum([
          "walkthrough",
          "boss",
          "collectibles",
          "builds",
          "trophies",
          "beginner",
          "endgame",
          "secrets",
          "reference",
        ])
        .default("walkthrough"),
      tags: z.array(z.string()).default([]),
      cover: image().optional(),
      coverAlt: z.string().default(""),
      // Spoiler intensity lets the UI warn readers up front.
      spoilers: z.enum(["none", "minor", "major"]).default("minor"),
      // Editorial difficulty/effort signal, optional.
      difficulty: z.enum(["easy", "medium", "hard"]).optional(),
      author: z.string().default("Kevin Yu"),
      published: z.coerce.date(),
      updated: z.coerce.date().optional(),
      // Set true to keep a draft out of production builds.
      draft: z.boolean().default(false),
      // Reading order within a multi-part guide (optional).
      order: z.number().optional(),
      // Mark a guide as featured on the homepage.
      featured: z.boolean().default(false),
      // Reader-visible update history; renders as "Update history" on the page.
      changelog: z
        .array(z.object({ date: z.coerce.date(), note: z.string() }))
        .default([]),
    }),
});

const blog = defineCollection({
  loader: glob({ base: "./src/content/blog", pattern: "**/*.{md,mdx}" }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      summary: z.string(),
      tags: z.array(z.string()).default([]),
      cover: image().optional(),
      coverAlt: z.string().default(""),
      author: z.string().default("Kevin Yu"),
      published: z.coerce.date(),
      updated: z.coerce.date().optional(),
      draft: z.boolean().default(false),
      featured: z.boolean().default(false),
    }),
});

export const collections = { guides, blog };
