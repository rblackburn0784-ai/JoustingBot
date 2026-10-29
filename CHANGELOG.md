# Changelog

## v2.9.3 — Graphical Fine Tuning

- Raised mounts ~36px relative to original background, scaled knights to 90% while retaining a consistent seated foot anchor.
- Raised the centre barrier and changed layering to blue/far → barrier → red/near.
- Split original supplied crowd strip into three clipped grandstand positions.
- Anchored raised and lowered lance sprites to each rider's grip point with correct handed orientation.
- Removed the central PASS/phase plaque, retained score strip and lower commentary strip.
- Introduced optional scene_layout.json to fine-tune visuals to locally installed art without Python edits, with safe validated fallbacks.
- Updated broadcast version label to v2.9.3. Combat outcomes, points and pass playback logic unaffected; added synthetic visual regression tests.

## v2.9.2f — Equipped Title Banners

- Added safe explicit mapping from all 30 saved title IDs to original transparent title-banner PNGs, including the marshal_favourite filename exception.
- Reused the already persisted, earned-only per-guild/title selection so equipped banner visuals cannot unlock unearned titles or drift from the equipped title.
- Added illustrated Your Title Collection display: equipped standard, selected unlocked candidate preview, locked candidate state and immediate refresh after dropdown/equip/unequip.
- Added a small far-end standard overlay to all six arena menu previews and challenge selection screens. Arena scoring, effects and live animations remain unchanged.
- Added a generated neutral royal-blue standard for unequipped titles or missing PNGs; menu remains usable without the optional art files.
- Added v2.9.2f banner art distribution as a separate ZIP with validated 30 original PNGs, installation instructions and regression tests.

## v2.9.2e — Tournament Hall, History & Trophy Cabinet Visuals

- Added the user-supplied Tournament Hall (`tournament.png`), Tournament History (`tournament_history.png`) and Trophy Cabinet (`trophy_cabinet.png`) as image-backed private Discord menu screens.
- Fixed `/menu → Tournaments → History` to navigate to a dedicated History page rather than keeping Tournament Hub buttons under history results.
- Added image-aware Refresh History, Tournament Menu and Main Menu navigation. All cabinet achievements, tournament titles, career medals and equip-title controls remain intact.
- Updated `/tournament history`, `/tournament cabinet`, `/tournament achievements` and persistent public tournament History/Trophy buttons to show private illustrated menus.
- Deferred public-panel/slash interactions before image rendering to avoid Discord interaction expiry; reused the existing threaded renderer and graceful text-only fallback.
- Left the tournament engine, brackets, player records, equipment, gold, match simulations and admin permissions unchanged; added regression tests.

## v0.9.2d — Interactive Knight, Horse & Shop Screens

- Added a full-screen 1280×720 illustrated menu renderer for seven player-supplied backgrounds: Shop, Knight, Horse (White, Bay, Black, Grey, Chestnut). Local art is loaded from `assets/ui/` and resized only in-memory for Discord.
- Added a separate Shop browsing/purchase flow; buying still uses the existing eligibility, wallet, gold balance and unlock functions and **never auto-equips**.
- Knight and Horse equipment pickers now show the correct illustrated base screen with current or selected equipment labels in empty gear panels. Unsupported equipment categories remain clearly marked coming soon.
- All illustrated screens edit the same private Discord message after a fast initial defer. Selecting a different horse or item refreshes the picture without posting duplicate images; missing images revert safely to text.
- Added player-accessible, persistent cosmetic horse coat selection independent of horse breed, bond, stats, progression, combat or purchased gear.
- Added seven-image installer with integrity checks, asset naming guide and offline tests covering five coat mappings, ownership separation, fallbacks and shop purchases.
- Kept v0.9.2c training, tournament permission checks, v0.9.2b live match animations, and all existing save formats. No new equipment stat models or gear overlays in this release.

---

## v0.9.2c — Training Yard & Tournament Controls

