# v0.9.2d — illustrated Discord screens

**The seven PNG backgrounds are intentionally installed on the player's machine, rather than being embedded in the Python source.** Keep the original artwork at full resolution. Save the seven images supplied in chat into a folder with these exact names:

```text
shop.png
knight.png
horse_white.png
horse_bay.png
horse_black.png
horse_grey.png
horse_chestnut.png
```

Copy them to `assets/ui/` OR use:

```powershell
python tools/install_ui_art_v092d.py --source "C:\\path\\to\\downloaded-screens" --check
python tools/install_ui_art_v092d.py --source "C:\\path\\to\\downloaded-screens"
```

Because GitHub's source connector handles UTF-8 text files rather than these binary images, the separate images are **not** included in this repository. Until the PNG files have been copied locally, the Shop/Knight/Horse menus gracefully fall back to text controls (no broken placeholders).

## Which image appears?

- `/menu` → **Shop** → `shop.png` (the shopkeeper behind the counter). Browsing/purchasing items shows the shop scene. Buying uses the unchanged `services.progression.buy` eligibility, unlocks and gold balance checks. Purchases never auto-equip.
- `/menu` → **Knight** and Knight **Equip Lance/Equip Armour** → `knight.png` (white-armoured knight, lance and shield). The two currently implemented equipment slots are labelled in the empty equipment panels.
- `/menu` → **Horse** and **Manage Stable** → `horse_{colour}.png` for the selected horse. The coat follows `assets/jousting/visual_mapping.json` (Courser=Bay, Destrier=Black, Rouncey=Chestnut, Palfrey=Grey, Charger=White). The **Coat Colour** button can override each horse's visual appearance, saved in its horse record as optional `visual_coat`; statistics and breed do not change.
- **Equip Horse Barding** → the matching horse screen; **Equip Armour/Lance** → the knight screen. Equipment selectors sit below the image and refresh the same private Discord message.

## Equipment art in a future release

The eight labelled panel locations on the Knight and Horse images are reserved for future equipment layers. v0.9.2d displays current equipment names for the actual supported gear categories (Knight lance/armour, Horse barding). Other illustrated categories such as bridles, saddles, horseshoes, helmets, shields, gauntlets, leg armour, cloak and accessories are marked **COMING SOON**; no unimplemented items or invented stat bonuses are sold.

New appearance changes are visual metadata only. Gameplay data, purchases, gold, progression, training, injuries, tournaments, score calculation and your existing joust animation asset tree are untouched.

Images are resized to 1280×720 and compressed to a lightweight JPEG **at display time only**. Original PNGs stay untouched on disk. A cache invalidates when source image modification times change. Art render uses `asyncio.to_thread` so buttons are acknowledged promptly.
