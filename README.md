# JoustingBot

A medieval jousting Discord bot built with `discord.py`.

This is a lightweight game-style bot where Discord users can create knights, create and bind horses, equip both rider and horse, choose an arena, and run single joust matches.

The current version is intentionally simple: **no tournaments, no ladders, no injuries, no replay system**. It is a clean base for expanding later.

---

## Features

- Create a knight with balanced stat allocation
- Interactive knight stat builder using Discord dropdowns
- Create horses with their own stats
- Bind a horse to your knight
- Equip knight lances and armour
- Equip horse barding
- View available arenas
- Run single joust matches against another Discord user
- Equipment has positive and negative traits for balance
- Arenas affect charge, alignment, slip risk, panic risk, and impact
- JSON-based local storage

---

## Current gameplay loop

1. Create your knight.
2. Assign knight stats using the private stat builder.
3. Create a horse.
4. Bind the horse to your knight.
5. Equip your knight and horse.
6. Pick an arena.
7. Challenge another player to a joust.

Example:

```text
/knight create name: Sir Raymond
/horse create name: Biscuit breed: Destrier speed: 5 stamina: 5 power: 5 obedience: 4 courage: 5
/horse list
/horse bind horse_id: h-123456-biscuit-1234567890
/equip list
/equip lance item_key: lance_heavy
/equip armour item_key: armour_full
/equip barding item_key: barding_steel
/arena list
/joust duel opponent: @Opponent arena_key: royal_lists
```

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

### 1. Clone the repository

```bash
git clone https://github.com/rblackburn0784-ai/JoustingBot.git
cd JoustingBot
```

### 2. Create a `.env` file

Create a file named `.env` in the project root, next to `main.py`.