- Restored `/joust train`, expanding the original four character-driven NPCs (Osric, Beren, Elis and Maud) into a twelve-level roster with distinct mounted statistics, tactics, horses and gear.
- Added `/joust trainers`, `/joust training_stats` and an accessible Training Yard menu/drop-down so players can choose their training opponent.
- Training battles use the v0.9.2b one-screen live sprite broadcast and deterministic combat, with independently selectable player style and standard arena selection.
- Each completed training bout grants three cosmetic Training XP, up to 30 XP per UTC day and with a per-user/server 120-second cooldown. Training grants **no gold, competitive record, titles, prestige or tournament credit**; XP is derived from saved, unique training match IDs.
- Real player injuries now also arise from recorded training impacts and are visible in existing injury/healing screens; NPCs cannot receive stored injuries.
- Clarified and enforced tournament creation as Manage Server-only at the slash command, menu, modal and interaction handler; public tournament registration remains open.
- Added release regression tests covering NPC tiers, rewards, daily cap, guild isolation, risks, menu visibility and tournament admin permissions.

---

## v0.9.2b — Live Match Broadcast Flow

- Replaced the multi-attachment sprite recap with **one evolving Discord broadcast message**: one chronological animation per real jousting pass, changed in place between rounds.
- Added Prep → Gallop → Lance Ready → Collision → Outcome phases with sprite-pose progression, authentic misses/refusals/falls and delayed outcome scoring.
- Added off-thread pass render/prefetch and short, configurable pauses between rounds; GIFs play once and hold on each pass's result.
- Final card replaces the same live graphic only after all actual passes, retaining the existing score, injuries, tactical recap and match ID.
- Added optional commentary ticker, reduced-motion per-pass PNGs, upload-size fallback, temporary file cleanup and safe fallback to v0.9.2 if art is unavailable.
- No changes to combat RNG, progression, rewards or persistent journals; tests verify single-message delivery and no premature results.

---

## v0.9.2a — Dynamic Sprite Animation Engine

- Integrated real-time sprite composition into the existing recorded-once v0.9.2 match broadcast. Tactical combat, tournaments, injuries, rewards and logs are unchanged.
- Added layered arena, crowd, horse, directional knight, lance, shield, particle and foreground barrier graphics with true pass-driven motion.
- Reads numbered transparent PNG frames from the `assets/jousting` art overlay. Detects the red/blue knight left/right sprite sets and five coat-colour horse sets. Preview sheets are excluded.
- Implements cinematic Approach, Charge, Impact and Aftermath, including horse refusals/slips, lance breaks, heavy hits, falls and appropriate crowd reactions.
- Renders GIF animations on demand from PNG frames; small bouts fit in one clip, longer bouts use sequential pass clips to respect the Discord upload limit.
- Graphics are presentation only, executed off the Discord event loop. The existing final match scorecard is always sent; missing art and failed sprite uploads fall back to the v0.9.2 stage broadcaster.
- Added editable visual breed-to-coat mapping, configurable `JOUST_SPRITE_ENABLED` switch and offline regression tests for sprite path selection, deterministic source results and replay fallbacks.
- The 581 original PNG files are delivered in a separate art overlay ZIP rather than GitHub code commits. The old local installer is no longer needed for GitHub main.

---

## v0.9.2 — Cinematic Matchday Broadcast

- Added a separate, deterministic broadcast planner that reads saved combat results without ever rerolling RNG or awarding duplicate match rewards.
- Added two heraldic entrance announcements and generated 1200x675 PNG introduction and final scoreboard graphics via Pillow. Both accept optional, user-supplied arena/background PNGs.
- Added the staged Approach → Charge → Impact → Aftermath sequence for each completed pass, incorporating arena ambience, tactics, fatigue, special moves, the recorded impact and marshal scoring.
- Implemented one continuously edited Discord live-screen message (not a new message or match for each phase) and a separate accessible final scoreboard with lance breaks, unhorsings, heavy hits, winner/tie, injury report and match ID.
- Added assets/broadcast/manifest.json with optional HTTPS GIF/PNG URLs for all stages, impact-specific categories and arena-specific artwork.
- Added environment configuration for broadcast enabling, adjustable stage delay and reduced-motion mode.
- Persist match history *before* presentation. Broadcast/image failures do not re-simulate matches, produce extra gold or duplicate injuries; the final result is still attempted.
- Added entrance/final media fallbacks and public Main Menu navigation on announcement, live stage and result cards.
- Added unit tests for no duplicate passes, score integrity, no result spoilers, media URL hygiene, PNG dimensions, one-message stage editing, reduced-motion mode and playback failure isolation.
- Updated README, dependencies and /version to v0.9.2.

