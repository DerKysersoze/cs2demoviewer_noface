# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.2.0] - 2026-10-26

Front page redesign (mockup option A): the plain “Previous Demos” text list is now a match-library card grid, and the big centered drop zone is a slim upload strip above it. The Results page is reorganised into four tabs — Overview · Rounds · Aim · Players — with the aim breakdown inline and a new per-player dossier (mockup option A + the “player dossier” layout). And the Loadout page now shows **both sides at once**: each player's CT and T loadouts side by side, rebuilt from the demo's purchase stream instead of a single end-of-match snapshot. The Rounds tab is reworked around the 2D map — it is now the tab's main content (always-on companion, ~80/20 split with the kill feed as a compact left rail), and the VIDEO SYNC jump card is removed.

### Added

- **Per-side (CT & T) loadouts** — the Loadout page shows both sides at once: each player card carries a **CT Side** and a **T Side** panel, each with its own agent + weapon grid (the old T/CT toggle is gone; panels stack below 900 px). A weapon used on both sides appears in both panels with a “both sides” badge.
  - **Purchase-stream extraction** — `extract_cosmetics` is rebuilt around `item_pickup` events inside each round's buy window (15 s + 1 s slack, scaled by the demo's tickrate), with round boundaries from `cs_pre_restart` and the side-at-purchase from the `player_team` switch timeline (initial side inferred when a player buys before their first logged switch, cross-checked against side-specific items in the cluster). Mid-round drop pickups fall outside the buy window and are excluded.
  - **Paint join + union safety** — skin · seed · wear · custom name are joined from `parse_skins()` by (steamid, def_index); any painted item missing from the purchase stream is kept and assigned by weapon class (CT / T / both), so no data is lost versus the old snapshot parser. StatTrak still comes from the `parse_ticks` pass.
  - **Legacy fallback** — when the purchase events are unavailable (older demos), the extractor falls back to the previous parse_skins + weapon_fire behaviour, so nothing regresses.
  - **Gear filtered out of loadouts** — grenades + C4 (defindices 43–49) and armor/defuse kit (50/51/55) no longer appear as loadout rows; knives (incl. base knives) and gloves stay.
  - **`ct_agent` / `t_agent` in the Loadout API** — `/api/demos/<id>/loadout` players now carry `ct_agent`/`t_agent` (a “both”-class agent goes to both) instead of a single last-wins `agent` key; skin rows keep their per-row `side` (CT / T / both) and the frontend filters by side.
  - **Library reparsed** — every stored demo went through `POST /api/demos/<id>/reparse` after the change; on the reference demo all 10 players now have both sides populated (previously only one side was stored per player).
  - **Two new API tests** — `test_loadout_api_per_side_shape` (ct_agent/t_agent keys, no legacy `agent`, side ∈ CT/T/both) and `test_loadout_api_both_sides_populated` (at least one player has CT and T rows; skips cleanly on an empty library).

- **Four-tab Results page** (`/results/<demoId>`) — a sticky tab bar under the match header (Overview is the default):
  - **Overview** — the full-match stats table plus the highlights; clicking a highlight selects its round **and switches to the Rounds tab** so you land on the story.
  - **Rounds** — round chips, then the round on the 2D map as the tab's main content: an always-on companion (right column, ~80%) with floor tabs, scrubber, static zoom and an **Open fullscreen map** CTA, with the round story (kill feed) as a compact left rail (~20%).
  - **Aim** — the full aim breakdown inline: player switcher, summary stats, hit-location bars and the per-weapon table. No page hop needed.
  - **Players** — a CT/T team rail (sorted by kills, K/D · DMG · HS% per row) that doubles as navigation; the dossier shows a player's match stats, aim summary, hit-location breakdown and per-weapon table in one place, with a **TOP PERFORMER** badge on the match's best player (also the default selection). Rail rows are plain-text buttons (an anchor inside a button is invalid HTML); the dossier head name carries the Steam profile link.
- **Shared `AimBreakdown` component** — extracted from the `/aim` page and reused by the Results Aim tab; `AimPage` is now a thin wrapper (199 → 68 lines).
- **Players-tab screenshots** — `screenshots/results-players.png` and `results-players-dark.png`.

