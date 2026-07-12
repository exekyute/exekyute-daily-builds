// Generates lightweight placeholder "screenshots" so the demo galleries render.
// Real builds replace these with actual captures. Run: node scripts/generate-placeholders.mjs
import sharp from "sharp";
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";

const PUB = "public/images";
const ASSET = "src/assets";

function svg({ w, h, c1, c2, label, sub }) {
  return Buffer.from(`
  <svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${c1}"/>
        <stop offset="1" stop-color="${c2}"/>
      </linearGradient>
      <radialGradient id="v" cx="0.5" cy="0.35" r="0.8">
        <stop offset="0" stop-color="rgba(255,255,255,0.18)"/>
        <stop offset="1" stop-color="rgba(0,0,0,0)"/>
      </radialGradient>
    </defs>
    <rect width="${w}" height="${h}" fill="url(#g)"/>
    <rect width="${w}" height="${h}" fill="url(#v)"/>
    <rect x="0" y="${Math.round(h * 0.30)}" width="${w}" height="${Math.round(h * 0.42)}" fill="rgba(8,10,14,0.42)"/>
    <g font-family="Segoe UI, system-ui, sans-serif" fill="#fff" text-anchor="middle">
      <text x="${w / 2}" y="${h / 2 - 4}" font-size="${Math.round(h / 8)}" font-weight="700">${label}</text>
      <text x="${w / 2}" y="${h / 2 + Math.round(h / 8.5)}" font-size="${Math.round(h / 13)}" font-weight="600" opacity="0.92">${sub}</text>
    </g>
    <rect x="0" y="0" width="${w}" height="${h}" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="2"/>
  </svg>`);
}

const palettes = [
  ["#1f6f8b", "#0b3d52"], ["#7b3f9e", "#311b4a"], ["#b5651d", "#5c2e0c"],
  ["#2e8b57", "#123524"], ["#b23a48", "#4a1018"], ["#3a5fcd", "#16245c"],
  ["#c9a227", "#5e4b0c"], ["#127475", "#062c2c"],
];

async function out(path, buf) {
  await mkdir(dirname(path), { recursive: true });
  await sharp(buf).png({ quality: 80 }).toFile(path);
  console.log("wrote", path);
}

const jobs = [];

// Gallery screenshots (served from /public, referenced by path).
// All game names and scenes are fictional demo content.
const shots = [
  ["Coastal Path", "Whistlewood"],
  ["Bellport Square", "Whistlewood"],
  ["Recording a Spirit", "Whistlewood"],
  ["Duet Form", "Whistlewood"],
  ["Mt. Carillon", "Whistlewood"],
  ["Warden Boss", "Whistlewood"],
  ["Shrine of Chimes", "Whistlewood"],
  ["Night Bazaar", "Whistlewood"],
];
shots.forEach(([label, sub], i) => {
  jobs.push(out(`${PUB}/gallery/shot-${i + 1}.png`,
    svg({ w: 1280, h: 720, c1: palettes[i % palettes.length][0], c2: palettes[i % palettes.length][1], label, sub })));
});

// Map placeholder for the interactive-map teaser
jobs.push(out(`${PUB}/maps/bellport.png`,
  svg({ w: 1600, h: 1000, c1: "#27506b", c2: "#0c2030", label: "Bellport Map", sub: "annotated overlay demo" })));

// Cover images (optimized via astro:assets, so they live in src/assets)
const covers = [
  ["whistlewood-walkthrough", "Whistlewood", "Full Walkthrough", "#7b3f9e", "#311b4a"],
  ["ashvale-achievements", "Ashvale", "Achievement Guide", "#b23a48", "#4a1018"],
  ["starter-spirits", "Starter Spirits", "Tier Picks", "#1f6f8b", "#0b3d52"],
  ["blog-top-jrpgs-2025", "Top JRPGs 2025", "Editorial", "#c9a227", "#5e4b0c"],
  ["blog-why-monster-collectors", "Monster Collectors", "Opinion", "#2e8b57", "#123524"],
];
covers.forEach(([name, label, sub, c1, c2]) => {
  jobs.push(out(`${ASSET}/${name}.png`, svg({ w: 1200, h: 630, c1, c2, label, sub })));
});

// Site logo mark
jobs.push(out(`${PUB}/og-default.png`,
  svg({ w: 1200, h: 630, c1: "#161c27", c2: "#0d1117", label: "Save Point", sub: "RPG guides, no bloat" })));

await Promise.all(jobs);
console.log("done");
