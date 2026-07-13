# Building a Better Anime Wiki: Research and Design Notes

These are the research notes behind Bibliotheca Dantalian, the wiki engine in this repository, and its bundled example wiki: what is wrong with the anime wikis people actually use, what the best wikis on the internet do differently, and how each finding became an engine design decision. Everything here is sourced; the series facts in the example wiki went through an additional adversarial fact-checking pass described below.

## 1. The question

Anime wikis are among the most-visited fan resources on the web, and among the most complained about. The question this project answers: if you started one from zero in 2026, what would you do differently, and can a solo maintainer actually ship it? The methodology was developed and validated against a real, currently airing series, since a mid-run adaptation stress-tests the hardest wiki problems: spoilers, freshness, and naming. The example wiki bundled with the engine is *Lanternfall*, a fictional series written for the demo, framed as mid-airing so it exercises the same problems without shipping anyone's copyrighted material.

## 2. Method

Six parallel research passes, each producing structured claims with a source URL per claim:

1. The wiki hosting landscape and documented migrations away from Fandom.
2. Concrete features and editorial practices from the best wikis (Bulbapedia, minecraft.wiki, poewiki.net, Wookieepedia, large anime wikis, and the structured databases AniList, AniDB, MyAnimeList).
3. Documented reader complaints specific to anime and manga wikis.
4. Stack options for a solo-maintained wiki in 2026.
5. Canonical facts about the series (publication, staff, cast, broadcast).
6. Encyclopedia-grade content detail (characters, terminology, volumes, episodes).

The two series-facts passes were then attacked by six adversarial verification agents across three lenses (official sources, dates and numbers, names and romanization), each instructed to refute claims rather than confirm them. The pass caught real errors that would otherwise have shipped:

- A character named "Keiichi Hamura" (羽村 圭一) on English Wikipedia is actually **Kenichi Hamura** (羽村ケンイチ); the voice actor's own casting announcement and the official cast list agree. English Wikipedia and the Fandom wiki both carry the error.
- English volume 3's release date is December 19, 2023 and volume 4's is April 9, 2024, per the publisher's own product pages. Wikipedia's table is wrong on volume 4, and the wrong date had propagated everywhere downstream.
- The claim that the English dub "launched after a two-week delay" was backwards: it launched same-day and was paused mid-run.
- The dog Daemon's name is the kanji 二狼 (Jiro), not katakana; Wikipedia misassigns the cat's kanji to the dog.
- "24 episodes" is not an official figure; only "two consecutive cours" is. The 24 is corroborated indirectly by the Blu-ray plan (8 volumes x 3 episodes) but the wiki attributes it to press rather than stating it as fact.

The lesson generalizes: **fan wikis and Wikipedia copy each other's errors in a loop, and the only way out is checking primary sources per claim.** That finding shaped the wiki's editorial policy more than any feature idea did.

## 3. The landscape: why the incumbents lose their communities

