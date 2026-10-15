# JoustingBot

A lightweight medieval jousting Discord game bot built with `discord.py`.

**Current version:** `v0.9.2 — Cinematic Matchday Broadcast`

Players create a knight, build and bind a horse, equip both rider and horse, choose an arena, and challenge other Discord users to cinematic jousts with accept/decline buttons.

This version adds cinematic stage-by-stage Discord commentary and generated entrance/final scoreboard PNGs. All v0.9.1 tactics, seeded combat, history, tournaments, progression, injuries and admin safeguards remain intact.

---

## v0.9.2 — Cinematic Matchday Broadcast

Each joust now has a staged replay of one authoritative saved combat result. Scoring, RNG, reward calculations and injury events are unchanged.

### Presentation sequence

1. **Entrances** — automatically generated 1200×675 PNG, each knight and mount introduced by the herald, arena backdrop, and both tactical plans.
2. **Approach** — arena atmosphere and riding styles; no premature outcome announcement.
3. **Charge** — chosen lance targets, current fatigue and activated special manoeuvres.
4. **Impact** — the recorded result, including misses, heavy hits, splintered lances and unhorsings, with optional outcome-specific GIF.
5. **Aftermath** — the marshal awards points and updates the running score.
6. Repeat stages 2–5 once for every actual pass. The match can conclude before the maximum of five passes.
7. **Final** — generated 1200×675 scoreboard PNG with both riders, points, winner/tie, lance breaks, unhorsings, heavy hits and seed, plus full accessible text, match ID and injury report.

Only ONE editable Discord message is used for the entire pass-by-pass presentation. The intro and final result are separate messages. All frames come from the already-completed seeded match; no frame ever re-simulates combat. If a media upload or stage edit fails, the recorded result is preserved and the final card is still attempted.

### Media placeholders

You do not have to add artwork. Pillow renders an attractive fallback card and scoreboard.

For additional backgrounds and highlights, see **[assets/broadcast/README.md](assets/broadcast/README.md)** and **[assets/broadcast/manifest.json](assets/broadcast/manifest.json)**.

- Copy your custom 16:9 backgrounds into the broadcast assets directory as intro.png, final.png, or arena_royal_lists.png, arena_muddy_field.png, arena_frozen_ground.png, etc.
- The bot overlays dynamic names, heraldry, tactics, scores and statistics itself. Leave text off the background art.
- Fill direct HTTPS URLs in the media manifest for approach, charge, impact, aftermath, impact_unhorsing, impact_lance_break, impact_horse_slip and other relevant events.
- Unfilled asset slots are ignored. URL validation prevents accidentally displaying local paths or insecure links. No GIFs are required to run the game.

### Configuration

Add these to your .env or host environment:

~~~dotenv
JOUST_BROADCAST_ENABLED=true
JOUST_BROADCAST_STAGE_DELAY=0.85
JOUST_BROADCAST_REDUCED_MOTION=false
~~~

- The stage delay is clamped from 0.35–2.5 seconds. Discord rate limits may impose extra delay.
- Reduced-motion mode displays one static final pass summary and no stage edits.
- Disabling the broadcast preserves the original quick intro/final result flow (with a generated final scoreboard).

The source is divided into services/broadcast.py (pure playback planner), services/broadcast_art.py (PNG renderer), and cogs/broadcast.py (Discord delivery). The playback module does not write storage, create awards or run combat.

The tests verify unique frames, scoring integrity, stage order, no spoilers before impact, renderer image dimensions, HTTPS media fallbacks, reduced motion and that a broken broadcast cannot re-run or re-award a match.

---

## v0.9.1 — Combat Tactics & Decisions

Players now directly influence competitive jousts without taking control of the RNG. Each accepted **/joust challenge** has a **Choose Tactics** button:

1. The challenger issues a public challenge (by /joust challenge or /menu → Challenge).
2. **Both knights** press **Choose Tactics**. Each receives a **private ephemeral editor** with three dropdowns.
3. Each chooses a **riding style**, **lance target**, and optional **special manoeuvre**, then presses **Lock Tactics**.
4. The public card shows only ✅ Locked / ⌛ Choose Tactics, **never the choices themselves**.
5. After **both** have locked, the invited opponent may press **Accept Challenge**. The match opens with both strategies revealed and concludes with the pass-by-pass chronicle. Challenges expire after **240 seconds**.
6. Once one rider locks, the arena cannot be changed. Riders may reopen the private editor and change their own choices until the duel is accepted.

Declines and expired challenges do not create completed matches or affect character statistics. All standard single-duel locks and cooldowns remain in force. **Admin instant-test duels and existing admin-run tournament matches use a neutral default (Balanced / Shield / No Manoeuvre)** and continue to work without an interactive tactics step. Tournament-specific tactical registration may be introduced separately.

### Riding styles

| Style | Effect | Trade-off |
| --- | --- | --- |
| Cautious | +2 alignment, gentler horse handling, −4 percentage points to personal injury risk | −1 charge; builds no fatigue per pass |
| Balanced | No immediate skill bonus/penalty; normal mount behaviour | +1 fatigue per pass |
| Aggressive | +2 charge, higher impact potential | −3 alignment, +3 fatigue per pass, +5 percentage points to personal injury risk; nervous mounts are less reliable |

### Aim your lance

| Target | Effect |
| --- | --- |
| Shield | Standard target and scoring |
| Lance | +2 alignment, −1 charge; converts successful heavy-hit/stagger events into one-point lance breaks rather than two-point hits |
| Rider | −2 alignment, +1 charge; +3 percentage points to the struck rider's injury risk on a qualifying hit |

### Optional manoeuvres

| Move | Advantage | Cost / cooldown |
| --- | --- | --- |
| No Manoeuvre | Normal jousting | No effect |
| Precision Strike | +3 alignment | −1 charge |
| Reckless Charge | +2 charge | −3 alignment, extra fatigue, increased injury risk to both involved riders |
| Shield Brace | +3 unhorsing resistance, +1 alignment | −1 charge |
| Feigned Miss | +2 alignment; also disrupts an Aggressive opponent's alignment by −2 while active | −1 charge; offers no disruption against Balanced/Cautious riders |
| Last Stand | +2 alignment and +2 charge in a comeback | Available **on pass 3 only** when trailing or fatigued; adds extra fatigue and risk |

Manoeuvres have a **two-full-pass cooldown**. Standard moves may activate on pass 1 and again on pass 4 if the match continues; a match may finish before a later activation. Last Stand is deliberately conditional and activates at most once. Players select their preferred manoeuvre ahead of the match; activation and cooldown are handled automatically rather than requiring five separate Discord prompts.

### Fatigue, temperament and safety

Aggressive charges accumulate more fatigue than Balanced; Cautious gains none. Fatigue penalises charge and alignment over subsequent passes and increases the mount-handling difficulty. A horse with high stamina partially mitigates fatigue, while a nervous or disobedient horse has greater chances of poor behaviour under Aggressive riding.

Injury odds still incorporate **arena, armour, lance, barding and horse breed**, plus the rider's current style, fatigue and dangerous manoeuvres. Existing injury severity, natural healing, capped total effective stat penalties and treatment tiers remain unchanged. The combat engine remains **seeded and reproducible**: the saved match JSON records each rider's tactical plan and the per-pass style, target, move activation, fatigue and roll details. Legacy match records do not need migration.

The automated balance suite performs seeded equal-stat match comparisons of Cautious, Balanced and Aggressive builds (including both seat orders), checking that no tested combination overwhelms the others. This is a useful guardrail, not a guarantee about every equipment/arena combination.

---

## v0.9.0a — Server Safety & Admin Cleanup

### Quick setup (Python 3.12 or compatible)

