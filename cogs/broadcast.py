"""v0.9.2 Discord broadcast playback: a single editable live-screen message.

The combat engine is called ONLY by JoustCog.send_match, never here.
If media rendering/editing fails, match history remains intact and final
score/awards can still be posted. No external media files are required.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import discord

from services.broadcast import PHASE_COLORS, make_frames

LOG = logging.getLogger(__name__)
MEDIA_PATH = Path(__file__).resolve().parent.parent / "assets" / "broadcast" / "manifest.json"
VERSION = "v0.9.2"


def enabled() -> bool:
    return os.getenv("JOUST_BROADCAST_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def delay_seconds() -> float:
    try:
        return max(0.35, min(2.5, float(os.getenv("JOUST_BROADCAST_STAGE_DELAY", "0.85"))))
    except ValueError:
        return 0.85


def media_manifest() -> dict:
    try:
        doc = json.loads(MEDIA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def media_url(phase: str, *, arena_key: str, category: str = "", manifest: dict | None = None) -> str:
    doc = manifest if manifest is not None else media_manifest()
    images = doc.get("images", {}) if isinstance(doc, dict) else {}
    if not isinstance(images, dict):
        return ""
    options = [f"{arena_key}_{phase}"]
    if category and phase == "impact":
        options.insert(0, f"impact_{category}")
    options.append(phase)
    for key in options:
        address = images.get(key)
        if not isinstance(address, str):
            continue
        address = address.strip()
        parsed = urlparse(address)
        if parsed.scheme == "https" and parsed.netloc:
            return address
    return ""


def intro_file(prepared) -> discord.File | None:
    try:
        from services.broadcast_art import intro
        return discord.File(io.BytesIO(intro(prepared)), filename="grand_lists_intro.png")
    except Exception:
        LOG.exception("Broadcast intro art unavailable; continuing with text.")
        return None


def final_file(result, prepared) -> discord.File | None:
    try:
        from services.broadcast_art import final
        return discord.File(io.BytesIO(final(result, prepared)), filename="grand_lists_final.png")
    except Exception:
        LOG.exception("Broadcast scoreboard art unavailable; continuing with text.")
        return None


async def send(sender, **kwargs):
    # A Discord Interaction followup is a Webhook, which needs wait=True to
    # return the message ID for our *edit-once-per-stage* live broadcast.
    if isinstance(sender, discord.Webhook):
        kwargs["wait"] = True
    return await sender.send(**kwargs)


async def send_intro(sender, prepared, intro_embed) -> object:
    picture = intro_file(prepared)
    manifest = media_manifest()
    if picture is not None:
        intro_embed.set_image(url="attachment://grand_lists_intro.png")
        return await send(sender, embed=intro_embed, file=picture)
    fallback = media_url("intro", arena_key=prepared.arena_key, manifest=manifest)
    if fallback:
        intro_embed.set_image(url=fallback)
    return await send(sender, embed=intro_embed)


def frame_embed(result, frame, arena_key: str, manifest: dict | None = None) -> discord.Embed:
    card = discord.Embed(
        title=frame.title,
        description=frame.commentary,
        colour=discord.Colour(PHASE_COLORS[frame.phase]),
    )
    card.add_field(
        name="🏟️ The Lists",
        value=f"{result.fighter_a}: **{frame.score_a}**    ·    "
              f"{result.fighter_b}: **{frame.score_b}**",
        inline=False,
    )
    card.add_field(name="Broadcast Progress",
                   value=f"Pass {frame.pass_no} of {frame.total} · {frame.phase.title()}",
                   inline=False)
    art = media_url(frame.phase, arena_key=arena_key, category=frame.category, manifest=manifest)
    if art:
        card.set_image(url=art)
    card.set_footer(text=f"JoustingBot {VERSION} · Only recorded combat results are being replayed")
    return card


async def play_passes(sender, result, *, arena_key: str, home_view=None, delay: float | None = None):
    """One Discord message is sent, then edited for each remaining stage.

    A failure to edit stops playback but never requests a new combat roll.
    Returns the one live-screen message, if any.
    """
    frames = make_frames(result, arena_key=arena_key)
    if not frames:
        return None
    manifest = media_manifest()
    pause = delay_seconds() if delay is None else max(0.0, delay)
    first = frame_embed(result, frames[0], arena_key, manifest)
    message = await send(sender, embed=first, view=home_view)
    if message is None or not callable(getattr(message, "edit", None)):
        LOG.warning("Broadcast message unavailable for editing; continuing to final.")
        return message
    seen = {frames[0].key}
    for frame in frames[1:]:
        if frame.key in seen:
            LOG.error("Duplicate cinematic frame suppressed: %s", frame.key)
            continue
        seen.add(frame.key)
        if pause:
            await asyncio.sleep(pause)
        try:
            await message.edit(embed=frame_embed(result, frame, arena_key, manifest), view=home_view)
        except (discord.HTTPException, OSError) as exc:
            LOG.warning("Broadcast stage edit failed on %s: %s", frame.key, exc)
            break
    return message


async def send_final(sender, result_embed, result, prepared, home_view=None):
    picture = final_file(result, prepared)
    if picture:
        result_embed.set_image(url="attachment://grand_lists_final.png")
        return await send(sender, embed=result_embed, file=picture, view=home_view)
    fallback = media_url("final", arena_key=prepared.arena_key)
    if fallback:
        result_embed.set_image(url=fallback)
    return await send(sender, embed=result_embed, view=home_view)
