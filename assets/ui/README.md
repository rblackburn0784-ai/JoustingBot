# v0.9.2d — illustrated Discord screens

## v2.9.2f — Earned title standards and arena banners

Download `Jousting_Bot_v2.9.2f_Banner_Art_Pack.zip`. From the root of your updated GitHub checkout, extract it so it creates:

```text
assets/title_banners/01_the_unhorsed.png
assets/title_banners/02_shield_splitter.png
...
assets/title_banners/27_marshals_favourite.png
...
assets/title_banners/30_arena_conqueror.png
```

All 30 original transparent PNGs are included in the separate artwork ZIP; they are not pushed to GitHub automatically. The renderer also accepts the original archive's `title_banners/` subfolder at the project root if you've already extracted it.

The **Your Title Collection** page automatically renders a 1280×720 royal-blue title gallery with the saved equipped banner on the left and currently browsed title on the right. Locked candidates are labelled locked. **Equip Selected** and **Unequip** update `storage/titles.json` using the existing earned-only `set_title()` API; a separate `equipped_banner_key` is deliberately *not* added because it could conflict with the player's real equipped title.

The **Arena** and **Challenge** preview artwork places a small equipped banner at the far end of each of six arenas. Positions can be tuned in `services/banner_art.py → ARENA_ANCHORS`; these do not affect joust animation sprites or combat physics. No chosen title, a missing banner PNG, or a removed/unearned title selection produces a **neutral plain blue-and-gold** fallback. Never substitute a locked title reward as the default.

For Railway or other cloud deployment, commit the 30 PNGs into your deployment checkout after extracting. Local PyCharm artwork does not transfer to Railway on its own.

## v2.9.2e — Tournament Hall, History & Trophy Cabinet

The ZIP `Jousting_Bot_v2.9.2e_Tournament_Visual_Pack.zip` contains the three user-supplied tournament backgrounds, with correct filenames and installation paths:

```text
assets/ui/tournament.png
assets/ui/tournament_history.png
assets/ui/trophy_cabinet.png
```

Extract it into the root of your checked-out GitHub project after `git pull origin main`. Do not put the three files under `assets/jousting/` or `assets/ui/arenas/`; these tournament screens look directly in `assets/ui/`.

- `/menu → Tournaments`: Tournament Hall scene, including when no tournament is active
- `/menu → Tournaments → History`: History scene with ten recent completed events, Refresh History and return buttons
- `/menu → Tournaments → Trophy Cabinet`: Trophy room scene across Achievements, Titles and Career Medals tabs
- `/tournament history`, `/tournament cabinet`, `/tournament achievements` and the public tournament History/Cabinet buttons: private illustrated views

Screens keep their existing interactive Discord components and database-driven information. When the art is not installed, the renderer safely produces text-only embeds. If running the bot on Railway, commit and push these PNGs so they are included in the deployed checkout; files present only on your desktop will not appear on Railway.

The seven original full-resolution PNG backgrounds are distributed separately, rather than embedded in the Python source. The updated installer accepts **either of the ZIP files supplied with v2.9.2d**, including artwork nested in subfolders:

- `Jousting_Bot_Setup_PNG_Pack_v2.zip` (original standalone artwork)
- `Jousting_Bot_v2.9.2d.zip` (complete release package)

From your GitHub checkout, check and then install the backgrounds directly from the downloaded ZIP:

```powershell
python tools/install_ui_art_v092d.py --source "C:\Downloads\Jousting_Bot_v2.9.2d.zip" --check
python tools/install_ui_art_v092d.py --source "C:\Downloads\Jousting_Bot_v2.9.2d.zip"
```

The installer automatically maps `equipment_setup.png` to `shop.png` and `knight_setup.png` to `knight.png`, preserves all five horse-colour filenames, validates each image, and writes **only** the seven artwork files under `assets/ui/`. It never overwrites `.env` or any `storage/` records.

You can also pass a folder containing these files (including nested folders), or install already-renamed `shop.png` / `knight.png` assets. Missing PNGs do not stop gameplay; the Shop, Knight and Horse menus fall back to functional text controls.

The binary artwork is not checked into GitHub, so a fresh Git checkout requires this one-time installation.

## Arena previews and Injury Ward (v0.9.2d scene patch)

From **/menu → Arenas**, selecting any arena now replaces the same Discord menu message's image with that arena background. **Random Arena** refreshes the preview too. The **Challenge** screen also follows its selected arena. The displayed name, description, and existing modifiers come from `services/arenas.py`, unchanged.

Place each original arena background in `assets/ui/arenas/` using its arena key:

```text
assets/ui/arenas/royal_lists.png
assets/ui/arenas/muddy_field.png
assets/ui/arenas/frozen_ground.png
assets/ui/arenas/wind_swept.png
assets/ui/arenas/festival_arena.png
assets/ui/arenas/war_torn.png
```

Existing artwork already placed in `assets/arenas/`, `assets/jousting/arenas/`, `assets/jousting/arena/`, `assets/jousting/` or `assets/ui/` is also recognized by its exact filename. No new arena artwork is generated by this change.

The **/menu → Injuries** and equipment **Injury Ward** screens use `assets/ui/injury_ward.png`. Extract the supplied `Jousting_Bot_Injury_Ward_Art.zip` into the project root to install the original provided ward room background. All injury details, treatments and gold handling remain in the existing embed and controls.

The artwork is optional. If missing, the screens remain functional with text-only embeds. Discord selection callbacks acknowledge interactions before rendering. When running on Railway, the PNGs must also exist in the deployed build (for example, commit them alongside the code), rather than only on the developer PC.

## Which image appears?

- `/menu` → **Shop** → `shop.png` (the shopkeeper behind the counter). Browsing/purchasing items shows the shop scene. Buying uses the unchanged `services.progression.buy` eligibility, unlocks and gold balance checks. Purchases never auto-equip.
- `/menu` → **Knight** and Knight **Equip Lance/Equip Armour** → `knight.png` (white-armoured knight, lance and shield). The two currently implemented equipment slots are labelled in the empty equipment panels.
- `/menu` → **Horse** and **Manage Stable** → `horse_{colour}.png` for the selected horse. The coat follows `assets/jousting/visual_mapping.json` (Courser=Bay, Destrier=Black, Rouncey=Chestnut, Palfrey=Grey, Charger=White). The **Coat Colour** button can override each horse's visual appearance, saved in its horse record as optional `visual_coat`; statistics and breed do not change.
- **Equip Horse Barding** → the matching horse screen; **Equip Armour/Lance** → the knight screen. Equipment selectors sit below the image and refresh the same private Discord message.

## Equipment art in a future release

The eight labelled panel locations on the Knight and Horse images are reserved for future equipment layers. v0.9.2d displays current equipment names for the actual supported gear categories (Knight lance/armour, Horse barding). Other illustrated categories such as bridles, saddles, horseshoes, helmets, shields, gauntlets, leg armour, cloak and accessories are marked **COMING SOON**; no unimplemented items or invented stat bonuses are sold.

New appearance changes are visual metadata only. Gameplay data, purchases, gold, progression, training, injuries, tournaments, score calculation and your existing joust animation asset tree are untouched.

Images are resized to 1280×720 and compressed to a lightweight JPEG **at display time only**. Original PNGs stay untouched on disk. A cache invalidates when source image modification times change. Art render uses `asyncio.to_thread` so buttons are acknowledged promptly.