- **Match library grid on the front page** — one card per demo: map image (served from `maps/` via the existing `/api/map_image/<map>` endpoint), final score with winner-coloured badge (CT blue / T amber), rounds · duration · date. Click the card (or Enter/Space — cards are keyboard-focusable) to open its Results page.
- **Hover quick stats per card** — a panel slides up over the map image showing the top performer (side dot · name · kills · K/D), rounds and duration, and a **Results →** CTA; the per-card delete button appears on hover/focus.
- **Richer `/api/demos` list payload** — each entry now also carries `ct_wins/t_wins`, `ct_team/t_team`, `total_rounds`, `duration` and the match top performer (`mvp_name/mvp_team/mvp_kills/mvp_kd`), resolved with a single `ROW_NUMBER()` join over `demo_scoreboard` (highest kills, K/D tiebreak) — no extra request per demo. Backward compatible (fields added, not changed).

### Changed

- **Rounds tab reworked — the 2D map is the main content** — the expandable “round on the 2D map” band and the VIDEO SYNC jump card (demo_play command, position readout, per-round jump grid) are both gone. The tab is now a split: the round story (kill feed) is a compact left rail (~20%) and an **always-on 2D map companion** is the right column (~80%) — nothing to expand, round ticks load immediately. The companion head carries the round label, the floor badge, the per-floor player distribution for the whole round and the **Open fullscreen map** link (deep-linking `/map/<id>?round=N` for the current round); the body is the shared replay stage filling the column — a new `wide` variant of `MapReplayStage` drops the 520 px cap. Chips and ←/→ still select rounds, and highlights still jump straight to the tab. Below 900 px the split stacks with the map first. Dead CSS (`.band*`, `.panel*`, `.jump*`, `.storyCol`, `.aside`) deleted and `JumpPanel.jsx` removed.
- **Upload area** — the big centered drop zone is now a slim strip above the library; dropping, clicking the strip, or **Choose files** all work. The **Choose files** button is now actually wired to the file picker (it previously did nothing). Single-file → Results and multi-file → queue flows are unchanged.
- **`DemoHistory` row list → card grid** — new `DemoCard` component; the old `demoRow`/`demoDel` styles are gone. Cards handle missing data gracefully (no score, no scoreboard, unknown map image).
- **Aim breakdown CTA out of the Results header** — the breakdown lives in the Aim tab (and per-player in the Players dossier). The `/aim/<demoId>` route is **kept** for shareable links and deep links.
- **Loadout CTA moved from the Results header to the right end of the sticky tab bar** — micro-label “Loadout →”, same voice as the tabs (kept outside `role=tablist`, since a link is not a tab); the header now carries ← Home only.

### Fixed

- **Loadout API agent overwrite** — the `/loadout` endpoint assigned every agent row to one `player.agent` slot (last row won), so a player with both a CT and a T agent kept only one. Agents now split into `ct_agent`/`t_agent` by row side.
- **Aim breakdown default selection** — the extracted shared component started with no player selected (“Select a player…”) on both the Aim tab and the `/aim` page; it now defaults to the first player, matching the pre-refactor `/aim` page.
- **Button text colour in dark mode** — bare `<button>`s (e.g. the Players rail names and kill counts) fell back to the UA `buttontext` (black) and were unreadable on the dark theme. The global reset now sets `color: inherit` (matching the existing `a { color: inherit }` convention), so all button text tracks the ink token; light-mode ink is `#000`, so light mode is pixel-identical. `results-players-dark.png` re-shot.
- **Playback control buttons (▶ + − ⌂)** — the base `.btn` carried no background, no colour and a transparent border, so the playback bar's buttons fell back to the UA buttonface: white boxes with white glyphs in dark mode. The base `.btn` now carries the paper background, ink border and ink text (the `btn-primary` / `btn-ghost` / `btn-danger` variants already override these). `results-rounds.png` / `results-rounds-dark.png` re-shot.

### Testing