---


## v0.9.1 — Combat Tactics & Decisions

- Added private challenge-phase choices for both riders: Cautious/Balanced/Aggressive styles, Shield/Lance/Rider targets and an optional manoeuvre.
- Both players must explicitly lock their choices before a public /joust challenge can be accepted; tactics are private until the cinematic match introduction. Timeout extended to 240 seconds.
- Added Precision Strike, Reckless Charge, Shield Brace, Feigned Miss (a situational counter to Aggressive riders) and conditional Last Stand, with two-pass cooldowns.
- Added per-pass fatigue and mount-handling modifiers. Aggressive riding creates more charge but worse alignment, nervous horse behaviour and higher injury risk.
- Integrated style, target, fatigue and activated manoeuvres into existing seeded combat, risk profiles and the match JSON journal. No character-save migration needed.
- Prevented arena rerolls once either rider has locked a tactical plan.
- Expanded result embeds to one per-pass chronicle field so tactical decisions are not lost to the original 1,024-character combined recap truncation.
- Kept neutral Balanced/Shield/No Manoeuvre defaults for admin instant duels and automated tournament rounds.
- Added simulation-based balance checks comparing equal-stat tactical builds, deterministic replay tests, manoeuvre cooldown/fatigue tests, injury-risk tests, and Discord private selection/ready-state tests.

---


## v0.9.0a — Stability, Admin Tools & Cleanup

- Added protected /admin group: /admin panel, /admin health, /admin backup, /admin repair and /admin reset_user; kept /maintenance and /version for compatibility.
- Admin Reset User includes server member selection, Settings/Inventory scopes, impact preview, explicit confirmation button and typed RESET <user ID> modal.
- Protected global player/horse records, history, tournament data, gold earning and other guilds from resets. Inventory retirement retains prior gold spending, preventing reset/refund abuse.
- Every reset creates a SHA-256-verified safety snapshot and an admin_audit.json entry recording scope, target, actor and time. Admin audit data is included in subsequent backup verification/restore checks.
- Admin menu has a direct Reset User button, independently gated by Manage Server permissions.
- Added non-destructive startup JSON health diagnostics, POSIX directory sync after atomic writes and updated version banners.
- Expanded regression tests for reset permissions, scope safety, cross-guild isolation, malformed data rejection, repeat resets, spending integrity and audit snapshots.
- Rewrote the README quick start, command reference and production safety checklist; removed obsolete scope statements.

---


## v0.9.0 — Stability & Admin Tools

- Hardened v0.8.1a physician support so multiple treatment bonuses cannot be banked for several later jousts; only the first completed accepted match after treatment can use one. Added regression coverage.

- Added /version and restricted /maintenance command, linked from the admin dashboard.
- Added SHA256-manifested local JSON backups, verification before restore, strictly validated snapshot names and safety backups before applying changes.
- Implemented an owner/admin-confirmation UI for safe repairs and snapshot restore, with checks to block maintenance while current-process matches are running.
- Added storage health inspection and conservative, dry-run-first repairs: initialize missing files/containers and deduplicate *identical* match records. Conflicting IDs or corrupt structures remain blocked for manual review.
- Added raw quarantine copies when restoring over already-corrupt JSON, so evidence is preserved before recovery.
- Improved JSON save reliability using per-write unique temporary files, fsync and atomic replacement.
- Added 30-second per-player/server challenge posting cooldowns across slash commands and menu buttons.
- Added atomic rider reservation locks to normal, admin test and tournament matches, with release on response errors, cancellations, timeouts and finished matches.
- Added global slash-command error cleanup, private user-friendly failure feedback, logged exception details and short incident references.
- Added regression tests covering backup verification, repair safety, restore, invalid data, atomic storage, cooldowns, locks, admin UI and slash-command error handling.
- Documented limitations: one running bot instance, no distributed transactions, backup files remain local unless copied off-host.

