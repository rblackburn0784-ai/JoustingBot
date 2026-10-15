"""v0.9.2 broadcast smoke and stability tests (no Discord token needed)."""
from __future__ import annotations

import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from services.broadcast import make_frames, statistics, STAGES
from services.combat import PassLog
from cogs import broadcast as ui


def make_result():
    passes = [
        PassLog(
            pass_no=1, result="Arthur: lance break", category="lance_break",
            points_a=1, points_b=0, margin=3, arena_line="The banners snap.",
            gear_line="An ash lance finds its mark.", notes=["No early announcement."],
            tactics_a={"style": "balanced", "target": "lance", "fatigue": 0, "move": "none"},
            tactics_b={"style": "aggressive", "target": "rider", "fatigue": 0, "move": "reckless_charge"},
        ),
        PassLog(
            pass_no=2, result="Basil: unhorsing", category="unhorsing",
            points_a=0, points_b=3, margin=13, arena_line="Frozen earth thunders.",
            gear_line="", notes=[],
            tactics_a={"style": "cautious", "target": "shield", "fatigue": 2, "move": "none"},
            tactics_b={"style": "aggressive", "target": "rider", "fatigue": 3, "move": "none"},
        ),
    ]
    return SimpleNamespace(
        fighter_a="Arthur", fighter_b="Basil",
        score_a=1, score_b=3, winner="Basil", seed=4142,
        passes=passes,
    )


def prepared():
    return SimpleNamespace(
        arena_key="frozen_ground", challenger=SimpleNamespace(id=1, mention="<@1>"),
        opponent=SimpleNamespace(id=2, mention="<@2>"),
        knight_a=SimpleNamespace(name="Arthur"),
        knight_b=SimpleNamespace(name="Basil"),
        horse_a=SimpleNamespace(name="Thunder", breed="Destrier"),
        horse_b=SimpleNamespace(name="Biscuit", breed="Courser"),
        tactics_a=SimpleNamespace(style="balanced", target="shield"),
        tactics_b=SimpleNamespace(style="aggressive", target="rider"),
    )


class BroadcastModelTests(unittest.TestCase):
    def test_stage_order_unique_frames_and_score_progression(self):
        result = make_result()
        frames = make_frames(result, arena_key="frozen_ground")
        self.assertEqual(len(frames), 8)
        self.assertEqual([f.phase for f in frames], list(STAGES) * 2)
        self.assertEqual(len({f.key for f in frames}), 8)
        self.assertEqual((frames[0].score_a, frames[0].score_b), (0, 0))
        self.assertEqual((frames[3].score_a, frames[3].score_b), (1, 0))
        self.assertEqual((frames[7].score_a, frames[7].score_b), (1, 3))
        self.assertEqual(frames[0].total, 5)  # no early-result spoiler
        self.assertEqual(frames[-1].category, "unhorsing")

    def test_preimpact_phases_reveal_neither_result_nor_winner(self):
        result = make_result()
        for frame in make_frames(result, arena_key="frozen_ground"):
            if frame.phase in {"approach", "charge"}:
                self.assertNotIn("unhorsing", frame.commentary.lower())
                self.assertNotIn("lance break", frame.commentary.lower())
                self.assertEqual(frame.category, "")

    def test_duplicate_pass_and_incorrect_total_are_rejected(self):
        match = make_result()
        match.passes.append(match.passes[0])
        with self.assertRaisesRegex(ValueError, "Duplicate pass"):
            make_frames(match, arena_key="royal_lists")
        match.passes.pop()
        match.score_a += 1
        with self.assertRaisesRegex(ValueError, "score"):
            make_frames(match, arena_key="royal_lists")

    def test_scoring_statistics_are_read_only(self):
        match = make_result()
        original = (match.score_a, match.score_b)
        stats = statistics(match)
        self.assertEqual(stats["a"]["lance_breaks"], 1)
        self.assertEqual(stats["b"]["unhorsings"], 1)
        self.assertEqual(stats["b"]["points"], 3)
        self.assertEqual(original, (match.score_a, match.score_b))

    def test_media_url_only_allows_https_and_uses_result_priority(self):
        manifest = {"images": {
            "impact": "https://cdn.example.com/impact.gif",
            "impact_unhorsing": "https://cdn.example.com/unhorsing.gif",
            "frozen_ground_approach": "https://cdn.example.com/ice.png",
            "charge": "file:///private/file.png",
        }}
        self.assertEqual(
            ui.media_url("impact", arena_key="frozen_ground", category="unhorsing",
                         manifest=manifest),
            "https://cdn.example.com/unhorsing.gif")
        self.assertEqual(ui.media_url("approach", arena_key="frozen_ground", manifest=manifest),
                         "https://cdn.example.com/ice.png")
        self.assertEqual(ui.media_url("charge", arena_key="frozen_ground", manifest=manifest), "")
        self.assertEqual(ui.media_url("aftermath", arena_key="frozen_ground", manifest={}), "")

    def test_generated_pngs_have_correct_dimensions_with_no_art(self):
        from PIL import Image
        from services.broadcast_art import intro, final
        with patch("services.broadcast_art.ROOT") as dummy:
            dummy.__truediv__.return_value.is_file.return_value = False
            intro_image = Image.open(io.BytesIO(intro(prepared())))
            end_image = Image.open(io.BytesIO(final(make_result(), prepared())))
        self.assertEqual(intro_image.size, (1200, 675))
        self.assertEqual(end_image.size, (1200, 675))
        self.assertEqual(intro_image.format, "PNG")
        self.assertEqual(end_image.format, "PNG")


class BroadcastDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_live_screen_post_then_edits_and_no_duplicate_sends(self):
        outgoing = SimpleNamespace(edit=AsyncMock())
        sender = SimpleNamespace(send=AsyncMock(return_value=outgoing))
        result = make_result()
        with patch.object(ui, "media_manifest", return_value={}):
            await ui.play_passes(sender, result, arena_key="frozen_ground", delay=0)
        self.assertEqual(sender.send.await_count, 1)
        self.assertEqual(outgoing.edit.await_count, 7)
        titles = [sender.send.await_args.kwargs["embed"].title] + [
            call.kwargs["embed"].title for call in outgoing.edit.await_args_list
        ]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertTrue(titles[0].endswith("Approach"))
        self.assertTrue(titles[-1].endswith("Aftermath"))

    async def test_reduced_motion_makes_no_live_edits(self):
        outgoing = SimpleNamespace(edit=AsyncMock())
        sender = SimpleNamespace(send=AsyncMock(return_value=outgoing))
        with patch.dict("os.environ", {"JOUST_BROADCAST_REDUCED_MOTION": "true"}):
            await ui.play_passes(sender, make_result(), arena_key="royal_lists", delay=0)
        sender.send.assert_awaited_once()
        outgoing.edit.assert_not_awaited()

    async def test_stage_edit_failure_does_not_resend_or_raise(self):
        outgoing = SimpleNamespace(edit=AsyncMock(side_effect=OSError("network disconnect")))
        sender = SimpleNamespace(send=AsyncMock(return_value=outgoing))
        await ui.play_passes(sender, make_result(), arena_key="royal_lists", delay=0)
        sender.send.assert_awaited_once()
        outgoing.edit.assert_awaited_once()

    async def test_send_intro_and_final_with_generated_attachment(self):
        sender = SimpleNamespace(send=AsyncMock())
        box = discord.Embed(title="Intro")
        with patch.object(ui, "intro_file", return_value=None), patch.object(ui, "media_manifest", return_value={}):
            await ui.send_intro(sender, prepared(), box)
        self.assertTrue(any(f.name == "🎺 Knight Entrances" for f in box.fields))
        self.assertEqual(sender.send.await_count, 1)
        with patch.object(ui, "final_file", return_value=None), patch.object(ui, "media_manifest", return_value={}):
            await ui.send_final(sender, discord.Embed(title="Final"), make_result(), prepared())
        self.assertEqual(sender.send.await_count, 2)

    async def test_match_is_simulated_and_recorded_once_despite_broadcast_failure(self):
        from cogs.joust import JoustCog
        prepared_ = SimpleNamespace(
            guild_id=None, arena_key="royal_lists", seed=4142,
            fighter_a=SimpleNamespace(user_id=1), fighter_b=SimpleNamespace(user_id=2),
            tactics_a=SimpleNamespace(), tactics_b=SimpleNamespace(),
            support_token_a=None, support_token_b=None, mode="instant",
        )
        match = make_result()
        sender = SimpleNamespace(send=AsyncMock())
        with patch("cogs.joust.make_intro_embed", return_value=discord.Embed(title="Intro")), \
             patch("cogs.joust.make_result_embed", return_value=discord.Embed(title="End")), \
             patch("cogs.joust.run_single_match", return_value=match) as simulate, \
             patch("cogs.joust.record_match", return_value="saved-id") as journal, \
             patch("cogs.broadcast.enabled", return_value=True), \
             patch("cogs.broadcast.send_intro", new_callable=AsyncMock, side_effect=OSError("no art")), \
             patch("cogs.broadcast.play_passes", new_callable=AsyncMock) as playback, \
             patch("cogs.broadcast.send_final", new_callable=AsyncMock) as final_post:
            result = await JoustCog.send_match(None, sender, prepared_)
        self.assertIs(result, match)
        simulate.assert_called_once()
        journal.assert_called_once()
        playback.assert_not_awaited()
        final_post.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
