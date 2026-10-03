# Changelog

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