---


## v0.8.5a — Tournament Titles & Achievements

- Introduced twelve equipable, cosmetic tournament titles (30 titles total): Lists Initiate, Bracket Breaker, The Finalist, Silver Lance, Cup Bearer, King of the Lists, Elite Eight, Grand Melee Champion, Marshal's Favourite, Tourney Veteran, Lance of the Lists and Arena Conqueror.
- Added eight independent tournament achievement badges and a private Trophy Cabinet displaying unlock progress, gold/silver medals and lifetime tournament stats.
- Added /tournament achievements [player] and /tournament cabinet; integrated Trophy Cabinet buttons in the public tournament panel and private Tournament menu, with Main Menu navigation.
- Added tournament medal/award progress to knight profiles and post-match announcements of newly unlocked tournament honours for both competitors.
- Replaced fixed /title equip choices with searchable title autocomplete and paginated the title-selection dropdown to obey Discord's 25-option limit.
- Kept tournament unhorsing/lance-break stats distinct from regular career title metrics; all previously earned titles remain valid.
- Rewards derive from verified completed tournament pairings and match journal results, not from registration alone or ordinary duels; server-specific with duplicate protection.
- Stopped truncating saved tournament history at 20 entries, preserving permanent achievements across long careers; recent-history display remains limited.
- Added automated tests for achievements, titles, championship and runner-up results, old title preservation, server isolation, unplayed registrations, long history and UI limits.

---


## v0.8.5 — Tournament Lite

- Added guild-specific, admin-created 4- and 8-player single-elimination tournaments with one active event at a time.
- Added /tournament create, /tournament join, /tournament start, /tournament status, /tournament next, and /tournament history.
- Enforced full brackets, ownership of a bound horse, no bot or duplicate registrations and Manage Server permission on admin operations.
- Randomised initial entrants; persisted all pairings, arenas, seeds, round winners, tournament champions and completion history.
- Added a public, restart-persistent tournament control panel and a private button-based tournament hub; integrated both main player menu and Admin Director.
- Reused the existing cinematic duel engine with the existing ranked, gold, title and injury systems. Registration counts as consent to automatic admin-triggered tournament jousts.
- Added deterministic seeded marshal tiebreaks when a joust ends level; the underlying player match still records a draw.
- Added recovery of interrupted in-progress pairings and stable journal IDs to avoid double-counting matches, gold or injuries on retry.
- Added tournament JSON data to admin health checks and backup snapshots.
- Added regression tests for 4/8 brackets, capacity, eligibility-related UI, server isolation, history, persistent controls and duplicate match-journal prevention.
- No league or season systems in this version.

---


## v0.8.1a — Contextual Injury Risk & Tiered Treatment

- Replaced flat injury odds with capped (2–42%) contextual probabilities: arena (Royal/Festival safer; Muddy/Frozen/War-Torn riskier), armour, barding, attacking lance, horse breed, courage, obedience, and riding while injured.
- Added the horse slip category to potential rider injuries; different arenas and horse slips weight injury types differently.
- Added Twisted Knee (Agility) and Strained Back (Endurance) while preserving the original three injuries and all existing saves.
- Added Light / Moderate / Serious severity, changing only recovery duration (roughly 0.8x, 1x, 1.35x). Existing fairness caps of one injury per rider per bout and at most two effective stat penalties remain.
- Added Faith Healer (12g/8h/16% failure), Shady Doctor (27g/18h/9% failure), and Private Doctor (55g/30h/3% failure).
- Healing successes can never reduce recovery below **3 real hours**; failures still cost gold.
- Successful treatment has a small 12–24% chance of granting one-time next-bout relief, easing a single injury penalty without exceeding normal base stats. Relief expires after 24 hours, and is consumed only by a recorded accepted duel.
- Added a second Injury Ward dropdown for treatment choice; /heal accepts a provider argument with Discord choices.
- Challenge screen now shows illustrative unhorsing injury probabilities, while match results include risk modifier details, severity and injury effects.
- Persisted the mount's breed/handling snapshots and consumed treatment-support token with each competitive match.
- Expanded regression suite with risk, treatment, noninstant recovery, gold spend, odds caps, arena weighting, next-bout aid and compatibility coverage.

