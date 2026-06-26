// ==UserScript==
// @name         Steam Global Achievements Downloader
// @namespace    https://github.com/local/steam-achievements-downloader
// @version      1.0.0
// @description  Adds a button to Steam's global achievements page that downloads every achievement name, description, and icon into a folder named after the game.
// @match        https://steamcommunity.com/stats/*/achievements*
// @run-at       document-end
// @grant        GM_download
// @grant        GM_xmlhttpRequest
// @connect      cloudflare.steamstatic.com
// @connect      akamaihd.net
// @connect      steamstatic.com
// @connect      steamcommunity.com
// @connect      steamdb.info
// ==/UserScript==

(function () {
    'use strict';

    // ---- Config ----
    // Steam only serves achievement icons at 64x64 (Steamworks requires devs to upload that exact size).
    // To get a larger image we upscale in the browser. Set to 0 to skip upscaling entirely.
    const UPSCALE_SIZE = 256;

    // Characters Windows (and most filesystems) refuse in filenames.
    const ILLEGAL_FILENAME_CHARS = /[\\/:*?"<>|\x00-\x1F]/g;

    function sanitizeFilename(name) {
        return name.replace(ILLEGAL_FILENAME_CHARS, '').trim().replace(/\.+$/, '') || 'untitled';
    }

    function getGameName() {
        // Steam puts the game name in the community header bar.
        const header = document.querySelector('.apphub_AppName');
        if (header && header.textContent.trim()) {
            return header.textContent.trim();
        }
        // Fallback: parse the <title>, which looks like "Steam Community :: <Game> :: Achievements".
        const titleMatch = document.title.match(/::\s*(.+?)\s*::/);
        return titleMatch ? titleMatch[1] : 'Unknown Game';
    }

    function getAppId() {
        // URL looks like https://steamcommunity.com/stats/<APPID>/achievements/
        const m = location.pathname.match(/\/stats\/(\d+)\//);
        return m ? m[1] : null;
    }

    function extractIconHash(url) {
        // Steam icons look like .../<APPID>/<HASH>.jpg — the hash is the achievement's stable ID.
        const m = (url || '').match(/\/([a-f0-9]{20,})\.(?:jpg|jpeg|png|gif|webp)/i);
        return m ? m[1].toLowerCase() : null;
    }

    function getAchievements() {
        // Steam wraps each achievement in a row containing an icon and a .achieveTxt block
        // with <h3> (name) and <h5> (description). The row class has changed over the years,
        // so we look for the inner .achieveTxt and walk up to its parent row.
        const blocks = document.querySelectorAll('.achieveTxt');
        const results = [];

        blocks.forEach((block) => {
            const row = block.closest('.achieveRow') || block.parentElement;
            const nameEl = block.querySelector('h3');
            const descEl = block.querySelector('h5');
            const iconEl = row ? row.querySelector('img') : null;

            if (!nameEl || !iconEl) return;

            const name = nameEl.textContent.trim();
            const rawDesc = descEl ? descEl.textContent.trim() : '';
            // Steam blanks out (or stubs as "Hidden achievement.") the description for
            // spoiler-locked achievements. We mark those so we know to fetch the real text
            // from SteamDB afterwards.
            const isHidden = !rawDesc || /^hidden achievement\.?$/i.test(rawDesc);

            results.push({
                name,
                description: rawDesc,
                isHidden,
                iconUrl: iconEl.src,
                iconHash: extractIconHash(iconEl.src),
            });
        });

        return results;
    }

    function gmFetch(url) {
        // GM_xmlhttpRequest bypasses CORS so we can read SteamDB's HTML from a Steam page.
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url,
                headers: { 'Accept': 'text/html,application/xhtml+xml' },
                onload: (res) => {
                    if (res.status >= 200 && res.status < 300) resolve(res.responseText);
                    else reject(new Error(`HTTP ${res.status} for ${url}`));
                },
                onerror: () => reject(new Error('network error')),
                ontimeout: () => reject(new Error('timeout')),
            });
        });
    }

    async function fetchHiddenDescriptions(appId) {
        // SteamDB's per-game stats page lists every achievement with its real description,
        // including the ones Steam hides on the community page. We match by icon hash, which
        // is identical across Steam and SteamDB.
        const html = await gmFetch(`https://steamdb.info/app/${appId}/stats/`);
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const map = new Map();

        doc.querySelectorAll('tr').forEach((tr) => {
            const img = tr.querySelector('img');
            if (!img) return;
            const hash = extractIconHash(img.getAttribute('src') || img.src || '');
            if (!hash) return;

            // The achievement row on SteamDB has its display name and description in the
            // same cell, separated by a <br>. Convert <br> to newline and split.
            const cells = tr.querySelectorAll('td');
            const textCell = [...cells].find((c) => c.querySelector('br')) || cells[cells.length - 2] || cells[cells.length - 1];
            if (!textCell) return;

            const html2 = textCell.innerHTML.replace(/<br\s*\/?>/gi, '\n');
            const tmp = document.createElement('div');
            tmp.innerHTML = html2;
            const lines = tmp.textContent.split('\n').map((s) => s.trim()).filter(Boolean);
            // First line is the display name, the rest is the description.
            const desc = lines.slice(1).join(' ').trim();
            if (desc) map.set(hash, desc);
        });

        return map;
    }

    async function revealHidden(achievements, appId, status) {
        const hiddenCount = achievements.filter((a) => a.isHidden).length;
        if (hiddenCount === 0 || !appId) return;

        status.textContent = `Looking up ${hiddenCount} hidden description${hiddenCount === 1 ? '' : 's'} on SteamDB…`;
        try {
            const map = await fetchHiddenDescriptions(appId);
            let revealed = 0;
            achievements.forEach((a) => {
                if (a.isHidden && a.iconHash && map.has(a.iconHash)) {
                    a.description = map.get(a.iconHash);
                    a.revealed = true;
                    revealed++;
                }
            });
            status.textContent = `Revealed ${revealed}/${hiddenCount} hidden descriptions from SteamDB`;
        } catch (err) {
            console.warn('SteamDB lookup failed:', err);
            status.textContent = 'SteamDB lookup failed — keeping hidden achievements as placeholders';
        }
    }

    function formatDescription(a) {
        // Three cases: visible from Steam, revealed via SteamDB, or still hidden.
        if (!a.isHidden) return a.description || '(no description)';
        if (a.revealed) return `${a.description}  [hidden: revealed via SteamDB]`;
        return '[hidden: description not shown by Steam]';
    }

    function buildAchievementsTxt(gameName, achievements) {
        const lines = [
            `Game: ${gameName}`,
            `Source: ${location.href}`,
            `Achievement count: ${achievements.length}`,
            '',
        ];
        achievements.forEach((a, i) => {
            lines.push(`${i + 1}. ${a.name}`);
            lines.push(`   ${formatDescription(a)}`);
            lines.push('');
        });
        return lines.join('\n');
    }

    function pickIconFilenames(achievements) {
        // Use the achievement name as the icon filename. If two achievements share a name
        // (rare but possible), suffix the later ones with _2, _3, etc. Returns one entry per
        // achievement: { base, originalExt } — caller composes the actual paths.
        const seen = new Map();
        return achievements.map((a) => {
            const ext = (a.iconUrl.match(/\.(jpg|jpeg|png|gif|webp)(\?|$)/i) || [, 'jpg'])[1];
            const baseName = sanitizeFilename(a.name);
            const count = (seen.get(baseName) || 0) + 1;
            seen.set(baseName, count);
            const suffix = count === 1 ? '' : `_${count}`;
            return { base: `${baseName}${suffix}`, originalExt: ext.toLowerCase() };
        });
    }

    function gmDownload(opts) {
        // GM_download is callback-based; wrap it in a Promise so we can await sequentially.
        return new Promise((resolve, reject) => {
            GM_download({
                ...opts,
                onload: resolve,
                onerror: (err) => reject(err),
                ontimeout: () => reject(new Error('timeout')),
            });
        });
    }

    function fetchAsBlob(url) {
        // Fetch the image bytes ourselves so we can both download them and feed them into a canvas.
        // Routing through GM_xmlhttpRequest avoids any canvas-tainting issues, since the blob URL
        // we generate is same-origin from the page's perspective.
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url,
                responseType: 'blob',
                onload: (res) => {
                    if (res.status >= 200 && res.status < 300) resolve(res.response);
                    else reject(new Error(`HTTP ${res.status} for ${url}`));
                },
                onerror: () => reject(new Error('network error')),
                ontimeout: () => reject(new Error('timeout')),
            });
        });
    }

    function loadImage(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('image decode failed'));
            img.src = src;
        });
    }

    async function upscaleBlob(srcBlob, targetSize) {
        // Browser canvas with high-quality smoothing = bicubic-ish resampling. Not a magic
        // AI upscaler, but it produces a clean smooth result from the 64x64 source.
        const srcUrl = URL.createObjectURL(srcBlob);
        try {
            const img = await loadImage(srcUrl);
            const canvas = document.createElement('canvas');
            canvas.width = targetSize;
            canvas.height = targetSize;
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(img, 0, 0, targetSize, targetSize);
            return await new Promise((resolve, reject) => {
                canvas.toBlob(
                    (b) => (b ? resolve(b) : reject(new Error('canvas toBlob failed'))),
                    'image/png',
                );
            });
        } finally {
            URL.revokeObjectURL(srcUrl);
        }
    }

    async function downloadAll(button) {
        const gameName = getGameName();
        const folder = sanitizeFilename(gameName);
        const appId = getAppId();
        const achievements = getAchievements();

        if (achievements.length === 0) {
            button.textContent = 'No achievements found on this page';
            return;
        }

        button.disabled = true;
        const status = document.createElement('span');
        status.style.marginLeft = '10px';
        status.style.color = '#a4d007';
        button.after(status);

        // Reveal hidden descriptions first so they make it into the .txt file.
        await revealHidden(achievements, appId, status);

        const iconFilenames = pickIconFilenames(achievements);
        const txt = buildAchievementsTxt(gameName, achievements);

        // Build a blob URL for the .txt so GM_download can save it like any other file.
        const txtBlob = new Blob([txt], { type: 'text/plain;charset=utf-8' });
        const txtUrl = URL.createObjectURL(txtBlob);

        const blobUrlsToRevoke = [];
        try {
            status.textContent = 'Saving achievements.txt…';
            await gmDownload({ url: txtUrl, name: `${folder}/achievements.txt` });

            const smallDir = `${folder}/icons_64`;
            const bigDir = `${folder}/icons_${UPSCALE_SIZE}`;

            for (let i = 0; i < achievements.length; i++) {
                const a = achievements[i];
                const { base, originalExt } = iconFilenames[i];
                status.textContent = `Downloading icons ${i + 1}/${achievements.length}…`;

                try {
                    // Fetch the icon once, then save both versions from the same bytes.
                    const originalBlob = await fetchAsBlob(a.iconUrl);
                    const originalUrl = URL.createObjectURL(originalBlob);
                    blobUrlsToRevoke.push(originalUrl);

                    await gmDownload({
                        url: originalUrl,
                        name: `${smallDir}/${base}.${originalExt}`,
                    });

                    if (UPSCALE_SIZE > 0) {
                        const upscaledBlob = await upscaleBlob(originalBlob, UPSCALE_SIZE);
                        const upscaledUrl = URL.createObjectURL(upscaledBlob);
                        blobUrlsToRevoke.push(upscaledUrl);
                        await gmDownload({
                            url: upscaledUrl,
                            name: `${bigDir}/${base}.png`,
                        });
                    }
                } catch (err) {
                    console.warn('Icon failed:', a.name, err);
                }
            }

            status.textContent = `Done — saved to Downloads/${folder}/`;
            status.style.color = '#a4d007';
        } catch (err) {
            console.error(err);
            status.textContent = 'Download failed — check the console';
            status.style.color = '#e24c4c';
        } finally {
            URL.revokeObjectURL(txtUrl);
            blobUrlsToRevoke.forEach(URL.revokeObjectURL);
            button.disabled = false;
        }
    }

    function injectButton() {
        // Place the button just above the achievement list so it's easy to find.
        // The achievements container has changed selector over time; try a few in order.
        const target =
            document.querySelector('#mainContents') ||
            document.querySelector('.achievement_list') ||
            document.body;

        if (!target || document.getElementById('userscript-dl-achievements-btn')) return;

        const wrap = document.createElement('div');
        wrap.style.cssText = 'margin: 12px 0; padding: 10px; background: #1b2838; border-left: 3px solid #66c0f4;';

        const btn = document.createElement('button');
        btn.id = 'userscript-dl-achievements-btn';
        btn.textContent = '⬇ Download achievements';
        btn.style.cssText = [
            'background: linear-gradient(to bottom, #75b022 5%, #588a1b 95%)',
            'color: #fff',
            'border: none',
            'padding: 8px 16px',
            'font-size: 14px',
            'font-weight: bold',
            'cursor: pointer',
            'border-radius: 2px',
        ].join(';');

        btn.addEventListener('click', () => downloadAll(btn));

        wrap.appendChild(btn);
        target.parentNode.insertBefore(wrap, target);
    }

    injectButton();
})();