```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

Do not commit `.env` to GitHub. It is ignored by `.gitignore`.

### 3. Run the bot

```bash
python main.py
```

If slash commands do not appear immediately in Discord, restart the Discord client or wait a short while for command sync.

---

## Project structure

```text
JoustingBot/
│
├── cogs/
│   ├── arena.py        # /arena commands
│   ├── equipment.py    # /equip commands
│   ├── horse.py        # /horse commands
│   ├── joust.py        # /joust duel command
│   └── knight.py       # /knight commands and stat builder UI
│
├── services/
│   ├── arenas.py       # Arena definitions and modifiers
│   ├── combat.py       # Match simulation logic
│   ├── equipment.py    # Equipment definitions and modifiers
│   └── storage.py      # JSON load/save helpers
│
├── storage/            # Local JSON save files, created at runtime
├── .gitignore
├── main.py
└── README.md
```

---

## Commands

### Knight commands

#### `/knight create name:<name>`

Creates a new knight using an interactive private stat builder.

The stat builder starts each stat at 1 and gives the player 20 total points to spend.

Knight stats:

- `strength`
- `control`
- `endurance`
- `agility`
- `resolve`
- `tactics`

Rules:

- Total points must equal 20.
- Each stat must stay between 1 and 8.
- The `Create Knight` button only completes creation once the total is valid.

#### `/knight view`

Shows your current knight, stats, equipped lance, equipped armour, and bound horse.

#### `/knight delete`

Deletes your knight.

---

### Horse commands

#### `/horse create`

Creates a horse.

Horse stats:

- `speed`
- `stamina`
- `power`
- `obedience`
- `courage`

Rules:

- Total horse stat points must equal 24.
- Each horse stat must be between 1 and 10.

Example:

```text
/horse create name: Biscuit breed: Destrier speed: 5 stamina: 5 power: 5 obedience: 4 courage: 5
```

#### `/horse list`

Lists your horses and their horse IDs.

#### `/horse view horse_id:<id>`

Shows one of your horses.

#### `/horse bind horse_id:<id>`

Binds one of your horses to your knight.

A knight needs a bound horse before jousting.

#### `/horse delete horse_id:<id>`

Deletes one of your horses.

---

### Equipment commands

#### `/equip list`

Lists all equipment.

#### `/equip list slot:lance`

Lists only lances.

#### `/equip list slot:armour`

Lists only armour.

#### `/equip list slot:barding`

Lists only horse barding.

#### `/equip lance item_key:<key>`

Equips a lance on your knight.

#### `/equip armour item_key:<key>`

Equips armour on your knight.

#### `/equip barding item_key:<key>`

Equips barding on your currently bound horse.

---

### Arena commands

#### `/arena list`

Lists all available arenas.

#### `/arena view arena_key:<key>`

Shows arena modifiers.

Current arenas:

- `royal_lists`
- `muddy_field`
- `frozen_ground`
- `wind_swept`
- `festival_arena`
- `war_torn`

---

### Joust commands

#### `/joust duel opponent:<member> arena_key:<arena>`

Runs a single joust match against another player.

Example:

```text
/joust duel opponent: @Opponent arena_key: frozen_ground
```

Both players need:

- A knight
- A horse
- A bound horse

The match runs up to 5 passes and ends early if a rider reaches 3 points.

---

## Knight stats

| Stat | Purpose |
|---|---|
| Strength | Adds force to charge and impact |
| Control | Helps alignment and accuracy |
| Endurance | Useful for heavier armour and future systems |
| Agility | Represents balance and responsiveness |
| Resolve | Represents nerve under pressure |
| Tactics | Reserved for future expansion |

---

## Horse stats

| Stat | Purpose |
|---|---|
| Speed | Adds to charge power |
| Stamina | Helps reduce slip risk |
| Power | Adds to charge power |
| Obedience | Helps alignment and behaviour checks |
| Courage | Helps resist panic, bolting, and refusal |

---

## Equipment balance

Equipment is not meant to be pure upgrades. Most items trade one advantage for one weakness.

### Lances

| Key | Item | Strength | Weakness |
|---|---|---|---|
| `lance_ash` | Ash Lance | Balanced | None |
| `lance_heavy` | Heavy War Lance | Higher impact | Worse aim/control |
| `lance_tournament` | Tournament Lance | Better accuracy | Lower impact |
| `lance_long` | Long Reach Lance | Better control | Lower strength/charge |

### Armour

| Key | Item | Strength | Weakness |
|---|---|---|---|
| `armour_mail` | Tournament Mail | Balanced | None |
| `armour_light` | Light Plate | Better agility/aim | Easier to unhorse |
| `armour_full` | Full Plate | Harder to unhorse | Worse agility/control |
| `armour_reinforced_helm` | Reinforced Helm | Better resolve/resistance | Worse vision/aim |

### Barding

| Key | Item | Strength | Weakness |
|---|---|---|---|
| `barding_none` | No Barding | No penalties | No protection |
| `barding_leather` | Leather Barding | Calmer horse | Minimal downside |
| `barding_steel` | Steel Barding | Braver horse | Slower, more slip risk |
| `barding_spiked` | Spiked Barding | More aggressive charge | Less obedience, more slip risk |

---

## Arenas

Arenas modify the joust without requiring a tournament system.

| Key | Arena | Gameplay effect |
|---|---|---|
| `royal_lists` | Royal Lists | Balanced default field |
| `muddy_field` | Muddy Field | Worse charge and alignment, higher slip risk |
| `frozen_ground` | Frozen Ground | Harder impacts, high slip risk |
| `wind_swept` | Wind-Swept Field | Worse alignment, slight panic pressure |
| `festival_arena` | Festival Arena | Crowd pressure and distraction |
| `war_torn` | War-Torn Battlefield | Chaotic, unstable, harder-hitting field |

---

## Match scoring

Each joust pass compares alignment, charge, equipment, horse behaviour, and arena modifiers.

Possible outcomes:

| Outcome | Points |
|---|---:|
| Glancing clash | 0 |
| Lance break | 1 |
| Solid hit | 2 |
| Unhorsed | 3 |
| Horse refused while opponent charges | Opponent gains 1 |

The match ends when:

- One player reaches 3 points, or
- 5 passes have been completed

---

## Local storage

The bot stores data in local JSON files under `storage/`.

Typical runtime files:

```text
storage/knights.json
storage/horses.json
```

These files are ignored by Git so local test data does not get committed.

---

## Troubleshooting

### `RuntimeError: Missing DISCORD_BOT_TOKEN in .env`

Create a `.env` file beside `main.py`:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

Make sure it is named `.env`, not `.env.txt`.

### Slash commands are not showing

Try:

1. Stop the bot.
2. Start it again.
3. Restart Discord.
4. Wait a short while for global slash command sync.

### `/knight create` says the bot is thinking forever

This usually means an exception happened during the interaction.

Check the PyCharm or terminal console for the real error.

The current version uses a safer two-dropdown stat builder to avoid Discord component layout problems.

### Import errors involving `services.arenas`

Make sure `services/arenas.py` contains the `ARENAS` dictionary and does not import itself.

Correct import style:

```python
from services.arenas import ARENAS, get_arena
```

Wrong import style:

```python
from services.arenas import arenas
```

### Do not run cog files directly

Do not run:

```bash
python cogs/joust.py
```

Run the bot from:

```bash
python main.py
```

---

## Development notes

This bot is currently a simplified base. Good future additions would be:

- Duel confirmation buttons
- Public challenge/accept flow
- Tournament mode
- Ranked ladder
- Match logs and replay
- Injuries and healing
- Knight XP and levelling
- Horse bond XP
- Better embeds and flavour commentary
- Arena images or GIF highlights

---

## License

No license has been set yet.