---


## v0.8.1 — Injuries & Recovery

- Added three non-permanent knight injuries: Bruised Ribs (Endurance −1, 24h), Wrenched Shoulder (Strength −1, 36h), and Jarred Wrist (Control −1, 48h).
- Injuries roll once after an accepted server challenge, based on the highest serious hit received (28% unhorsing, 12% saddle stagger, 6% heavy shield hit); admin test duels do not injure riders.
- Injury events are deterministically stored inside completed match JSON; no injury rolls are repeated on profile views and old matches are not retroactively injured.
- At most one new injury per rider per match, a maximum of 2 effective stat debuffs total, and no permanent stat losses.
- Free slow natural recovery continues while offline; paid treatment advances the selected injury by 24 hours for 30 gold.
- Healing payments share the existing progression wallet ledger, preventing gold being spent twice on healing and gear.
- Added /injuries and /heal, plus private Injury Ward selection/treatment and Main Menu navigation.
- Added injury announcements in match results, injury indicators on introductions, and recovery status on rider profiles.
- Added regression tests for fair penalties, deterministic outcomes, healing payments, natural expiry, legacy history and match-journal persistence.

---


## v0.8 — Equipment Progression & Unlocks

- Added server-specific gold earned from accepted challenge results only: +12 per match, +8 per win, +4 per draw.
- Added prestige tiers based on completed matches and wins, plus feat-driven reputation (wins, unhorsings and lance breaks); neither metric can be spent or influence combat.
- Added six unlockable equipment sidegrades with trade-offs and a milestone + gold purchase requirement.
- Preserved twelve existing pieces of starter equipment as free choices; original JSON data continues working.
- Added permanent per-server purchases and per-guild knight loadouts; barding belongs to an individual horse.
- Added three earned, purely cosmetic standards (Royal, Frost, Mud) shown in duel intros and profiles.
- Added /progress, /armory, /standards, /equip unlock and /equip wallet, plus an actionable progression screen in /menu.
- Added equipment snapshots to new match records for no-barding wins; kept older history compatible.
- Updated knight/horse views to reflect effective unlocked guild gear.
- Added regression tests for gold calculation, purchasing, inventory isolation, prestige, standards and gear disadvantages.
- Updated admin backup/health tools to include progression.json.

---


## v0.7.1 — Titles & Interactive UI

- Added 12 new earned titles (18 total), preserving the original six and existing title selections.
- Replaced help-only main menu with functional player navigation and Home buttons.
- Knight/horse creation modals plus stat builders with Home navigation, stable browser and binding, gear selection, arena selection and button-driven challenge creation.
- Added profile browsing, leaderboard selection and paginated title unlock/equip/unequip UI.
- Added restricted /admin dashboard with server health, snapshot backups, server totals and instant test duel.
- Restricted instant /joust duel to Manage Server permission, while regular accepted challenges remain open to players.
- Added private Main Menu entrypoints on public challenge/result messages.
- Extended UI navigation/admin permission smoke tests and ignored local backups directory.

---


## v0.7 — Leaderboards & Titles

- Added eight server-scoped boards: wins, win rate, unhorsings, lance breaks, jousts, reliable horses, chaotic horses and arena specialists.
- Added six automatically earned cosmetic titles, /titles progress, /title equip and /title unequip.
- Added minimum match requirements for win-rate, horse and arena rankings.
- Only accepted /joust challenge results affect competitive rankings and title progress; instant duels remain visible in personal match history.
- Match recording now captures guild_id and match type. Historical v0.6 results without guild_id remain in global career profiles only.
- Title selections persist in storage/titles.json and appear on profiles and leaderboards.
- Fixed the invalid Python expression in the v0.6 match-ID embed and added GitHub Actions tests.
- Added Leaderboards and Titles pages to /menu.