For a fresh installation, clone the repository; for an existing installation use git pull. Then install dependencies:

```bash
git clone https://github.com/rblackburn0784-ai/JoustingBot.git
cd JoustingBot
python -m pip install -r requirements.txt
```

For an existing checkout, run `git pull` inside the project folder before starting the bot.

Create a local .env file with DISCORD_BOT_TOKEN=<token>, invite the bot with applications.commands and bot permissions, and run:

```bash
python main.py
```

Do not commit your token or any saved JSON records. Keep ONE running bot process and use a persistent storage directory on hosts such as Railway. Run /version and /menu in your Discord server to verify the install.

### New restricted administrator commands

| Command | What it does | Safety |
| --- | --- | --- |
| /admin panel | Open the private admin dashboard | Rechecks Manage Server permission |
| /admin health | Inspect stored JSON data and highlight issues | Read-only |
| /admin backup | Create an integrity-checked snapshot | Locks against active matches; local SHA-256 manifest |
| /admin repair | Preview conservative repairs | Requires explicit confirmation and a safety backup |
| /admin reset_user member scope | Reset a selected member's guild equipment settings or inventory | Typed confirmation, backup, admin audit |
| /maintenance | Legacy button-based admin maintenance interface | Still available |
| /version | Show current release and hardening features | Available to everyone |

The **Admin** menu remains hidden from ordinary users. Commands additionally check authorisation at execution time. Actions are unavailable during active jousts or tournament match operations within the running process.

### Reset User: two safe scopes

Use /admin reset_user member:@Member scope:settings (the default) or scope:inventory. A private review screen identifies the target, scope and effects. The admin must click Confirm Reset and type RESET followed by the member's numeric Discord ID.

- **Settings:** remove their active guild-specific lance/armour/barding selections, cosmetic standard and equipped title. Previously purchased equipment remains owned.
- **Inventory:** do everything Settings does, and retire the member's purchased unlockable equipment for **this server only**. There is **no gold refund**; retired purchases remain in the spending ledger, so players cannot gain extra gold by repeating a reset.

**Both scopes deliberately preserve** historical match results, leaderboard results, earned-title eligibility, unspent earned gold, previously spent healing gold, injury history, tournaments, globally shared knight and horse records, and data from other Discord servers. This is a *guild settings and inventory reset*, not a destructive character/history wipe. It does not zero the leaderboard.

Every successful reset produces a verified backup and appends an admin action record to storage/admin_audit.json. The audit records actor ID, target ID, guild, scope, time, planned changes and backup name. To reverse a reset, an administrator would need to restore the whole verified snapshot—never perform this lightly.

### File safety and recovery

- Individual JSON writes are staged into unique temporary files, flushed, synchronised and atomically renamed; POSIX hosts also sync the containing directory when possible.
- Startup warns about invalid or missing files without replacing corrupt JSON.
- /admin repair can initialise missing files/top-level containers and deduplicate identical match IDs only. Conflicting IDs or corrupt JSON are refused rather than guessed or erased.
- /admin backup and /maintenance restore use SHA-256 manifests. Data snapshots are LOCAL only. Copy them off-host.
- All seven recognised data files are: knights.json, horses.json, matches.json, titles.json, progression.json, tournaments.json and admin_audit.json.
- Single-process locks/cooldowns prevent multiple overlapping jousts or concurrent maintenance in this bot instance. They do NOT coordinate multiple replicas or make cross-file saves transactional.
- Regression tests cover admin permissions, reset confirmation, cross-server isolation, no-refund gold integrity, audit backups, recovery and command registration.

**Server deployment checklist:** configure a persistent volume, restrict Manage Server permissions, keep your token in environment secrets, run exactly one bot instance, check /admin health, create /admin backup and retain off-host copies. Test /joust challenge with two players before a public tournament.

---

## v0.9.0 — Stability & Admin Tools

