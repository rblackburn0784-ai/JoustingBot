# JoustingBot

A lightweight medieval jousting Discord game bot built with `discord.py`.

**Current version:** `v0.6 — Profiles, Records & History`

Players create a knight, build and bind a horse, equip both rider and horse, choose an arena, and challenge other Discord users to cinematic jousts with accept/decline buttons.

This version focuses on making matches feel more like a sport: richer pass categories, arena-specific lines, gear-specific lines, seed display, debug roll breakdowns, and tunable balance constants.

---

## v0.6 Career & History

Every **completed** joust (including instant test duels) is saved to `storage/matches.json`. Declined and expired challenges do not count. Existing knight and horse JSON records remain compatible; older matches played before this update cannot be reconstructed automatically.

- `/profile [player]` — rider record, bound mount, and five most recent completed matches (private response).
- `/knight stats` — your knight's wins, losses, draws, total jousts, unhorsings caused, times unhorsed, and lance breaks.
- `/horse stats horse_id:<id>` — your horse's appearances, refusals, slips, and wins with its rider.
- Saved history includes the matchup, horse identities, arena, scores, seed and pass outcomes.
- Historical totals are calculated from the match journal, avoiding accidental double counting from displaying a result twice.

**Note:** Records are local to the bot installation, not shared across deployments. Instant `/joust duel` results also count. Back up `storage/matches.json` alongside your existing local data.

---

## Features

- Interactive `/menu` with button-based help pages
- Private dropdown knight builder
- Private dropdown horse builder
- Horse binding
- Knight lances and armour
- Horse barding
- Arenas with modifiers
- `/joust challenge` with accept/decline buttons
- 120-second challenge timeout
- Active challenge locking
- Random arena support
- Random Arena button on challenges
- Expanded pre-match comparison before accept
- `/joust duel` for instant testing/admin use
- Cinematic intro embed
- Dramatic pass-by-pass match chronicle
- Final result summary embed
- Match seed display
- Optional reproducible seed input
- Hidden admin/debug roll breakdowns
- Balance constants in `services/balance.py`
- JSON-based local storage

---

## Current gameplay loop

```text
/menu
/knight create name: Sir Raymond
/horse create name: Biscuit breed: Destrier
/horse list
/horse bind horse_id: h-123456-biscuit-1234567890
/equip list
/equip lance item_key: lance_heavy
/equip armour item_key: armour_full
/equip barding item_key: barding_steel
/arena list
/joust challenge opponent: @Opponent arena_key: royal_lists
```

You can also use a random arena:

```text
/joust challenge opponent: @Opponent arena_key: random
```

For immediate testing:

```text
/joust duel opponent: @Opponent arena_key: royal_lists
```

For reproducible/admin testing:

```text
/joust duel opponent: @Opponent arena_key: frozen_ground seed: 12345 debug: True
```

`debug: True` only shows hidden roll breakdowns to users with **Manage Server** permission.

---

## Requirements

- Python 3.11 or newer
- Discord bot token
- `discord.py`
- `python-dotenv`

Install dependencies:

```bash
pip install discord.py python-dotenv
```

---

## Setup

```bash
git clone https://github.com/rblackburn0784-ai/JoustingBot.git
cd JoustingBot
```

Create `.env` beside `main.py`:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

Run:

```bash
python main.py
```

---

## Project structure

```text
JoustingBot/
│
├── cogs/
│   ├── arena.py        # /arena commands
│   ├── equipment.py    # /equip commands
│   ├── horse.py        # /horse commands and horse builder UI
│   ├── profile.py      # /profile and records screens
│   ├── joust.py        # /joust challenge, /joust duel, presentation and debug embeds
│   ├── knight.py       # /knight commands and knight builder UI
│   └── menu.py         # /menu and /help_joust
│
├── services/
│   ├── arenas.py       # Arena definitions
│   ├── balance.py      # v0.5 tunable combat constants
│   ├── records.py      # Persistent matches and career statistics
│   ├── combat.py       # Match simulation logic
│   ├── equipment.py    # Equipment definitions and modifiers
│   └── storage.py      # JSON helpers
│
├── storage/            # Runtime JSON save files
├── CHANGELOG.md
├── .gitignore
├── main.py
└── README.md
```

