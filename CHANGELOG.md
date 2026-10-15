# Changelog

## v0.9.0 — Stability & Admin Tools

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
