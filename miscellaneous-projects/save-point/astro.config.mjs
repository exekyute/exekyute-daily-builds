// @ts-check
import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";

// Anti-bloat by default: static output, zero client JS unless a component
// explicitly opts in with a client directive. Update `site` before deploying.
export default defineConfig({
  site: "https://example.com",
  output: "static",
  integrations: [mdx(), sitemap()],
  image: {
    // Astro optimizes and serves modern formats; keeps galleries light.
    responsiveStyles: true,
  },
  build: {
    inlineStylesheets: "auto",
  },
});
