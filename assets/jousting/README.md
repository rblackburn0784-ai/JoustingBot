# v0.9.2a — Jousting sprite assets

Copy the separate `JoustingBot_v0.9.2a_Asset_Overlay.zip` into the root of the current GitHub project. The overlay contains artwork only, not old source files or player saves.

Asset folders:
- `arenas/`: six side-on arena PNGs named `royal_lists.png`, `muddy_field.png`, `frozen_ground.png`, `wind_swept.png`, `festival_arena.png`, `war_torn.png`
- `horses/{Bay,Black,Chestnut,Grey,White}/{Idle,Gallop,Rear,Refusal,Slip}/`: numbered frame PNGs, e.g. `gallop_01.png`
- `knights/{red_knight,blue_knight}/{idle,gallop,impact,lower_lance,unhorsed}/`: numbered *directional* frames, e.g. `red_knight_gallop_right_01.png` or `blue_knight_gallop_left_01.png`
- `crowd/{idle_1,idle_2,cheer,boo,applause}.png`: transparent side-on strips
- `effects/animation_frames/{dust_1,dust_2,splinter,impact_flash,stars}/`: numbered effect PNGs
- `props/{lance,broken_lance,shield,barrier}.png`: foreground and equipment layers

The renderer explicitly rejects preview sheets and `_strip` frames. Knights use separately drawn directional art; the horses are mirrored to face each other. Art can be swapped without changing the Python source.

`visual_mapping.json` defines the default *appearance* of each existing breed (Courser → Bay, Destrier → Black, Rouncey → Chestnut, Palfrey → Grey, Charger → White). It does not change horse statistics. `player_coats` can map user IDs to different coat colours.

After merging the artwork, run `python -m unittest discover -s tests -v`, then try a match in Discord. Set `JOUST_SPRITE_ENABLED=false` to fall back to the v0.9.2 embed broadcaster. Generated animations are stored under `storage/renders/` and are never required to reproduce combat results.

**The old one-off installer is NOT needed** for the current GitHub version. Simply update GitHub code and extract the art overlay.


## v2.9.3 — Sprite layout calibration

`assets/jousting/scene_layout.json` is committed as a lightweight, editable starting point for **your locally installed PNGs** (no binary art is uploaded). The live broadcast renderer uses a **960×540** frame. After `git pull origin main`, restart the bot to load your edits. Change values incrementally:

- `horse_top` (159): horse and rider move vertically together; *lower values = higher on the field*
- `knight_scale` (0.90): knight size without changing mount size or equipment
- `rider_foot_clearance` (69): where the scaled knight sits relative to the horse
- `barrier_top` (349): central rail height; scene order is **blue → barrier → red**
- `lance_raised_degrees` (46): raised angle for PREP/GALLOP; both lances rotate around the same hand grip position
- `lance_lowered_degrees` (0): ready/collision horizontal angle
- `lance_hand_offset_x` (28) and `lance_hand_fraction_y` (0.53): lance grip anchor relative to rider centre and height
- `crowd_stands`: 3 `[x, y, width, height]` zones for the left, centre and right pavilions; each cropped section of your transparent crowd image stays inside its respective zone

The 3 crowd zones are calibrated for the Royal Lists screenshot. Other backgrounds share them; you may adjust these once you compare against your exact art. The default values keep scene drawing inside bounds. Invalid settings fall back to the bundled defaults rather than break a joust.

The original `PASS 1 · PREP` box is gone. The score/name strip and lower textual commentary remain. The renderer does not modify saved joust logs, award prizes, alter scoring, create duplicate animations or change existing PNG sprites. Run tests with:

```powershell
python -m unittest discover -s tests -v
```

