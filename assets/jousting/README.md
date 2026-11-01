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

## v2.9.3a — Field-side banners and grandstand cropping

Pull the latest source code; **retain your existing local arena, horse, knight, prop, crowd and title banner PNGs**. The bot uses them without rebuilding or overwriting them.

`scene_layout.json` now includes the middle-divider calibration:
`barrier_left=56`, `barrier_top=301`, `barrier_width=845`, `barrier_height=92`.
These are 960×540 pixel values, not Discord embed dimensions. Blue riders render behind that rail; red riders render in front.

For the three separate Royal Lists viewing boxes, set:
`crowd_stands=[[35,132,250,62],[356,132,248,62],[675,132,250,62]]`.
If people overlap stands' curved arches, create optional **local** black/transparent PNG masks:
`assets/jousting/crowd_masks/left.png`,
`assets/jousting/crowd_masks/centre.png`,
`assets/jousting/crowd_masks/right.png`.
White/opaque reveals spectators; black/transparent hides them. The masks are resized to their assigned boxes and the crowd is clipped even without masks.

`left_banner_rect=[30,144,69,133]` and
`right_banner_rect=[862,144,69,133]` place the **player's chosen title** to the red/left and blue/right edges. Players without a current earned/equipped title have **no visible banner**. The 12 training opponents instead have fixed cosmetic personality-matched title-art choices; those do not count as earned achievements or affect XP. Install optional artwork from the previous `assets/title_banners/` ZIP for the illustrated versions.

The one-pass animation is now approximately 6.95 seconds instead of ~4.36 seconds. All phases and result timings remain in the original single self-contained GIF; the next pass still edits the same Discord message.

Run tests with `python -m unittest discover -s tests -v`.

## v2.9.3d — Fine-tuning shields, gauntlets and the collision gap

The renderer uses the 960×540 stage coordinates. All local artwork remains intact. The `scene_layout.json` adds three visual-only controls and adjusts two original lance anchors:

- `shield_forward_offset_x: 8` — distance forward from each knight's centre to the near edge of the off-hand shield (mirrored for red/blue)
- `shield_offhand_lift: 35` — how many pixels above the lance grip the shield top is placed
- `lance_hand_offset_x: 20` — horizontal grip offset from the knight centre (was 28)
- `lance_hand_fraction_y: 0.48` — vertical fraction down the knight sprite for the lance grip (was 0.53)
- `collision_closure_px: 18` — additional pixels **per rider** at full contact; smoothly interpolated only after the last 40% of the approach

Lances remain high in the PREP and GALLOP frames and lower during LANCE READY/COLLISION. This alignment places both tips within the opponent's default 50×70 shield area at the collision frame, while not forcing missed/refused/slipped jousts to visibly hit. The values can be changed locally to match different original PNGs. The collision drawing layers and saved stats are unchanged.

