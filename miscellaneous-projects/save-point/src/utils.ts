export function formatDate(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  // Frontmatter dates parse as UTC midnight; format in UTC so they do not
  // drift a day backward in negative-offset timezones.
  return date.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function isoDate(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toISOString().slice(0, 10);
}

// Rough reading time from rendered word count.
export function readingTime(body: string | undefined): string {
  const words = (body ?? "").trim().split(/\s+/).filter(Boolean).length;
  const mins = Math.max(1, Math.round(words / 220));
  return `${mins} min read`;
}

export function gameSlug(game: string): string {
  return game
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}
