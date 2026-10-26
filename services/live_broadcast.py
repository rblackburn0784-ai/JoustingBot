"""v0.9.2b — one editable Discord graphic for the entire live joust.

Send only ONE public broadcast message. Each pass is a self-playing timed GIF
that stays on the outcome card. After a short pause, edit that SAME message
with the next pass. Only after the last pass edit it into the final scoreboard
and accessible match recap. No simulation/reward/storage calls live here.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from pathlib import Path

import discord

from services.live_sprite_renderer import render_live_pass, validate_result
from services.sprite_engine import ASSET_ROOT, AssetCatalog

LOG = logging.getLogger(__name__)


def _flag(name, default=False):
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _float_setting(name, default, low, high):
    try:
        return min(high, max(low, float(os.getenv(name, default))))
    except (TypeError, ValueError):
        return default


def _max_kib():
    try:
        return min(7500, max(1000, int(os.getenv("JOUST_LIVE_MAX_KIB", "7500"))))
    except (TypeError, ValueError):
        return 7500


def configured_pause():
    return _float_setting("JOUST_LIVE_PASS_PAUSE", .9, .2, 3.0)


def _screen_embed(result, clip, *, arena_key):
    e = discord.Embed(
        title=f"🏇 The Grand Lists — Pass {clip.pass_no}",
        description=(
            f"**{result.fighter_a}** vs **{result.fighter_b}** · "
            f"{arena_key.replace('_', ' ').title()}\n"
            "Prepare → Gallop → Lance Ready → Collision → Outcome"
        ),
        colour=discord.Colour(0xB4874C),
    )
    e.set_image(url=f"attachment://{clip.path.name}")
    e.set_footer(text=f"JoustingBot v0.9.2c · {clip.pass_no} of {len(result.passes)} passes")
    return e


def _fallback_final_embed(result):
    e = discord.Embed(
        title="🏆 The Grand Lists — Final Result",
        description=(
            f"**{result.fighter_a}: {result.score_a}**"
            f"  ·  **{result.fighter_b}: {result.score_b}**\n"
            f"Winner: **{result.winner}**"
        ),
    )
    return e


async def _publish_first(sender, **kwargs):
    if isinstance(sender, discord.Webhook):
        kwargs["wait"] = True
    return await sender.send(**kwargs)


def _close_file(attachment):
    if attachment is not None:
        attachment.close()


def _cleanup(path: Path | None):
    if path and not _flag("JOUST_LIVE_KEEP_RENDERS"):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            LOG.warning("Could not remove temporary sprite clip %s", path)


async def _final_image(result, prepared):
    """Generate in worker thread; returns bytes or None if PIL art fails."""
    try:
        from services.broadcast_art import final
        return await asyncio.to_thread(final, result, prepared)
    except Exception:
        LOG.exception("Final scorecard PNG unavailable; text remains accessible.")
        return None


async def _show_final(message, sender, result, prepared, final_embed, home_view):
    final_embed = final_embed or _fallback_final_embed(result)
    png = await _final_image(result, prepared)
    if png is not None:
        final_embed.set_image(url="attachment://joust_live_final.png")
    else:
        final_embed.set_image(url=None)

    # Message.edit accepts attachments=[discord.File]; using the same stable
    # live message prevents the browser from displaying stale passed GIFs.
    try:
        if png is not None:
            file = discord.File(io.BytesIO(png), filename="joust_live_final.png")
            try:
                await message.edit(embed=final_embed, attachments=[file], view=home_view)
            finally:
                file.close()
        else:
            await message.edit(embed=final_embed, attachments=[], view=home_view)
        return True
    except (discord.HTTPException, OSError, TypeError, ValueError):
        LOG.exception("Final live-screen edit failed; trying normal final post.")
        # This is a recovery-only extra message, not the normal experience.
        if png is not None:
            file = discord.File(io.BytesIO(png), filename="joust_live_final.png")
            try:
                await _publish_first(sender, embed=final_embed, file=file, view=home_view)
            finally:
                file.close()
        else:
            await _publish_first(sender, embed=final_embed, view=home_view)
        return True


async def play_live_match(sender, result, prepared, *,
                          final_embed=None, home_view=None, catalog=None,
                          pause=None, sleep=asyncio.sleep):
    """Play distinct saved passes sequentially in ONE Discord message.

    Return False ONLY if playback never started; the v0.9.2 broadcast can then
    take over. Once first animation is posted we own that one live message and
    recover to a final card rather than replaying/duplicating the whole joust.
    """
    from services.sprite_broadcast_adapter import sprite_enabled
    if not sprite_enabled():
        return False
    if not (ASSET_ROOT / "arenas" / (prepared.arena_key + ".png")).is_file():
        LOG.info("No arena art for %s; using v0.9.2 broadcaster.", prepared.arena_key)
        return False
    try:
        validate_result(result)
    except (ValueError, TypeError, AttributeError):
        LOG.exception("Invalid pass journal, sprite playback unavailable.")
        return False

    atlas = catalog or AssetCatalog()
    fa, fb = prepared.fighter_a, prepared.fighter_b
    visible_ticker = _flag("JOUST_LIVE_TICKER", True)
    reduced = _flag("JOUST_BROADCAST_REDUCED_MOTION")
    limit = _max_kib()
    interval = configured_pause() if pause is None else max(0.0, pause)
    stem = f"{getattr(result, 'seed', 'match')}_{getattr(fa, 'user_id', 'a')}_{getattr(fb, 'user_id', 'b')}"
    score = (0, 0)
    jobs = []
    for log in result.passes:
        before = score
        score = (score[0] + int(log.points_a), score[1] + int(log.points_b))
        jobs.append((log, before, score))

    def render(job):
        log, before, after = job
        return render_live_pass(
            result, fa, fb, prepared.arena_key, log, before, after,
            atlas=atlas, horse_a=prepared.horse_a, horse_b=prepared.horse_b,
            max_kib=limit, show_ticker=visible_ticker,
            reduced_motion=reduced, out_stem=stem,
        )

    try:
        current_clip = await asyncio.to_thread(render, jobs[0])
    except Exception:
        LOG.exception("First pass could not render; fallback to v0.9.2.")
        return False

    filename = current_clip.path.name
    initial_file = discord.File(str(current_clip.path), filename=filename)
    try:
        message = await _publish_first(
            sender, embed=_screen_embed(result, current_clip, arena_key=prepared.arena_key),
            file=initial_file, view=home_view,
        )
    except (discord.HTTPException, OSError):
        LOG.exception("Could not post first sprite pass; fallback to v0.9.2.")
        return False
    finally:
        initial_file.close()
        _cleanup(current_clip.path)

    if message is None or not callable(getattr(message, "edit", None)):
        LOG.warning("Live message has no edit method; posting final when pass finishes.")
        await sleep(current_clip.duration_ms / 1000)
        await _show_final_uneditable(sender, result, prepared, final_embed, home_view)
        return True

    last_clip_played = False
    try:
        for index in range(1, len(jobs)):
            # Render the next pass off-thread DURING the previous GIF playback,
            # so there is no extra rendering pause between rounds.
            pending = asyncio.create_task(asyncio.to_thread(render, jobs[index]))
            await sleep(current_clip.duration_ms / 1000 + interval)
            last_clip_played = True
            try:
                next_clip = await pending
            except Exception:
                LOG.exception("Unable to render pass %s; ending at saved final score.", index+1)
                break
            file = discord.File(str(next_clip.path), filename=next_clip.path.name)
            try:
                await message.edit(
                    embed=_screen_embed(result, next_clip, arena_key=prepared.arena_key),
                    attachments=[file], view=home_view,
                )
            except (discord.HTTPException, OSError, TypeError, ValueError):
                LOG.exception("Live screen could not advance to pass %s.", next_clip.pass_no)
                _cleanup(next_clip.path)
                break
            finally:
                file.close()
            _cleanup(next_clip.path)
            current_clip = next_clip
            last_clip_played = False
        # Leave the last outcome on screen before showing the final card.
        # Do not wait twice if a later pass was unable to render.
        if not last_clip_played:
            await sleep(current_clip.duration_ms / 1000 + interval)
    finally:
        # No state of the match is changed, even if artwork is unavailable.
        pass
    try:
        await _show_final(message, sender, result, prepared, final_embed, home_view)
    except Exception:
        # Playback has already been publicly shown. Never re-run the old
        # stages and display the same bout twice if Discord is unavailable.
        LOG.exception("Live match completed but Discord rejected its final scorecard.")
    return True


async def _show_final_uneditable(sender, result, prepared, final_embed, home_view):
    final_embed = final_embed or _fallback_final_embed(result)
    png = await _final_image(result, prepared)
    if png:
        final_embed.set_image(url="attachment://joust_live_final.png")
        file = discord.File(io.BytesIO(png), filename="joust_live_final.png")
        try:
            await _publish_first(sender, embed=final_embed, file=file, view=home_view)
        finally:
            file.close()
    else:
        final_embed.set_image(url=None)
        await _publish_first(sender, embed=final_embed, view=home_view)
