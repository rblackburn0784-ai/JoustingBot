# JoustingBot

A lightweight medieval jousting Discord game bot built with `discord.py`.

Players create a knight, build and bind a horse, equip both rider and horse, choose an arena, and run single-match jousts against other Discord users.

This version is a clean MVP base: **main menu, knight builder, horse builder, equipment, arenas, and single duels**. It does not currently include tournaments, ladders, injuries, economy, or replay logs.

---

## Features

- Interactive `/menu` with button-based help pages
- Create a knight with a private dropdown stat builder
- Create a horse with a private dropdown stat builder
- Bind a horse to your knight
- Equip knight lances and armour
- Equip horse barding
- View available arenas and arena modifiers
- Run single joust matches against another Discord user
- Equipment has positive and negative traits for balance
- Arenas affect charge, alignment, slip risk, panic risk, and impact
- JSON-based local storage

---

## Current gameplay loop

1. Open the main menu.
2. Create your knight.
3. Create your horse.
4. Bind the horse to your knight.
5. Equip your knight and horse.
6. Pick an arena.
7. Challenge another player to a joust.

Example:

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
│   ├── horse.py        # /horse commands and horse stat builder UI
│   ├── joust.py        # /joust duel command
│   ├── knight.py       # /knight commands and knight stat builder UI
│   └── menu.py         # /menu and /help_joust interactive main menu
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

### Main menu

#### `/menu`

Opens the main Jousting Bot menu with buttons for:

- Getting Started
- Knight
- Horse
- Equipment
- Arenas
- Duel

#### `/help_joust`

Alias-style help command that opens the same interactive menu.

---

### Knight commands

#### `/knight create name:<name>`

Creates a new knight using an interactive private stat builder.

The builder starts each stat at 1 and gives the player **20 total points** to spend.

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
- The `Create Knight` button only enables once the total is valid.

#### `/knight view`

Shows your current knight, stats, equipped lance, equipped armour, and bound horse.

#### `/knight delete`

Deletes your knight.

---

### Horse commands

#### `/horse create name:<name> breed:<breed>`

Creates a new horse using an interactive private stat builder.

The builder starts each stat at 1 and gives the player **24 total points** to spend.

Horse stats:

- `speed`
- `stamina`
- `power`
- `obedience`
- `courage`

Rules:

- Total horse stat points must equal 24.
- Each horse stat must stay between 1 and 10.
- The `Create Horse` button only enables once the total is valid.

#### `/horse list`

Lists your horses and their horse IDs.

#### `/horse view horse_id:<id>`

Shows one of your horses.

#### `/horse bind horse_id:<id>`

Binds one of your horses to your knight.

A knight needs a bound horse before jousting.

#### `/horse delete horse_id:<id>`

Deletes one of your horses. If that horse was bound to your knight, the knight is unbound.

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

Shows one arena and its modifiers.

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

Runs a single joust match.

Requirements:

- Both players must have a knight.
- Both players must have a bound horse.
- The arena key must be valid.

Example:

```text
/joust duel opponent: @Opponent arena_key: frozen_ground
```

---

## Stats overview

### Knight stats

| Stat | Main role |
|---|---|
| Strength | Adds power to charge impact |
| Control | Helps alignment and lance control |
| Endurance | Used by armour/equipment balance and future expansion |
| Agility | Used by armour/equipment balance and future expansion |
| Resolve | Future expansion / flavour support |
| Tactics | Future expansion / flavour support |

### Horse stats

| Stat | Main role |
|---|---|
| Speed | Adds to charge force |
| Stamina | Helps avoid slipping |
| Power | Adds to charge force |
| Obedience | Helps alignment and prevents refusal/slip |
| Courage | Helps prevent refusal/bolting |

---

## Equipment balance

### Lances

| Key | Item | Positive | Negative |
|---|---|---|---|
| `lance_ash` | Ash Lance | Balanced | None |
| `lance_heavy` | Heavy War Lance | Higher impact | Worse aim/control |
| `lance_tournament` | Tournament Lance | Better accuracy | Lower impact |
| `lance_long` | Long Reach Lance | Better control | Lower strength/charge |

### Armour

| Key | Item | Positive | Negative |
|---|---|---|---|
| `armour_mail` | Tournament Mail | Balanced | None |
| `armour_light` | Light Plate | Better agility/aim | Easier to unhorse |
| `armour_full` | Full Plate | Harder to unhorse | Worse agility/control |
| `armour_reinforced_helm` | Reinforced Helm | Better resolve/resistance | Worse control/vision |

### Barding

| Key | Item | Positive | Negative |
|---|---|---|---|
| `barding_none` | No Barding | No restrictions | No protection |
| `barding_leather` | Leather Barding | Calmer/braver horse | Minimal downside |
| `barding_steel` | Steel Barding | Braver horse | Slower, more slip risk |
| `barding_spiked` | Spiked Barding | More aggressive charge | Less obedience, more slip risk |

---

## Arena effects

Arenas can modify:

- Alignment
- Charge
- Slip risk
- Panic/refusal risk
- Impact multiplier

Use:

```text
/arena view arena_key:<key>
```

to inspect exact modifiers in Discord.

---

## Match scoring

Each match runs up to 5 passes.

General scoring:

- Lance break: 1 point
- Solid hit: 2 points
- Unhorsed: 3 points
- Horse refusal can award 1 point to the opponent
- First to 3 points can end the match early
- Otherwise, highest score after 5 passes wins

---

## Storage

The bot uses local JSON files created at runtime:

```text
storage/knights.json
storage/horses.json
```

These files are ignored by Git and should remain local.

---

## Troubleshooting

### `RuntimeError: Missing DISCORD_BOT_TOKEN in .env`

Make sure `.env` exists beside `main.py` and contains:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

### Slash commands do not appear

Try:

1. Stop the bot.
2. Restart the bot.
3. Restart Discord.
4. Wait a short while for command sync.

### `/horse create` or `/knight create` does not finish

Make sure you spend exactly the required points:

- Knight: 20 points
- Horse: 24 points

The create button stays disabled until the total is correct.

### Unknown arena or item key

Use:

```text
/arena list
/equip list
```

to see valid keys.

---

## Current scope

Included:

- Main menu
- Knight builder
- Horse builder
- Horse binding
- Equipment
- Arenas
- Single duels

Not currently included:

- Tournaments
- Ranked ladder
- Injuries
- Economy/gold
- XP/levelling
- Match replay logs
- Persistent leaderboards

These can be added later once the core loop is stable.