- **52/52 tests pass** in ~22 s — the `/api/demos` list tests pass against the extended shape; the two new loadout tests pin the per-side API shape and both-sides population; `/aim/<id>` still resolves via the SPA fallback.
- Frontend build and lint clean; verified live on the Flask server with a scripted browser pass (21/21 checks): 4 tabs render and switch (computed-style verified), Overview stats + highlights, highlight click lands on Rounds, Rounds chips/story/map companion, Aim tab (10 players · 7 stats · hit bars · weapon table), Players dossier (10 rail rows, top-performer default + badge, steam link on the name, rail switch updates the dossier), `/aim/<id>` regression, light + dark, zero page errors.
- Re-worked Rounds tab scripted pass (30/30 checks, light + dark): companion visible **without any expand click**, canvas wide (>520 px), story rail left of the map with a 20/80 width ratio (measured 0.200), no VIDEO SYNC text, FLOORS badge + per-floor distribution, chip click updates the head label and the CTA href (`?round=4`), play/pause toggles, a highlight click lands on the Rounds tab with the companion still mounted, zero page errors.
- Loadout page scripted pass (11/11 checks, light + dark): 10 player cards × 2 side panels (CT/T labels), no legacy toggle, per-side agents + weapons verified against the reference demo (Keyser Soze: T agent Getaway Sally, T side Glock/AK/Galil/MAC-10, CT side AWP/M4A4/MP9/SSG 08), all panel images loaded, no empty side panels, player-name contrast ≥ 4.5 in dark mode, zero page errors.
- `screenshots/upload.png` refreshed to the new front page; dark-mode shots added (`results-dark.png`, `map-dark.png`); `results.png`/`results-dark.png` re-shot to the tabbed layout, `results-players.png`/`results-players-dark.png` added, `aim-breakdown.png` re-shot (default player selected), **`loadout.png` re-shot to the two-panel layout**, `results-rounds.png`/`results-rounds-dark.png` added for the reworked Rounds tab and re-shot after the playback-button fix (the old `results-map-band*.png` shots are deleted) — the README now shows light and dark variants of the Results page (Overview + Players tabs), the Rounds tab and the map page.

## [2.1.0] - 2026-10-26

Route cleanup and two dedicated pages: the Viewer is gone — the 2D replay moves to a full-page `/map/<demoId>` route with a live player-details panel, and the aim breakdown gets its own `/aim/<demoId>` page. The Results page is now the single entry point to a match.

### Added

- **Dedicated 2D map page** (`/map/<demoId>`) — the Viewer's map tab, promoted to a first-class route:
  - Full free camera (wheel zoom to cursor, drag-pan, 0.25×–6×) with floor tabs and the full scrubber.
  - **Live player-details panel** (left): per-frame HP, the **weapon held in the current frame**, full-match K/A/D · DMG · HS%, armor/helmet indicators; click a row to hide that player on the map.
  - **Round event feed** (right): buys, utility (smoke / flash / molotov) and kills up to the current tick.
  - Round pill strip with shareable deep links — the Results page's per-round **View on map** CTA lands directly on `/map/<demoId>?round=N`.
- **Dedicated aim breakdown page** (`/aim/<demoId>`) — the Viewer's aim tab as a standalone page: sticky player list, summary stats (hits, damage, avg damage, HS-hit %, KAST, shots, accuracy), hit-location bars and the per-weapon sortable table.
- **Per-tick weapon names in the replay data** — each player frame now carries the weapon held at that tick (`w`, e.g. `M4A1-S`, `Butterfly Knife`); `null` when dead or unknown (~74% coverage on the reference demo, blob grows ~1.7%). Demos parsed before this release can be upgraded via `POST /api/demos/<id>/reparse`.
- **Results header CTAs** — Aim breakdown (primary) · Loadout · Home; the 2D map page is reached via the expandable map band and the per-round **View on map** buttons.
- **Steam community profile links on the Results page** — player names in the full-match stats table, the per-round kill feed (killers, victims and assists) and the highlights cards now link to each player's Steam profile (`steamcommunity.com/profiles/<steamid64>`, new tab). IDs come from the scoreboard — the one table that carries them; names the parser couldn't resolve render as plain text. Also fixed a duplicated "round N" in highlight card text.
- **`test_removed_viewer_route_returns_404`** — regression guard: the removed `/viewer/<id>` route must no longer resolve to the SPA.

### Changed

