# Changelog

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