This release hardens saved game data, challenge safety, Discord error handling and administrator workflows. It keeps the same knight, horse, injury, equipment, title, leaderboard and tournament data formats—**no reset or manual migration is required**.

### New slash commands

| Command | Permission | Purpose |
| --- | --- | --- |
| /version | Everyone | Display the running release and its stability features |
| /maintenance | Manage Server only | Open the private admin storage maintenance control panel |

Open /menu → **Admin** → **Maintenance Tools** to reach the same controls by buttons. Non-admins cannot open or act on the panel. Each admin action independently verifies permissions. The interface includes **Validate**, **Create Backup**, **Review Repairs**, **Restore Selected**, **Admin Dashboard** and **Main Menu**. Restore and actual repairs require a separate confirmation page.

### Backups and restores

Backups are stored in dated local directories under backups/ and include the six known storage files when they exist:

- knights.json, horses.json, matches.json
- titles.json, progression.json, tournaments.json

Each snapshot has a manifest with **SHA-256 hashes**. Backups are verified after creation and again before restore. A failed checksum or invalid JSON structure blocks restore. Backup identifiers are strictly validated, rejecting directory traversal or arbitrary paths.

Restore creates an additional **pre-restore safety snapshot**. If the current file is corrupt, the bot saves its raw bytes in a quarantine directory so it can still restore a previously verified healthy snapshot. Restores and repairs are blocked while the current process has an active joust or tournament match. These snapshots remain **on the host**, not in GitHub or a remote service. Maintain separate off-host backups and a persistent disk/volume, particularly for Railway deployments.

**Operational caution:** Restoring overwrites files present in the selected snapshot, but does not erase unrelated files or files absent from that backup. This is a controlled local file restore, not a cross-file database transaction; do not restore while a second copy of the bot is running.

### Validation and conservative repair

The admin **Validate** panel reports present/missing JSON files and schema/type errors, duplicate match IDs and unusual tournament state. **Review Repairs** shows only a dry-run plan; the bot never applies it without a separate button confirmation.

The **Confirm Repair** action can initialize missing JSON files, restore missing top-level containers and remove *identical* duplicate match entries while retaining all other fields. It creates a verified safety backup first. Malformed JSON, conflicting match IDs or complex bracket corruption are intentionally not auto-repaired: the admin must inspect the damaged data and restore a known-good snapshot if necessary. There is no automatic destructive reset.

### Challenge cooldowns, locks and error cleanup

- New challenges have a **30-second per-initiator, per-server posting cooldown**, enforced by both /joust challenge and the main-menu Challenge buttons. Rejected posts do not start the cooldown.
- A synchronous atomic lock prevents a rider being reserved for multiple live duels. Tournament matches, public challenges and instant admin test duels use the same reservation path.
- On declines, timeouts, failed challenge posts, completed jousts and handled Discord errors, locks are released. Tournament bracket/match journal restart recovery remains available.
- Global slash-command error handling reports permission/cooldown problems privately and logs unexpected errors with a short reference ID, without showing internal tracebacks to players.
- JSON writes now use **unique temporary files, fsync, and atomic os.replace**, preventing concurrent temporary filenames or torn individual JSON writes on supported filesystems.

### Limitations

The bot still assumes **one running application instance** writing to its persistent storage. Per-file atomic writes do not make a multi-file restore transactional; nor do they provide distributed locking or automated cloud backups. The in-memory challenge cooldown and pending public challenge timers reset when the bot process restarts. Tournament brackets and records remain persisted. New automated tests exercise backup/restore checksum enforcement, corrupt-file quarantine, safe repairs, challenge locks/cooldowns, admin permissions and command error messages.

---

## v0.8.5a — Tournament Titles & Achievements

Tournament Lite now awards **12 new equipable tournament titles and 8 achievement badges**. The title collection contains **30 titles** in total (the previous 18 plus the new 12). Existing titles and equipment remain unchanged. These rewards are cosmetic: they never alter knight stats, horse stats, injury risk or tournament seeding.

