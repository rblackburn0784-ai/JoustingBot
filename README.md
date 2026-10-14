# JoustingBot

A lightweight medieval jousting Discord game bot built with `discord.py`.

**Current version:** `v0.8.1 — Injuries & Recovery`

Players create a knight, build and bind a horse, equip both rider and horse, choose an arena, and challenge other Discord users to cinematic jousts with accept/decline buttons.

This version focuses on making matches feel more like a sport: richer pass categories, arena-specific lines, gear-specific lines, seed display, debug roll breakdowns, and tunable balance constants.

---

## v0.8.1 — Injuries & Recovery

Knights can suffer **minor, temporary injuries** from serious impacts in **accepted** jousts. Injuries are part of the match history, are generated once per completed match, and have no permanent effects. Admin-only instant test duels do not cause injuries.

### Possible injuries

| Injury | Knight stat reduction | Natural healing |
| --- | --- | --- |
| Bruised Ribs | Endurance −1 | 24 real hours |
| Wrenched Shoulder | Strength −1 | 36 real hours |
| Jarred Wrist | Control −1 | 48 real hours |

An unhorsing has a 28% chance of injuring the rider who was unhorsed; a saddle stagger has a 12% chance, and a heavy shield hit has a 6% chance. A match can inflict **at most one injury per rider**, using the most serious impact received. These are approximate chances before the deterministic seeded injury roll, not guarantees.

**Fair-play restrictions:** Active injury debuffs are capped to **2 total stat points** across at most two different stats. No stat can drop below 1 from injury effects. Any additional injury is displayed but cannot increase that penalty; injuries are never fatal and do not change permanent allocated character stats. Recovery continues based on real-world time, even while the bot is offline.

### Gold treatment

- **30 gold** reduces one selected injury's remaining recovery time by **24 hours**.
- A treatment may finish recovery immediately if under 24 hours remain.
- The cost is paid from the same gold wallet used for purchasing equipment.
- Treatment is only permitted for your own active injuries in that server.
- Injuries heal naturally for free. Paying is optional, and confers no advantage beyond returning a hurt knight to their normal base stats.

### Commands and UI

- `/injuries` — private Injury Ward panel showing remaining healing time, effective penalties and gold balance.
- `/heal injury_id:<id>` — pay for 24 hours of recovery.
- `/menu` → **Injuries**, or `/menu` → **Profile** → **Injury Ward** — button-only recovery flow with a dropdown to select an injury and a **Treat Selected** button.
- Your `/profile` and duel introduction show current injury status.
- Match results announce any new injuries.

### Persistence and compatibility

New injury snapshots are saved **inside `storage/matches.json`**, alongside the completed match that caused them. Gold treatment payments are stored in **`storage/progression.json`**, so equipment purchases and treatments cannot spend the same gold. Both files are already included in the Admin backup and Git ignore rules.

**Historical matches from v0.8 or earlier do not produce retroactive injuries.** Existing saves do not require migration. The injury roll is based on a match's unique ID, so viewing a result again never generates another injury.

---

## v0.8 — Equipment Progression & Unlocks

The v0.8 release introduces a **guild-specific equipment economy** and unlockable sidegrades. The original twelve pieces of equipment are still free and usable without migration. New equipment is deliberately designed as a *sidegrade*, with an advantage and a meaningful drawback.

### Gold and prestige

Only **completed, accepted** `/joust challenge` matches in the current server earn gold, prestige and unlock progress. Instant admin test duels do **not** earn rewards.

| Outcome | Gold earned |
| --- | ---: |
| Participate in an accepted joust | +12 |
| Win (additional bonus) | +8 |
| Draw (additional bonus) | +4 |

A win therefore awards **20 gold**, a draw **16 gold** and a loss **12 gold**. The gold wallet is derived from the completed-match journal, less previous purchases in `storage/progression.json`, so simply restarting the bot does not duplicate rewards.

Prestige is **1 per completed challenge plus 2 per win**, and determines a display tier (Squire, Lancer, Knight Errant, Grand Champion, Legend of the Lists). **Reputation** is another non-spendable metric: +1 for each competitive win, +2 for each unhorsing caused and +1 per lance break. Neither prestige nor reputation changes combat strength.

