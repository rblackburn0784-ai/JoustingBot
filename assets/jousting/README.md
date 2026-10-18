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