### Twelve new tournament titles

| Title | Requirement |
| --- | --- |
| Lists Initiate | Enter one started tournament |
| Bracket Breaker | Advance through 3 tournament matches |
| The Finalist | Compete in a completed tournament final |
| Silver Lance | Finish a tournament as runner-up |
| Cup Bearer | Win one tournament |
| King of the Lists | Win 3 tournaments |
| Elite Eight | Enter a started 8-rider tournament |
| Grand Melee Champion | Win an 8-rider tournament |
| Marshal's Favourite | Advance after a seeded marshal's tie-break |
| Tourney Veteran | Enter 5 started tournaments |
| Lance of the Lists | Unhorse 3 opponents in tournament matches |
| Arena Conqueror | Win tournament jousts in 3 different arenas |

### Eight achievement badges

| Achievement | Requirement |
| --- | --- |
| First Entry | Join a tournament that has actually started |
| Opening Victory | Advance from your first tournament pairing |
| Centre of the Lists | Compete in a completed final |
| Raise the Banner | Win a tournament championship |
| A Noble Defeat | Finish as runner-up |
| Grand Melee | Compete in an 8-rider tournament |
| Still Standing | Win a tournament joust while already injured |
| Tournament Splinters | Break 5 lances in tournament matches |

**Titles** may be equipped and appear on the player's profile and server leaderboards. **Achievement badges** are permanent recognitions shown in the Tournament Trophy Cabinet, not additional equippable titles. Both show locked/unlocked state and actual progress.

### Commands and buttons

