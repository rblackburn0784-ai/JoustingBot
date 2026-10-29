# v0.9.2d — illustrated Discord screens

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

## Which image appears?

- `/menu` → **Shop** → `shop.png` (the shopkeeper behind the counter). Browsing/purchasing items shows the shop scene. Buying uses the unchanged `services.progression.buy` eligibility, unlocks and gold balance checks. Purchases never auto-equip.
- `/menu` → **Knight** and Knight **Equip Lance/Equip Armour** → `knight.png` (white-armoured knight, lance and shield). The two currently implemented equipment slots are labelled in the empty equipment panels.
- `/menu` → **Horse** and **Manage Stable** → `horse_{colour}.png` for the selected horse. The coat follows `assets/jousting/visual_mapping.json` (Courser=Bay, Destrier=Black, Rouncey=Chestnut, Palfrey=Grey, Charger=White). The **Coat Colour** button can override each horse's visual appearance, saved in its horse record as optional `visual_coat`; statistics and breed do not change.
- **Equip Horse Barding** → the matching horse screen; **Equip Armour/Lance** → the knight screen. Equipment selectors sit below the image and refresh the same private Discord message.

## Equipment art in a future release

The eight labelled panel locations on the Knight and Horse images are reserved for future equipment layers. v0.9.2d displays current equipment names for the actual supported gear categories (Knight lance/armour, Horse barding). Other illustrated categories such as bridles, saddles, horseshoes, helmets, shields, gauntlets, leg armour, cloak and accessories are marked **COMING SOON**; no unimplemented items or invented stat bonuses are sold.

New appearance changes are visual metadata only. Gameplay data, purchases, gold, progression, training, injuries, tournaments, score calculation and your existing joust animation asset tree are untouched.

Images are resized to 1280×720 and compressed to a lightweight JPEG **at display time only**. Original PNGs stay untouched on disk. A cache invalidates when source image modification times change. Art render uses `asyncio.to_thread` so buttons are acknowledged promptly.
