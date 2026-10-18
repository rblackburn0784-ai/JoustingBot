"""v0.9.2b: one-screen, round-by-round animation regression suite."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from PIL import Image

from services import live_sprite_renderer as render
from services import live_broadcast as live
from services.sprite_engine import AssetCatalog


def fighter(uid, name):
    return SimpleNamespace(user_id=uid, knight_name=name, horse_name=name+" Horse",
                           horse_breed="rouncey")


def saved_bout(count=2):
    passes = [
        SimpleNamespace(
            pass_no=i, category="lance_break", result="Red: lance break",
            points_a=1, points_b=0, margin=3, notes=[], tactics_a={},
            tactics_b={},
        )
        for i in range(1, count+1)
    ]
    return SimpleNamespace(
        fighter_a="Red", fighter_b="Blue", winner="Red", seed=9192,
        score_a=count, score_b=0, passes=passes, arena_name="Royal Lists",
    )


def prepared():
    return SimpleNamespace(
        arena_key="royal_lists", fighter_a=fighter(1, "Red"),
        fighter_b=fighter(2, "Blue"),
        horse_a=SimpleNamespace(breed="rouncey"),
        horse_b=SimpleNamespace(breed="destrier"),
    )


class TimelineTests(unittest.TestCase):
    def test_five_stages_in_chronological_order_with_outcome_hold(self):
        moments = render.timeline()
        stages = []
        for moment in moments:
            if not stages or stages[-1] != moment.phase:
                stages.append(moment.phase)
        self.assertEqual(tuple(stages), render.PHASES)
        self.assertGreater(sum(m.duration_ms for m in moments), 3500)
        self.assertGreater(moments[-1].duration_ms, 500)
        self.assertLess(moments[0].position, moments[-1].position)

    def test_refusal_stops_short_of_full_collision(self):
        refused = render.timeline("refusal")
        collision = next(m for m in refused if m.phase == "COLLISION")
        self.assertLess(collision.position, 1.0)

    def test_before_collision_never_reveals_saved_result_or_score(self):
        result = saved_bout(1)
        log = result.passes[0]
        for item in render.timeline():
            comment = render.moment_commentary(item, log, fighter(1, "Red"),
                                                fighter(2, "Blue"), (0, 0), (1, 0))
            if item.phase in ("PREP", "GALLOP", "LANCE READY"):
                self.assertNotIn("lance break", comment.lower())
                self.assertNotIn("score 1", comment.lower())
        self.assertIn("Score 1", render.moment_commentary(
            render.timeline()[-1], log, fighter(1, "Red"), fighter(2, "Blue"),
            (0, 0), (1, 0)))

    def test_duplicates_and_score_mismatch_detected_before_playback(self):
        result = saved_bout(2)
        self.assertTrue(render.validate_result(result))
        result.passes.append(result.passes[0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            render.validate_result(result)
        result.passes.pop()
        result.score_a = 9
        with self.assertRaisesRegex(ValueError, "totals"):
            render.validate_result(result)

    def test_renders_real_single_pass_animated_gif_and_static_accessibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atlas = AssetCatalog(root)
            result = saved_bout(1)
            args = (
                result, fighter(1, "Red"), fighter(2, "Blue"), "royal_lists",
                result.passes[0], (0, 0), (1, 0),
            )
            with patch.object(render, "RENDER_DIR", root/"output"):
                gif = render.render_live_pass(*args, atlas=atlas, max_kib=7500)
                self.assertEqual(gif.stages, render.PHASES)
                self.assertEqual(gif.score_before, (0, 0))
                self.assertEqual(gif.score_after, (1, 0))
                with Image.open(gif.path) as im:
                    self.assertEqual(im.format, "GIF")
                    self.assertGreaterEqual(im.n_frames, 14)
                    # It plays once; do not loop the last outcome forever.
                    self.assertIsNone(im.info.get("loop"))
                png = render.render_live_pass(*args, atlas=atlas, reduced_motion=True)
                with Image.open(png.path) as im:
                    self.assertEqual(im.format, "PNG")
                    self.assertEqual(im.size, (960, 540))
                self.assertEqual(result.score_a, 1)


class LiveDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_public_message_all_passes_then_final_card(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"arenas").mkdir()
            (root/"arenas"/"royal_lists.png").touch()
            sends = []
            edits = []
            message = SimpleNamespace()

            async def edit(**kwargs):
                edits.append(kwargs)
                return message

            async def send(**kwargs):
                sends.append(kwargs)
                return message

            message.edit = edit
            sender = SimpleNamespace(send=send)
            async def render_clip(*args, **kwargs):
                raise AssertionError("render should be called in a worker thread")

            clips = []
            for n in (1, 2):
                path = root/f"pass_{n}.gif"
                path.write_bytes(b"GIF89a")
                clips.append(render.PassClip(
                    path=path, duration_ms=2000, pass_no=n,
                    score_before=(n-1, 0), score_after=(n, 0),
                    stages=render.PHASES,
                ))
            index = iter(clips)
            timings = []
            async def fake_sleep(duration):
                timings.append(duration)

            with patch.object(live, "ASSET_ROOT", root), \
                 patch.object(live, "render_live_pass",
                              side_effect=lambda *a, **k: next(index)), \
                 patch.object(live, "_final_image",
                              new_callable=AsyncMock, return_value=b"png"):
                success = await live.play_live_match(
                    sender, saved_bout(), prepared(),
                    final_embed=discord.Embed(title="Complete Recap"),
                    pause=.7, sleep=fake_sleep,
                )
            self.assertTrue(success)
            self.assertEqual(len(sends), 1)
            self.assertEqual(len(edits), 2)  # pass 2, then final
            self.assertIn("pass_1.gif", sends[0]["embed"].image.url)
            self.assertIn("pass_2.gif", edits[0]["embed"].image.url)
            self.assertEqual(edits[1]["embed"].title, "Complete Recap")
            self.assertEqual(edits[1]["embed"].image.url,
                             "attachment://joust_live_final.png")
            self.assertEqual(len(timings), 2)
            self.assertAlmostEqual(timings[0], 2.7)
            self.assertAlmostEqual(timings[1], 2.7)

    async def test_no_assets_returns_false_before_any_public_message(self):
        with tempfile.TemporaryDirectory() as root, \
             patch.object(live, "ASSET_ROOT", Path(root)):
            sender = SimpleNamespace(send=AsyncMock())
            success = await live.play_live_match(sender, saved_bout(), prepared())
        self.assertFalse(success)
        sender.send.assert_not_awaited()

    async def test_first_render_failure_falls_back_without_any_message(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"arenas").mkdir()
            (root/"arenas"/"royal_lists.png").touch()
            sender = SimpleNamespace(send=AsyncMock())
            with patch.object(live, "ASSET_ROOT", root), \
                 patch.object(live, "render_live_pass",
                              side_effect=OSError("bad PNG")):
                success = await live.play_live_match(sender, saved_bout(), prepared())
        self.assertFalse(success)
        sender.send.assert_not_awaited()

    async def test_reduced_motion_uses_static_per_pass_still_in_one_message(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"arenas").mkdir()
            (root/"arenas"/"royal_lists.png").touch()
            clip = root/"still.png"
            clip.write_bytes(b"fake png")
            message = SimpleNamespace(edit=AsyncMock())
            sender = SimpleNamespace(send=AsyncMock(return_value=message))
            def render_static(*args, **kwargs):
                self.assertTrue(kwargs["reduced_motion"])
                return render.PassClip(
                    clip, 1400, 1, (0, 0), (1, 0), render.PHASES, False,
                )
            with patch.dict("os.environ", {"JOUST_BROADCAST_REDUCED_MOTION": "true",
                                            "JOUST_LIVE_KEEP_RENDERS": "true"}), \
                 patch.object(live, "ASSET_ROOT", root), \
                 patch.object(live, "render_live_pass", side_effect=render_static), \
                 patch.object(live, "_final_image",
                              new_callable=AsyncMock, return_value=None):
                await live.play_live_match(sender, saved_bout(1), prepared(),
                                           pause=0, sleep=AsyncMock())
            sender.send.assert_awaited_once()
            message.edit.assert_awaited_once()
            self.assertIn("still.png", sender.send.await_args.kwargs["embed"].image.url)


    async def test_modern_joust_handler_does_not_send_second_final_card(self):
        from cogs.joust import JoustCog
        current = saved_bout()
        ready = prepared()
        ready.guild_id = None
        ready.seed = 9192
        ready.tactics_a = SimpleNamespace()
        ready.tactics_b = SimpleNamespace()
        ready.support_token_a = None
        ready.support_token_b = None
        ready.mode = "instant"
        sender = SimpleNamespace(send=AsyncMock())
        with patch("cogs.joust.make_intro_embed", return_value=discord.Embed(title="Intro")), \
             patch("cogs.joust.make_result_embed",
                   return_value=discord.Embed(title="Recorded Result")), \
             patch("cogs.joust.run_single_match", return_value=current) as combat, \
             patch("cogs.joust.record_match", return_value="saved-match") as journal, \
             patch("services.sprite_broadcast_adapter.send_sprite_broadcast",
                   new_callable=AsyncMock, return_value=True) as stream, \
             patch("cogs.broadcast.send_final", new_callable=AsyncMock) as old_final:
            returned = await JoustCog.send_match(None, sender, ready)
        self.assertIs(returned, current)
        combat.assert_called_once()
        journal.assert_called_once()
        stream.assert_awaited_once()
        old_final.assert_not_awaited()
        self.assertEqual(stream.await_args.kwargs["final_embed"].title,
                         "Recorded Result")

    async def test_failed_next_pass_ends_at_final_without_repeating_full_bout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/"arenas").mkdir()
            (root/"arenas"/"royal_lists.png").touch()
            path = root/"pass_1.gif"
            path.write_bytes(b"GIF89a")
            first = render.PassClip(
                path, 2000, 1, (0, 0), (1, 0), render.PHASES,
            )
            message = SimpleNamespace(edit=AsyncMock())
            sender = SimpleNamespace(send=AsyncMock(return_value=message))
            calls = iter((first, OSError("corrupt sprite")))
            def make(*args, **kwargs):
                item = next(calls)
                if isinstance(item, Exception):
                    raise item
                return item
            sleeps = []
            async def fake_sleep(value):
                sleeps.append(value)
            with patch.object(live, "ASSET_ROOT", root), \
                 patch.object(live, "render_live_pass", side_effect=make), \
                 patch.object(live, "_final_image", new_callable=AsyncMock,
                              return_value=None):
                done = await live.play_live_match(
                    sender, saved_bout(), prepared(), pause=.5, sleep=fake_sleep,
                )
            self.assertTrue(done)
            sender.send.assert_awaited_once()
            message.edit.assert_awaited_once()  # final, no duplicate stages
            self.assertEqual(message.edit.await_args.kwargs["embed"].title,
                             "🏆 The Grand Lists — Final Result")
            self.assertEqual(len(sleeps), 1)  # no double wait on failed pass



if __name__ == "__main__":
    unittest.main()