---

## Joust commands

### `/joust challenge opponent:<member> arena_key:<arena> seed:<optional> debug:<optional>`

Preferred normal player flow.

Creates a public challenge with:

- Accept Challenge button
- Decline button
- Random Arena button
- Pre-match rider comparison
- Arena modifiers
- 120-second timeout

Only the challenged player can accept. The challenger or challenged player can decline.

### `/joust duel opponent:<member> arena_key:<arena> seed:<optional> debug:<optional>`

Runs the match immediately. Best for testing/admin use.

---

## v0.5 pass categories

The match engine now returns structured pass categories:

- `clean_miss`
- `shield_scrape`
- `lance_break`
- `heavy_shield_hit`
- `saddle_stagger`
- `unhorsing`
- `horse_refusal`
- `horse_slip`
- `double_clash`

Each pass can include:

- public result label
- score change
- margin
- arena-specific flavour line
- gear-specific flavour line
- notes
- hidden debug rolls

---

## Match scoring

General scoring:

- Clean miss: 0 points
- Shield scrape: 0 points
- Lance break: 1 point
- Heavy shield hit: 2 points
- Saddle stagger: 2 points
- Unhorsing: 3 points
- Horse refusal: 1 point to opponent
- Horse slip: 1 point to opponent
- Double clash: 0 points

Matches run up to 5 passes. First to 3 points can end the match early.

---

## Debug and seeds

Every match result shows a seed.

Use a seed to reproduce a match shape:

```text
/joust duel opponent: @Opponent arena_key: royal_lists seed: 12345
```

Use debug mode for hidden roll breakdowns:

```text
/joust duel opponent: @Opponent arena_key: royal_lists seed: 12345 debug: True
```

Debug requires **Manage Server** permission and is sent as an ephemeral message.

---

## GIF placeholders

`cogs/joust.py` contains:

```python
GIF_PLACEHOLDERS = {
    "intro": "",
    "lance_break": "",
    "heavy_shield_hit": "",
    "saddle_stagger": "",
    "unhorsing": "",
    "miss": "",
    "draw": "",
    "victory": "",
}
```

Add hosted GIF/image URLs later. Blank values are safe.

---

## Other commands

### Main menu

```text
/menu
/help_joust
```

### Knight

```text
/knight create name:<name>
/knight view
/knight delete
```

Knight stats: `strength`, `control`, `endurance`, `agility`, `resolve`, `tactics`.

### Horse

```text
/horse create name:<name> breed:<breed>
/horse list
/horse view horse_id:<id>
/horse bind horse_id:<id>
/horse delete horse_id:<id>
```

Horse stats: `speed`, `stamina`, `power`, `obedience`, `courage`.

### Equipment

```text
/equip list
/equip list slot:lance
/equip list slot:armour
/equip list slot:barding
/equip lance item_key:<key>
/equip armour item_key:<key>
/equip barding item_key:<key>
```

### Arena

```text
/arena list
/arena view arena_key:<key>
```

Current arenas:

- `royal_lists`
- `muddy_field`
- `frozen_ground`
- `wind_swept`
- `festival_arena`
- `war_torn`

---

## Current scope

Included:

- Main menu
- Knight builder
- Horse builder
- Horse binding
- Equipment
- Arenas
- Challenge/accept duel flow
- Random arena controls
- Cinematic duel intro
- v0.5 match engine categories
- Dramatic pass-by-pass presentation
- Seed/debug support
- Instant duel command for testing

Not currently included:

- Tournaments
- Ranked ladder
- Injuries
- Economy/gold
- XP/levelling
- Match replay logs
- Persistent leaderboards
