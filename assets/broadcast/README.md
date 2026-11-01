# JoustingBot Broadcast Art Slots (v0.9.2)

These are OPTIONAL. The bot generates a 1200 x 675 introduction image and final scoreboard on every match if Pillow is installed. A missing art file or URL does not block a joust.

## Replace the generated background

Add any of these real 16:9 PNGs in this folder:

- `intro.png` — shared intro background
- `final.png` — final scoreboard background
- `arena_royal_lists.png`, `arena_muddy_field.png`, `arena_frozen_ground.png`, `arena_wind_swept.png`, `arena_festival_arena.png`, `arena_war_torn.png` — arena backgrounds (higher priority for both entrance/final cards)

The compositor darkens backgrounds and overlays names, knight crests, score, horse names and match statistics. It never requires portraits or character art. Keep background images legible under text.

## Staged motion/media

Edit `manifest.json` and fill in HTTPS links to hosted PNG, JPG, GIF or other Discord-supported images:

- `approach`, `charge`, `impact`, `aftermath`
- `impact_unhorsing`, `impact_lance_break`, `impact_heavy_shield_hit`, `impact_saddle_stagger`, `impact_clean_miss`, `impact_horse_refusal`, `impact_horse_slip`
- Arena overrides: `royal_lists_approach`, `muddy_field_charge`, etc.
- `intro` and `final` are optional remote fallbacks if generated PNG rendering fails.

The resolver prioritises an impact-specific clip, then an arena/stage clip, then the general stage asset. No empty images, filenames or made-up links are posted.

**Important:** The bot does not convert image files to animated GIFs. To get motion, create and host real GIFs or use your chosen media provider and paste their direct HTTPS URLs into the manifest. Animated images should loop cleanly and be short.

## Config (environment variables)

- `JOUST_BROADCAST_ENABLED=true` — set to `false` to skip the live pass animation and send intro/final only.
- `JOUST_BROADCAST_STAGE_DELAY=0.85` — seconds per stage edit (clamped to 0.35–2.5), balancing theatre against Discord rate limits.
- `JOUST_BROADCAST_REDUCED_MOTION=true` — show one static final-pass summary without repeated live-screen edits, followed by the full final scoreboard.

The graphical card contains all dynamic text; do not burn the knight names or scores into the background PNGs.


## v2.9.3b — Winner-specific final scorecards

The final screen now checks for these two **optional** local PNGs:

```text
assets/broadcast/final_blue_win.png
assets/broadcast/final_red_win.png
```

Extract `Jousting_Bot_v2.9.3b_Final_Scorecards.zip` in the project root after pulling the v2.9.3b Python code. The original 1672×941 designs are preserved without the dark overlay used by the older generic illustration.

**Blue left, red right:** fighter B (blue) appears on the left and fighter A (red) on the right. The winner determines which template has its pre-drawn WINNER ribbon. Passes = recorded passes; Lance Breaks and Unhorsings = awarded actions per fighter; Injuries = new injuries sustained in this particular match; Impact Score = final *awarded joust points*, because the match log does not store cumulative raw impact force. Arena, Format and Seed use recorded match metadata.

For draws, missing PNGs or corrupt images, the renderer keeps the existing neutral scorecard. No match calculations or stored statistics are altered. When deployed on Railway, the two art files must be included in the deployed GitHub checkout; downloading them to a local PyCharm project alone will not supply them to Railway.