- **Navigation re-centered on Results** — a finished upload now lands on the Results page; demo-history rows link to Results; Loadout's back button returns to Results; per-round **View on map** deep-links to the map page.
- **SPA route set** — Flask resolves `/results/<id>`, `/map/<id>`, `/aim/<id>`, `/loadout/<id>` and `/admin` on hard refresh (`/viewer/<id>` is gone).
- **Round selection on the Results and Map pages is derived state** — the "snap to a valid round" fallback no longer runs through a `setState`-in-effect loop (fewer re-renders, lint-clean).

### Removed

- **The Viewer page** — `/viewer/<id>` now 404s. Its 2D Replay and Aim tabs live on as the new `/map` and `/aim` pages (gaining the player panel and event feed); its never-rendered extras (swag breakdown, kill-feed widget, legacy single-map view, standalone scoreboard, timeline) are deleted along with the `pages/Viewer/` folder (10 files).
- **`store/demoStore.js`** and the empty `store/` folder — zero importers after the Viewer's removal.
- **Unused dependencies** — `zustand` and `recharts` sat in `package.json` with no usages; removed (~42 packages pruned from `node_modules`).
- **Lint debt** — seven `no-unused-vars` / `set-state-in-effect` errors across `DotText`, `MicroLabel`, `Upload`, the admin `ResultsTable` and the two new pages; `npm run lint` is now fully clean.

### Notes

- **Ammo is not available in CS2 demo data** — 14 candidate `player` properties were probed in demoparser2 0.41.1 and none exposes a reliable current-mag / reserve value, so the player panel shows weapon + HP + stats instead (documented in the parser docstring).

### Testing