---


## v0.6 — Profiles, Records & History

- Added append-only completed match journal in `storage/matches.json` with unique match IDs, participants, horse identities, arena, seed, scores and outcomes.
- Added `/profile [player]`, `/knight stats`, `/horse stats horse_id:<id>`.
- Track knight wins, losses, draws, jousts, unhorsings caused/taken and lance breaks.
- Track horse jousts, refusals, slips and wins with rider.
- Display last five completed matches.
- Declines and timeouts do not create results; instant duels do.
- Career totals are derived from saved match history. Matches before v0.6 are not automatically backfilled.

---

## v0.5 — Match Engine Polish

Combat readability and tuning update. This version makes jousts feel more like a sport while keeping the existing command flow.

### Added

- Better pass categories:
  - `clean_miss`
  - `shield_scrape`
  - `lance_break`
  - `heavy_shield_hit`
  - `saddle_stagger`
  - `unhorsing`
  - `horse_refusal`
  - `horse_slip`
  - `double_clash`
- More flavour text per result category.
- Arena-specific pass lines.
- Gear-specific pass lines.
- Match seed generation and seed display in result embeds.
- Optional `seed` parameter on joust commands for reproducible matches.
- Optional `debug` parameter on joust commands.
- Hidden admin/debug roll breakdown embed when `debug: True` is used by someone with Manage Server permission.
- `services/balance.py` for tunable match constants.
- Random arena support using `arena_key: random`.
- Random Arena button on active challenges.
- Expanded pre-match comparison in challenge embeds.

### Notes

- `/joust challenge` remains the preferred player flow.
- `/joust duel` remains available for instant/admin-style testing.
- Debug output is intentionally hidden/ephemeral and permission-gated.

---

## v0.4 — Challenge Flow

Controlled duel flow update for fair player-vs-player jousts.

### Added

- `/joust challenge opponent:<member> arena_key:<arena>`.
- Public challenge embed with challenger, opponent, arena and timeout details.
- Accept Challenge button for the challenged player.
- Decline button for the challenged player or challenger.
- 120-second challenge timeout.
- Active challenge lock to prevent overlapping challenge spam.
- Shared duel preparation logic used by both `/joust duel` and `/joust challenge`.
- v0.4 footer label on joust embeds.

### Completed in v0.5

- Random Arena button.
- Expanded pre-match comparison before accept.

### Notes

- `/joust duel` still exists for instant/admin-style testing.
- `/joust challenge` is now the preferred normal player flow.

---

## v0.3 — Match Presentation Update

Presentation-layer update for single joust matches.

### Added

- Cinematic duel intro embed before each match.
- Arena flavour text in the intro.
- Rider-vs-rider presentation with knight, horse, lance, armour and barding details.
- Dramatic pass-by-pass match chronicle.
- Result-specific flavour text for:
  - unhorsing
  - solid hits
  - lance breaks
  - glancing clashes
  - missed passes
  - refused charges
  - even clashes
- Final result summary embed.
- Footer label showing `JoustingBot v0.3 — Match Presentation Update`.
- GIF placeholder support in `cogs/joust.py` via `GIF_PLACEHOLDERS`.

### Notes

- Core combat maths were not changed in this update.
- GIF placeholders are intentionally blank by default. Add hosted image/GIF URLs into `GIF_PLACEHOLDERS` when assets are ready.

---

## v0.2 — Menu + Builder Update

- Added `/menu`.
- Added `/help_joust`.
- Added interactive main menu buttons.
- Converted horse creation to dropdown stat-builder flow.
- Updated README.

---

## v0.1 — Core MVP

- Knight creation.
- Horse creation and binding.
- Equipment system.
- Arena system.
- Single joust duel command.
- JSON local storage.