### Unlockable sidegrade equipment

| Item | Required achievement | Cost | Advantages and drawbacks |
| --- | --- | ---: | --- |
| Oakbreaker Lance | 5 wins | 110 | Better charge and impact; weaker control/alignment |
| Windrunner Lance | 3 wins on Wind-Swept Field | 100 | Excellent alignment; reduced charge |
| Riveted Mail | 8 completed jousts | 105 | Some unhorsing resistance; worse alignment |
| Duelist's Harness | Unhorse 3 rivals | 110 | Better alignment; much lower saddle protection |
| Runner's Barding | Win with no barding equipped | 95 | Higher speed; less courage and more slipping |
| Marsh Warden Barding | Finish 3 Frozen Ground jousts without being unhorsed | 95 | Better footing; lower speed and charge |

Once an achievement is satisfied, players may **purchase** the item with earned gold. Buying the same item twice is rejected. Equipment purchases are permanent per server; no microtransactions or paid currency are involved.

**Equipment loadouts are per server.** Lance and armour are chosen for the player's knight, while barding is equipped to a specific owned horse. Stored old-style gear is used as a fallback where possible; in a different server, gear that has not been unlocked there cannot be brought into combat.

### Cosmetic standards

Standards are displayed at duel introductions and on player career profiles, but have **no gameplay effects**.

- **Royal Standard** — win 5 accepted jousts.
- **Frost Pennant** — complete 3 Frozen Ground jousts without being unhorsed.
- **Mud Banner** — win 3 Muddy Field jousts.
- **No Standard** — unequipped/default.

Cosmetic standards are earned automatically; they cost no gold.

### Navigation and commands

The `/menu` main hub now has a **Progression** button. The **Equipment** section includes gear selection, **Unlock Selected**, **Equip Selected**, Gold and Standards screens, all with Main Menu navigation.

- `/progress` — interactive wallet, rank and achievement progress.
- `/armory` — interactive equipment catalog, unlock and equip controls.
- `/standards` — browse/equip earned cosmetic standards.
- `/equip list [slot]` — view equipment and unlock requirements.
- `/equip unlock item_key:<key>` — unlock one earned sidegrade for gold.
- `/equip wallet` — view available gold.
- `/equip lance|armour|barding item_key:<key>` — equip owned gear.

Player/horse profiles and duel introductions reflect the actual equipped loadout. New match records store the equipment used in a duel, making no-barding challenge unlocks auditable. Historical matches without equipment snapshots cannot count towards the specific *no-barding* achievement.

`storage/progression.json` contains your purchases, server-specific loadouts and standards; it is intentionally excluded from Git and included in the Admin backup/health checks. Back up this file together with `storage/matches.json`, `storage/titles.json`, `storage/knights.json` and `storage/horses.json`. On Railway, use a persistent volume for storage.

---

## v0.7.1 — Titles & Interactive Game Hub

**12 new earnable titles** bring the total to **18**. All are unlocked automatically from accepted-challenge match history in the current Discord server. They give **no combat advantages**.

| New title | Requirement |
| --- | --- |
| First Lance | Win your first accepted joust |
| Iron Will | Win 10 jousts |
| Grand Champion | Win 25 jousts |
| Veteran of the Lists | Complete 25 jousts |
| Saddlebreaker | Unhorse opponents 10 times |
| Timberstorm | Break 15 lances |
| Royal Standard | Win 3 jousts at Royal Lists |
| Gale Rider | Win 3 jousts at Wind-Swept Field |
| Festival Hero | Win 3 jousts at Festival Arena |
| Battle Hardened | Win 3 jousts at War-Torn Battlefield |
| Honour Bound | Finish 3 jousts in draws |
| Steady in the Saddle | Complete 10 clean jousts without horse slip/refusal |

### Main menu and navigation

The `/menu` and `/help_joust` commands now open a **functional game dashboard**, not just command instructions. Every hub page has a **Main Menu** button.

