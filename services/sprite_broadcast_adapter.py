"""v0.9.2a: optional dynamic sprite replay of ONE already-recorded match.

Never runs combat, changes match logs, or awards rewards. The caller always
sends the normal final scoreboard, regardless of rendering success.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

LOG = logging.getLogger(__name__)


def sprite_enabled() -> bool:
    return os.getenv("JOUST_SPRITE_ENABLED", "true").strip().lower() not in {
        "0", "false", "off", "no"
    }


async def send_sprite_broadcast(sender, result, prepared) -> bool:
    """Return True if at least one animated clip was successfully posted.

    When a rendering error or missing assets prevents playback, False allows
    the previous v0.9.2 stage broadcaster to take over automatically.
    """
    if not sprite_enabled():
        return False

    import discord
    from services.sprite_engine import ASSET_ROOT, maybe_render_match_media

    # A clean GitHub checkout without separately distributed PNG assets uses
    # the original broadcast, rather than animated placeholder rectangles.
    if not (ASSET_ROOT / "arenas" / (prepared.arena_key + ".png")).is_file():
        LOG.info("Sprite arena PNG unavailable; using cinematic text broadcast.")
        return False

    a, b = prepared.fighter_a, prepared.fighter_b
    ha, hb = prepared.horse_a, prepared.horse_b
    coat_a = getattr(ha, "sprite_coat", None) or getattr(ha, "breed", None)
    coat_b = getattr(hb, "sprite_coat", None) or getattr(hb, "breed", None)
    bundle = await asyncio.to_thread(
        maybe_render_match_media, result, a, b, prepared.arena_key,
        out_stem=f"{getattr(result, 'seed', 'match')}_{a.user_id}_{b.user_id}",
        coat_a=coat_a, coat_b=coat_b,
    )
    if bundle.error:
        LOG.warning("Sprite renderer: %s", bundle.error)
    clips = list(bundle.gif_parts) if bundle.gif_parts else (
        [bundle.gif_path] if bundle.gif_path is not None else []
    )
    clips = [Path(p) for p in clips if p and Path(p).is_file()]
    if not clips:
        return False
    posted = False
    for index, path in enumerate(clips, 1):
        image = discord.File(str(path), filename=path.name)
        try:
            suffix = f" — Pass {index}/{len(clips)}" if len(clips) > 1 else ""
            await sender.send(
                content=f"🏇 **{a.knight_name} vs {b.knight_name}** · Sprite Broadcast{suffix}",
                file=image,
            )
            posted = True
        except (discord.HTTPException, OSError):
            LOG.exception("Sprite upload failed; match result is already saved.")
            break
        finally:
            image.close()
    return posted
