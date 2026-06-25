# Steam Global Achievements Downloader

A Firefox userscript that adds a **Download achievements** button to any Steam game's global achievements page. Click it and every achievement's name, description, and icon gets saved into a folder named after the game.

## What it downloads

For a game like Portal, clicking the button produces this inside your Firefox Downloads folder:

```
Downloads/
└── Portal/
    ├── achievements.txt
    ├── icons_64/
    │   ├── Heartbreaker.jpg
    │   ├── Cake_and_Grief_Counseling.jpg
    │   └── ... (one .jpg per achievement, the original Steam icon)
    └── icons_256/
        ├── Heartbreaker.png
        ├── Cake_and_Grief_Counseling.png
        └── ... (one .png per achievement, upscaled 4×)
```

`achievements.txt` looks like:

```
Game: Portal
Source: https://steamcommunity.com/stats/400/achievements/
Achievement count: 15

1. Heartbreaker
   Break the heart of GLaDOS.

2. Cake and Grief Counseling
   Help test the Weighted Companion Cube.
...
```

## Install

You already have **Tampermonkey** in Firefox. To install the script:

1. Open the Tampermonkey dashboard (toolbar icon → **Dashboard**).
2. Click the **+** tab ("Create new script").
3. Delete the placeholder, paste the full contents of `steam-achievements.user.js`, and press **Ctrl+S**.

Or: drag `steam-achievements.user.js` onto a Firefox window and Tampermonkey will offer to install it.

## Use

1. Open any Steam game's global achievements page, e.g. <https://steamcommunity.com/stats/400/achievements/>.
2. A green **⬇ Download achievements** button appears at the top of the achievement list.
3. Click it. Progress text shows next to the button while files download.
4. When it finishes, open `Downloads/<Game Name>/` to see the results.

## Notes

- **Icon sizes**: Steam only serves 64x64. Steamworks actually requires developers to upload icons at exactly that size, so there is no larger original anywhere on Steam's CDN. The script saves that original to `icons_64/` and then **upscales** it in the browser (via a canvas with high-quality smoothing) to produce a larger PNG in `icons_256/`. This isn't a magic AI upscaler; it's bicubic resampling, so the upscaled image is smoother and bigger but no more detailed than the source. To change the upscale size, edit `UPSCALE_SIZE` near the top of the script (set to `0` to skip the upscale and only save the 64x64 originals; try `128`, `512`, etc.). Hidden-achievement icons download fine, since Steam serves the image even when it hides the text.
- **Hidden achievements (unhiding)**: when the script sees an achievement Steam has marked as hidden, it quietly fetches that game's stats page on [SteamDB](https://steamdb.info) and pulls the real description from there. Matching is done by the achievement's icon hash, which is identical on both sites. Lines unhidden this way are tagged `[hidden: revealed via SteamDB]` in the .txt so you can tell them apart. If SteamDB can't be reached (Cloudflare challenge, offline, etc.) the achievement stays marked `[hidden: description not shown by Steam]` and the rest of the download still finishes.
- **First run**: Tampermonkey will pop up permission prompts the first time `GM_download` and `GM_xmlhttpRequest` are used, plus one for the `steamdb.info` domain specifically. Allow them, optionally with "always," so future runs are silent.
- **Where files go**: wherever your Firefox download directory is set (Firefox → Settings → Files and Applications → Downloads). The script creates a subfolder there named after the game.

## Troubleshooting

- **Button doesn't appear**: make sure you're on the *global* achievements page (`/stats/<appid>/achievements/`), not your personal one. Reload the page after installing the script.
- **Downloads fail silently**: open Tampermonkey → Settings → set "Config mode" to Advanced → "Downloads BETA → Mode" should be `browser` (the default). The browser API mode handles subfolders correctly.
- **A few icons missing**: the script logs failures to the browser console (F12 → Console). Re-running usually picks them up.
- **Hidden descriptions stayed hidden**: SteamDB is gated by Cloudflare. If you haven't visited SteamDB in this Firefox profile for a while, the first request can land on a challenge page. Open <https://steamdb.info> in a tab once (so Cloudflare sets a cookie), then rerun the download. The console (F12) will show why the lookup failed if it keeps not working.