- **Getting Started:** guided game flow.
- **Knight:** Create (modal + point allocation), view, career stats, delete confirmation.
- **Horse:** Create (modal + point allocation), browse/select horses, view, stats, bind, delete confirmation; stable pages for larger collections.
- **Equipment:** browse lances, armour and barding, then equip using Discord dropdowns and buttons.
- **Arenas:** browse modifiers, pick a random arena, or start a challenge for that arena.
- **Challenge:** select another Discord member and an arena, then post a public challenge with Accept/Decline buttons; instant test duels are separate.
- **Profile:** browse another member's profile, your stats and recent history.
- **Leaderboards:** switch between eight server rankings with a dropdown.
- **Titles:** browse three pages of six titles with progress, choose and equip an earned title, or unequip it.
- **Admin:** restricted menu with System Health, Server Summary, Backup Data and Instant Test Duel.

The `/titles` slash command also opens the new title browser. Duel challenge/result messages have a **Main Menu** button that opens a private dashboard for the person who clicks.

### Admin permissions

The **Admin** entry is displayed only to members with **Manage Server** permission. `/admin` is hidden from ordinary users where supported by Discord permissions, and the bot **checks permission again for every admin button**. Instant `/joust duel` testing is now also restricted to admins; normal gameplay uses `/joust challenge`.

The backup button writes timestamped JSON snapshots to `backups/` on the host machine, which Git ignores. These are *local* files, not off-host backups.

### Compatibility

No reset or migration is required for existing knight, horse, match or title JSON. The original six titles and their keys are preserved. The 12 new titles use the same server-specific accepted-joust rules, and existing eligible records can count toward them.

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

## v0.7 — Leaderboards & Titles

Eight server-scoped leaderboards are available, based on **accepted challenges only**:

| Command | Ranking | Minimum |
| --- | --- | --- |
| /leaderboard wins | Most wins | 1 match |
| /leaderboard winrate | Win percentage | 5 matches |
| /leaderboard unhorsings | Most unhorsings caused | 1 match |
| /leaderboard lancebreaks | Most lance breaks | 1 match |
| /leaderboard jousts | Most completed matches | 1 match |
| /leaderboard reliable_horse | Clean jousts / total jousts | 5 horse jousts |
| /leaderboard chaotic_horse | (Refusals + slips) / joust | 3 horse jousts |
| /leaderboard arena | Each rider's best arena by wins | 3 jousts at that arena |

**Six cosmetic titles** can be earned:

| Title | Unlock |
| --- | --- |
| The Unhorsed | Get unhorsed five times |
| Shield Splitter | Break five lances |
| Mud King | Win three jousts on Muddy Field |
| Frozen Terror | Win three jousts on Frozen Ground |
| Crowd Favourite | Complete ten jousts |
| The Reluctant Rider | Experience three horse refusals |

Use /titles to check progress, /title equip to select a title and /title unequip to remove it. Equipped titles appear on your profile and alongside your name in server leaderboards. They provide no combat bonuses.

**Server scoping and historical data:** From v0.7 onwards, new match records include the Discord guild ID. Historical v0.6 match records did not capture guild IDs, so they remain available in global career history but are excluded from new *server* rankings and title unlocks. **Only accepted /joust challenge matches count towards server leaderboards and earned titles.** Instant /joust duel tests continue to be saved in personal match history, but do not affect competitive standings.

Back up both storage/matches.json and storage/titles.json; these files are intentionally ignored by Git. Automated Python syntax, tests and Discord command-registration checks run under GitHub Actions.

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
│   ├── competition.py  # Rankings and title commands
│   ├── profile.py      # /profile and records screens
│   ├── joust.py        # /joust challenge, /joust duel, presentation and debug embeds
│   ├── knight.py       # /knight commands and knight builder UI
│   └── menu.py         # /menu and /help_joust
│
├── services/
│   ├── arenas.py       # Arena definitions
│   ├── balance.py      # v0.5 tunable combat constants
│   ├── progression.py  # Gold, unlocked sidegrades and standards
│   ├── competition.py  # Leaderboards/title rules
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
