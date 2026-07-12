// Site-wide constants. Rename freely - this is the one place to edit branding.
export const SITE = {
  name: "Save Point",
  tagline: "Completion guides for tactics RPGs and JRPGs. Fast, clean, no bloat.",
  // Used for absolute URLs in RSS/sitemap; update before deploying.
  url: "https://example.com",
  author: "Kevin Yu",
  description:
    "100% achievement guides, collectible checklists, and completion roadmaps for tactics RPGs and JRPGs - built to load fast and read clean.",
};

export const NAV = [
  { label: "Guides", href: "/guides/" },
  { label: "Games", href: "/games/" },
  { label: "Blog", href: "/blog/" },
  { label: "About", href: "/about/" },
];

// Category labels used across cards, filters, and badges.
export const CATEGORY_LABELS: Record<string, string> = {
  walkthrough: "Walkthrough",
  boss: "Boss",
  collectibles: "Collectibles",
  builds: "Builds",
  trophies: "Achievements",
  beginner: "Beginner",
  endgame: "Endgame",
  secrets: "Secrets",
  reference: "Reference",
};