- \`/tournament achievements\` — private interactive achievement cabinet; optionally pass \`player:@Member\` to view another rider's progress.
- \`/tournament cabinet\` — open your tournament medal and career-stat screen.
- \`/titles\` or \`/title equip\` — see and equip all 30 titles, including tournament titles.
- \`/menu\` → **Tournaments** → **Trophy Cabinet** — browse achievements, tournament titles, and career medals with Home navigation.
- The public tournament control panel also includes a **Trophy Cabinet** button that opens a *private* personal screen.

The title dropdown now displays six titles at a time rather than attempting to exceed Discord's 25-choice limit. The \`/title equip\` command uses name-search autocomplete so every title remains selectable. The player profile also displays tournament crowns, silver finishes, entry counts and unlocked award totals.

After a completed tournament pairing, the bot automatically announces newly earned tournament titles and achievements for either competitor. Champions and runners-up can both earn honours.

### Progression safety and persistence

Tournament awards are calculated from **verified completed brackets** and the corresponding guild-specific match-journal results. Ordinary duels, admin test matches, registrations that never start, duplicate match records, and tournament records from other Discord servers cannot grant these trophies. Seeded marshal tie-breaks count as a bracket advance but do not change the underlying joust's draw result.

Awards are associated with Discord member IDs, so changing a knight's name does not reset them. Tournament history is now retained indefinitely rather than discarding completed events after 20, preserving long-term achievement progress. History screens still limit how many older events they display.

Back up \`storage/tournaments.json\`, \`storage/matches.json\`, and \`storage/titles.json\` together using the existing admin backup feature; no data migration or reset is required.

---

## v0.8.5 — Tournament Lite

A deliberately small, **one-at-a-time single-elimination tournament** for each Discord server. Choose 4 or 8 riders. No leagues, seasons, divisions, substitutions or complicated seeding rules yet.

### Commands

| Slash command | Who may use it | Purpose |
| --- | --- | --- |
| /tournament create name:<name> size:<4 or 8> | Manage Server admins | Create and open registration |
| /tournament join | Players | Register your own knight and bound horse |
| /tournament start | Manage Server admins | Randomly seed a full 4/8-player bracket |
| /tournament status | Everyone | Public tournament registration / live bracket |
| /tournament next | Manage Server admins | Run the next pairing and advance the winner |
| /tournament history | Everyone | View the last ten champions |

Every player must own a knight with a bound horse and must join voluntarily. No bots or duplicate registrations. Registration cannot exceed event capacity, and an admin cannot start until the bracket is full. **Only one active tournament per server** can exist at a time. A new tournament may be created after its predecessor finishes.

When the admin starts, the bot randomly seeds registered players and allocates one arena and deterministic seed per pairing. Each press of **Start Next Match** plays one cinematic joust and advances its winner. After the final, the bot announces the **champion** publicly and moves the completed event into server tournament history. There are three matches in a 4-player tournament or seven in an 8-player tournament.

**Tie rule (Tournament Lite only):** A level result is resolved by a deterministic seeded marshal's decision for bracket advancement, which is announced. The underlying joust remains a draw in normal career statistics. A full overtime/sudden-death ruleset is outside v0.8.5's scope.

### Buttons and permissions

Use /menu → **Tournaments** for a private, button-based tournament dashboard (Join, Refresh, History). Admins also see **Create**, **Start** and **Start Next Match**. Admin-only Tournament Director is also accessible from /menu → **Admin**. Administrators may create an event from a modal.

The public status message includes **Join Tournament**, **Start Tournament**, **Start Next Match**, **History**, **Refresh** and **Main Menu** buttons. The bot checks **Manage Server** on every admin action (including button clicks); public controls cannot grant admin access. Public button handlers are restart-persistent; returning to Main Menu always opens a private dashboard.

### Progression and persistence

**Registering is consent to tournament jousts**: there is no Accept/Decline step for each pairing. Tournament jousts use the existing combat system and count as competitive matches, including the existing equipment, title, gold and injury mechanics. Running admin test duels separately remains unranked.

State and bracket history are stored in storage/tournaments.json. Each bracket pairing has a stable match ID, seed and arena. If the process is interrupted, the admin can press **Start Next Match** again; the bot checks the match journal before resimulating or advancing, preventing duplicate match awards or injury records. All tournament JSON is included in the Admin backup/health checks.

**Operational limits:** v0.8.5 supports a single running bot instance and local/volume-backed JSON files. Keep storage/matches.json and storage/tournaments.json together on the same persistent disk (for example, a Railway volume). If an unplayed pairing loses a member or valid mount, the admin needs to resolve the entry before play; advanced forfeit/substitution tooling belongs in a later update. The bot does not schedule matches automatically.

---

## v0.8.1a — Contextual Injuries & Tiered Recovery

Injury risk now depends on the **arena, impact, defender's armour and barding, attacking lance, mount breed, horse handling stats**, and whether the rider is already injured. All percentages are deliberately tuned **in-game balance values**, not real-world medical risk estimates.

### Injury probability modifiers

Each rider's most dangerous qualifying hit received per joust has a single injury roll. Base injury odds are:

| Received event | Starting injury chance |
| --- | ---: |
| Unhorsing | 28% |
| Saddle stagger | 12% |
| Heavy shield hit | 6% |
| Horse slip | 10% |

Arena modifiers (percentage **points**):

| Arena | Adjustment |
| --- | ---: |
| Royal Lists | −3 |
| Festival Arena | −1 |
| Wind-Swept Field | +2 |
| Muddy Field | +5 |
| War-Torn Battlefield | +6 |
| Frozen Ground | +7 |

Other modifications are added to the base risk: heavy/Oakbreaker lances raise injury risk; Tournament/Windrunner lances reduce it. Full Plate or a Reinforced Helm reduces the wearer's risk; Light Plate and a Duelist's Harness raise it. Barding affects footing and protection. Horse breed has a **small** adjustment: Destrier/Palfrey generally offer stability, while Charger/Courser are slightly riskier; unrecognised custom breeds are neutral. High courage and obedience slightly lower injury risk, while low values increase it. Riding while already injured adds **+3 points** of risk.

**Final chance is clamped between 2% and 42%** for any qualifying impact, preventing extreme equipment combinations from making injuries either unavoidable or impossible. Injury-risk previews appear on challenge cards, and injury results list the final chance and applied modifiers.

### Five injury types, variable recovery

| Injury | Stat effect | Base recovery |
| --- | --- | --- |
| Bruised Ribs | Endurance −1 | 24 hours |
| Wrenched Shoulder | Strength −1 | 36 hours |
| Jarred Wrist | Control −1 | 48 hours |
| Twisted Knee | Agility −1 | 32 hours |
| Strained Back | Endurance −1 | 40 hours |

Arena and impact type alter the *relative frequency* of each injury: muddy and frozen terrain favour knee problems; wind favours wrist/shoulder injuries; war-torn arenas favour shoulder/rib injuries; horse slips especially favour knees. Severity is rolled as Light (50%), Moderate (40%) or Serious (10%) and changes recovery duration to approximately 80%, 100% or 135% of the base, respectively. Every injury still affects its chosen stat by only **one point**.

Fairness constraints are unchanged: at most **one new injury per rider per completed match**, no stat can fall below 1 due to injuries, and at most **two total effective penalty points** at once. There are no permanent injuries and no injuries from admin instant-test duels. Injuries heal naturally even when the bot is offline.

### Three treatment providers

| Provider | Gold cost | Maximum time reduction | Failure chance | Temporary aid chance on success |
| --- | ---: | ---: | ---: | ---: |
| Faith Healer | 12 | 8h | 16% | 12% |
| Shady Doctor | 27 | 18h | 9% | 18% |
| Private Doctor | 55 | 30h | 3% | 24% |

A failed treatment **still costs gold** but reduces no recovery time. A successful one shortens natural recovery by *up to* its listed amount. **No treatment may reduce recovery below three hours**, so purchasing care does not instantly cure injuries. When fewer than three hours remain, treatment is unavailable; let natural healing finish. Previous successful treatments already paid for in v0.8.1 remain effective.

A successful treatment also has a small independent chance to grant **physician's aid**: during the **next eligible accepted bout within 24 hours**, if the treated injury is still active, it negates **one** injury stat penalty for that bout. Aid is not consumed by posting, declining or timing out a challenge, is never used in admin instant tests, cannot stack into an extra bonus, and is recorded in the completed match history so it cannot be used again.

### Commands and navigation

Open \`/menu\` → **Injuries**, \`/menu\` → **Profile** → **Injury Ward**, or \`/injuries\`. The injury panel includes dropdowns for **which wound** to treat and **which provider** to use, plus treatment, refresh and Main Menu buttons.

Command-line equivalent:

\`/heal injury_id:<injury_id> provider:<faith_healer|shady_doctor|private_doctor>\`

The provider argument is optional and defaults to Shady Doctor. Existing injuries, gold balances, gear and title records are kept; no data wipe or schema migration is required. New match records preserve horse breed and handling, the injury-risk breakdown and the consumption of any one-bout relief. Payment and recovery records remain in \`storage/progression.json\`; injury snapshots remain in \`storage/matches.json\`. Both are covered by the Admin backup feature.

---

**One-bout anti-stacking rule:** Multiple successful treatments before a match do not accumulate extra bonuses. The first completed accepted joust after treatment consumes all preceding temporary physician support opportunities. Declines, timeouts and instant admin tests do not consume support.

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

## Current capabilities and limits

Working systems include interactive knight/horse creation, gear and equipment sidegrades, arena-specific duels, injury/recovery and three treatment tiers, persistent match history, server leaderboards and titles, gold/prestige/reputation progression, 4- and 8-player tournaments, admin maintenance and recovery controls.

Limitations: JSON persistence targets a **single running bot process**. Snapshots are local unless exported. Active-match locks are held in process memory, and cannot coordinate separate replicas. External media assets remain optional and some visuals are still placeholders. Test real Discord permissions, channel access and button interaction behaviour on your server before announcing a production launch.
