"""v0.9.2b live sprite broadcast entry point for already-recorded matches.

The v0.9.2a multi-attachment recap is superseded by a SINGLE continuously
edited Discord message. Combat, rewards and journals remain in JoustCog.
"""
from __future__ import annotations

import os


def sprite_enabled() -> bool:
    return os.getenv("JOUST_SPRITE_ENABLED", "true").strip().lower() not in {
        "0", "false", "off", "no"
    }


async def send_sprite_broadcast(sender, result, prepared, *,
                                final_embed=None, home_view=None) -> bool:
    """True means the live broadcaster owns the final scorecard.

    False means nothing was posted and the caller should use the previous
    v0.9.2 cinematic text/card sequence instead.
    """
    if not sprite_enabled():
        return False
    from services.live_broadcast import play_live_match
    return await play_live_match(
        sender, result, prepared,
        final_embed=final_embed, home_view=home_view,
    )