Fandom hosts the large majority of anime wikis. It is a private-equity-backed ad business (TPG invested in 2018) monetizing volunteer labor, and the documented complaints cluster tightly: autoplay video with sound, popup and redirect ads that make mobile "totally unusable" (Fandom's own community forums), layout-shifting late ads, quizzes and Fan Feed modules injected without editor consent, and features shipped over community objection ([Wikipedia's Fandom article](https://en.wikipedia.org/wiki/Fandom_(website)), [Fandom community threads](https://community.fandom.com/f/p/2972903901495298800)).

The exodus is not hypothetical. Documented migrations, each citing some mix of ads, autoplay, and lost control:

| Wiki | Left for | Year |
| --- | --- | --- |
| Touhou Wiki | self-hosted | 2010 |
| RuneScape Wiki | Weird Gloop (Jagex-funded) | 2018 |
| Yu-Gi-Oh! (Yugipedia) | independent | 2018-2019 |
| JoJo's Bizarre Encyclopedia | jojowiki.com, self-hosted | 2019 |
| Path of Exile Wiki | poewiki.net | 2021 |
| Terraria, Calamity, ARK | wiki.gg | 2022 |
| Zelda Wiki | independent | 2022 |
| Minecraft Wiki, Hollow Knight, Wowpedia, Fallout | minecraft.wiki (Weird Gloop), hollowknight.wiki, warcraft.wiki.gg, fallout.wiki | 2023 |
| League of Legends | Weird Gloop (Riot-backed) | 2024 |
| Warframe, Vocaloid Lyrics Wiki | Weird Gloop; Miraheze | 2025 |
| GTA Wiki, VALORANT | Weird Gloop | 2026 |

Anime-specific note: anime wikis skew toward self-hosting or Miraheze because there is no game publisher to fund a Weird Gloop-style deal, and copyright pressure is an anime-specific migration trigger (the Vocaloid Lyrics Wiki left in 2025 after Fandom staff deleted lyrics unilaterally).

The tax on leaving: Fandom never deletes a forked wiki. The abandoned "zombie" copy keeps the URL and the Google ranking, outranking the maintained fork for years ([Fandom Forking Policy](https://community.fandom.com/wiki/Forking_Policy), [forkfandom.com](https://forkfandom.com/)). Countermeasures exist (Indie Wiki Buddy redirects users across 650+ independent wikis) but the structural conclusion for a new wiki is blunt: **never start on Fandom, because the exit door has a toll booth.**

## 4. What the best wikis get right

The features and practices worth copying, distilled from the strongest exemplars:

- **Structure beats prose.** poewiki.net stores item data in queryable Cargo tables so a correction is one edit, not thousands; AniList exposes its whole database over a keyless GraphQL API. Store facts once, render everywhere.
- **Write the tie-breaker down.** Every healthy wiki has a published, ranked rule for contested names: One Piece Wiki ranks manga > author Q&A > databooks > anime; Bulbapedia ranks trademarked spellings > Hepburn. The specific ranking matters less than that it exists.
- **Spoiler policy is a product decision.** The field splits between per-reader hiding in the markup (AniList's `~!spoiler!~`) and a single bright line with no hiding at all (One Piece Wiki). Most Fandom anime wikis take the second pole and readers hate it (section 5).
- **Stub control happens at creation time.** Jujutsu Kaisen Wiki requires an infobox, opening sentence, and section skeleton before a page may exist. Cheaper than cleanup.
- **Infobox discipline is about constraints.** minecraft.wiki bans key art from infoboxes and mandates comparable renders; that is why its infoboxes read like a database instead of a fan collage.
- **Independence is a feature readers feel.** minecraft.wiki's move bought faster loads, real search, dark mode, and one ad per page, and readers followed.
- **Proportionate citation burden.** Facts visible in the primary work need no footnote; anything out-of-universe does, and fan translations are banned as sources (Chainsaw Man Wiki).

## 5. What anime wiki readers actually complain about

Every complaint below is documented, not hypothesized:

1. **Spoilers by ambush.** The One Piece Wiki's own rules say it "does not hide spoilers or have special markings for them," and its forums carry threads from readers spoiled before starting the series. Infoboxes are the worst offender: a Status: Deceased field spoils at a glance, and the community blur-template hacks do not render on Fandom mobile.
2. **Mobile ads that break reading.** Redirect loops on iOS, autoplay video that cannot be closed, page-yanking late ads. This is the top stated reason communities fork.
3. **Romanization chaos.** Wikis flip between Hepburn, wapuro, and official spellings; TV Tropes maintains an entire catalog of anime name-spelling conflicts. Edit wars follow.
4. **Dub names and dub errors presented as canon.** The Dragon Ball wiki is called unreliable by its own series' biggest fan community for treating dub-only mistakes as fact; the Detective Conan wiki listed invented dub names for characters never in the dub.
5. **Unsourced speculation as fact.** Major character pages with two or three references total.
6. **Stub proliferation.** Fandom's own help pages admit a high stub ratio lowers Google's confidence in the whole wiki.
7. **Staleness mid-season**, and abandoned zombie copies outranking maintained wikis.

## 6. Stack decision

Options compared for a solo maintainer (full notes in the research data): Miraheze (free, ad-free, nonprofit, but a dormancy policy closes idle wikis), wiki.gg (free, ad-supported, application process, games-first), self-hosted MediaWiki (total control, meaningful ops burden and spam fighting), Wiki.js and DokuWiki (closed-editing knowledge bases in practice), Obsidian Publish (subscription, no contributors), and a git-backed static site (GitHub Pages, zero hosting cost, zero attack surface, contributions by pull request).

**Chosen: git-backed static, custom engine.** Rationale:

- The editing model is the real fork in the road. Open-wiki editing needs patrol tooling and spam defense that dwarf a solo maintainer; pull requests give review-before-publish, full history, and structurally zero vandalism. A working precedent exists (the Morrowind Modding Wiki, Quartz on GitHub Pages).
- Static pages make the top reader complaints (ads, weight, mobile breakage) impossible by construction rather than by policy.
- A custom engine over an off-the-shelf SSG because the wiki mechanics that matter here (scoped spoiler blocks, red links, backlinks, category pages, infobox front matter) are the product, and owning them in ~600 lines of stdlib Python beats bending a theme. Everything series-specific (name, spoiler scopes, page types, nav, footer) lives in a per-wiki `wiki.json`, so one engine serves any fandom.
- GitHub's built-in repo wiki was rejected: robots.txt blocks it from search indexing below 500 stars.
- If the community outgrows pull requests, the exit path is Miraheze or self-hosted MediaWiki with Cargo, and the content is already portable Markdown in git.

## 7. Design decisions mapped to documented gaps

| Documented gap | Design answer in the engine and example |
| --- | --- |
| Spoilers by ambush; blur hacks broken on mobile | Scoped spoiler blocks (anime / manga) in the markup, hidden by default, opt-in via a persistent header menu plus per-block reveal; works identically on mobile because it is plain HTML and CSS |
| Infobox spoilers | Editorial rule: infoboxes and intros must be safe at premise level; late-series facts go in scoped blocks in the body |
| Romanization chaos | Published naming policy: the official English release's spellings win, Japanese and romaji recorded once in the infobox, macron-less style matching that release |
| Dub errors as canon | Sourcing policy whitelists official sites, publisher, and trade press; adaptation-only naming is labeled with its source |
| Unsourced speculation | Every page carries a References section; the two verified-wrong "facts" found during research (a character name, a volume date) are corrected with primary sources cited |
| Stub proliferation | No-stub rule at creation time; missing pages render as amber red links that double as the contributor to-do list, and the build prints a red-link report |
| Mobile ads and page weight | No ads, no trackers, no external requests at all; self-contained static pages |
| Staleness mid-season | A "coverage current through episode N / volume N" status line on the main page, updated with each content change |
| Zombie-wiki SEO trap | Independent hosting from day one; content in git, portable forever |
| Copyright takedown risk (anime-specific) | No hosted copyrighted images at all; pages link to official sources for visuals |

## 8. What a bigger wiki would add

Honest limits of this build, and the roadmap if it grew a community:

- **Progress-gated spoilers** ("I am at episode 8") rather than two coarse scopes. The block markup already carries scope data; a finer gate is a client-side enhancement.
- **A structured data layer** (JSON per character/episode rendering into infoboxes and lists) for one-edit corrections, Cargo-style.
- **A name registry** with every alias and spelling variant as searchable, cited data.
- **Open editing**, if PR friction proves too high: migrate to Miraheze or self-hosted MediaWiki; Markdown-to-wikitext conversion is the known cost.
- **An API** in the AniList mold, which for a static site can be as simple as publishing the JSON data layer.

## 9. Primary sources

Landscape and practices: [Fandom (Wikipedia)](https://en.wikipedia.org/wiki/Fandom_(website)), [Fandom Forking Policy](https://community.fandom.com/wiki/Forking_Policy), [minecraft.wiki move discussion](https://minecraft.wiki/w/Minecraft_Wiki:Moving_from_Fandom), [JoJo Wiki: Leaving Fandom](https://jojowiki.com/JoJo_Wiki:Leaving_Fandom), [RuneScape: Leaving Wikia](https://runescape.wiki/w/Forum:Leaving_Wikia), [Vocaloid Lyrics migration](https://vocaloidlyrics.miraheze.org/wiki/Vocaloid_Lyrics_Wiki:Fandom_Migration), [One Piece Wiki spoiler rules](https://onepiece.fandom.com/wiki/One_Piece_Wiki:Guidebook/Spoiler_Rules), [Wookieepedia sourcing](https://starwars.fandom.com/wiki/Wookieepedia:Sourcing), [Bulbapedia romanization](https://bulbapedia.bulbagarden.net/wiki/Bulbapedia:Manual_of_style/Romanization), [AniDB creq system](https://wiki.anidb.net/Creq), [AniList API docs](https://docs.anilist.co/), [PoE wiki tooling](https://github.com/Project-Path-of-Exile-Wiki/wiki), [Miraheze content policy](https://meta.miraheze.org/wiki/Content_Policy), [wiki.gg wiki creation](https://support.wiki.gg/wiki/Creating_a_new_wiki), [Morrowind Modding Wiki](https://github.com/morrowind-modding/morrowind-modding.github.io).

Series facts for the validation build: the series' official anime site, the English publisher's series and product pages, the production company's lineup page, and Anime News Network's announcement chain (July 2025 through June 2026), with per-claim citations carried on each page. The published example replaces that content with the fictional *Lanternfall*, so those citations do not appear in this repo; the sourcing discipline they proved out is written into the example's editorial policy instead.