- **50/50 tests pass** in ~26 s (the 48 fast + 1 slow suite, with the SPA-route test updated for the new route set and one new regression test for the removed `/viewer` route).
- **The test suite no longer pins a demo id** — the canonical regression demo is now the most recent demo in the library that has stored replay data (map/round count asserted against that demo's own records, not literals), and demo-dependent tests skip cleanly when the library is empty. Deleting and re-importing demos no longer breaks the suite.
- Frontend build and lint are clean; the production bundle in `static_react/` is verified live on the Flask server.

## [2.0.0] - 2026-10-26

Major rewrite of the parsing engine and viewer: a new match results page,
multi-floor 2D replay, shot tracers, async parsing, a 48-test suite, and a
~10× speedup of tick extraction.

### Added

- **Match results page** (`/results/<demoId>`) — a full match review:
  - Map name, final score, winner badge, round count and duration.
  - Full-match sortable player table (K / D / A / K/D / DMG / HS%), grouped by team.
  - Round chip strip (CT / T / draw chips with round-end reason icons) with keyboard ←/→ navigation.
  - Per-round story: winner, end reason, start time and duration, and the full kill feed with weapons, HS/smoke/wall/no-scope flags and assists.
  - Jump panel with the CS2 `demo_play` console command and per-round timestamps.
  - Auto-detected highlights: multi-kills, kill streaks, clutches, bomb/defuse moments and top-damage players — each deep-linking to its round.
  - Entry points: a **Results** button in the Viewer header and a **Results →** link on every demo in the Upload page history.
- **Multi-floor 2D replay** — maps with multiple floors (e.g. `de_nuke`'s Lower, `de_palais` with 3 floors, `de_train`, `de_vertigo`, `ar_baggage`) now replay floor-by-floor:
  - Floor tabs with **live per-frame player counts**; switching floors swaps the radar image and shows only the players on that floor in the current frame (assigned by altitude).
  - Per-floor radar images served from the bundled `maps/` folder (`/api/map_image/<map>/<floor>`).
  - Player altitude (`z`) is now parsed into the tick data (was available but previously dropped).
  - Maps without multiple floors keep the exact single-floor experience.
- **"Round on the 2D map" band on the Results page** — an expandable band under the kill feed: collapsed it shows the radar, the round label, a floors badge and per-floor player counts for that round; expanding opens the full replay (floor tabs, playback, scrubber) without leaving the page.
- **Shared replay stage** (`MapReplayStage`) — one replay core used by both the Viewer tab and the Results band: playback (play/pause, 0.5–4× speed), zoom/pan, a scrubber with **kill markers (yellow = headshot)** and the **bomb plant/defuse region**, plus a download fallback for maps without local radar images.
- **2D replay data** — per-round player positions, grenade throws, buy events and shot tracers are parsed and persisted, so replays survive server restarts without the original `.dem`.
- **Shot tracers** in the 2D replay (persisted in a new `shots_data` blob).
- **Async parse jobs** — `POST /api/parse` now returns `202` immediately and parses in the background; the Upload queue shows a "Parsing…" state. Long uploads no longer block the request for 40–60 s.
- **Reparse endpoint** — `POST /api/demos/<id>/reparse` re-runs the parser over a stored demo to upgrade data saved under the old parser.
- **Round tick bounds** — each round now stores `start_tick` / `end_tick`, powering kill-feed timestamps, "starts at MM:SS" labels and the jump list.
- **`pytest` test suite** — 48 tests covering the parser (header, rounds, kills, damages, ticks, shots, per-tick kill attribution), the API, SPA serving, job registry, cache semantics and a **golden-blob equivalence guard** that fails the suite if replay data ever silently changes.
- **`.gitignore` hygiene** — runtime demo storage and vendored reference sources are no longer trackable.

### Changed

- **Parser rewritten on `demoparser2`** (`parser_foundation.py`) — all parsing (header, rounds, kills, damages, ticks, shots) no longer goes through awpy. Awpy remains only a last-resort fallback for map bounds when no local radar data exists.
- **Map data is now txt-first** — bounds and floors come from the bundled HLTV overview files in `maps/` (27 maps, all with radar images), with awpy as fallback.
- **Flask serves the React SPA** — `/`, `/viewer/<id>`, `/results/<id>`, `/loadout/<id>` and `/admin` all resolve on hard refresh; unknown non-API paths return a JSON 404.
- **Viewer deep links** — `?tab=…` selects the initial tab, so "View on map" lands directly on the 2D Replay tab.
- **Results map band is a static map** — the band's radar stays centered and in place; zoom (1×–4×) scales around the center without drifting, and the page scrolls normally over the map. The Viewer tab keeps the full free camera (scroll-to-cursor zoom + drag-pan).
- **`uploaded_at`** is stored as explicit ISO-8601 (unambiguous for `new Date()`, no deprecation warnings).
- **Session cache is a true LRU** — cache hits refresh recency, so an actively-used session is no longer the first one evicted.
- **Upload limit is 512 MB** per demo file.

### Fixed

- Kill **round numbers** were all `0` — now correct (1…N).
- Kill **victims** were all `?` — now real names; **assists and death counts** were 0 — now populated.
- Kill **teams** were guessed from "victim is on the losing side" — wrong for timer/defuse endings and friendly fire; now resolved from each player's actual team at the kill tick (verified against friendly-fire demos).
- **Scoreboard** had phantom rows (including a `?` row for bomb kills) — now exactly the 10 real players.
- **Accuracy / KAST** were empty or implausibly low — now in sensible ranges.
- **Header** showed `?` duration and an impossible score split — now correct.
- **Delete endpoint** orphaned `.dem` files — now removes the file and all DB rows.
- **Phantom empty demos** — non-CS2 files used to be saved as 0-round demos; they are now rejected with a clear error.
- **Zoom drift** — the map drifted on every zoom step (a double-applied pan correction under React StrictMode); zoom/pan math is now pure and verified to keep the image centered across arbitrary zoom sequences.
- `requirements.txt` was missing `demoparser2` — added.

### Removed

- 603 MB of duplicate `.dem` files (verified byte-identical to the stored canonical demo).
- A duplicate `screenshots_claudedemo/` folder (byte-identical copies of `screenshots/`).
- Dead code: the legacy `cs2_demo_viewer.py`, Jinja template routes, the `/api/probe_bullets` debug endpoint, and the redundant root `package.json`.
- A stale March log file.

### Performance

- **`extract_ticks` ~10× faster** — the per-row loop is now vectorised with numpy with identical output (locked in by the golden test): **7.54 s → ~0.7 s** on the reference de_nuke demo; full `parse_demo` ~14.9 s → ~12.9 s.
- Parse jobs run in the background, so the upload response is immediate instead of blocking for the full parse time.

### Testing

- **48/48 tests pass** in ~15–20 s, including the full `parse_demo` pipeline and the golden-blob replay-equivalence guard.
- Frontend build and lint are clean on all changed files.
