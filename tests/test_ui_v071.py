"""UI and title smoke tests; no bot token, network, or live Discord server."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from cogs import menu
from cogs.horse import HorseStatBuilderView
from cogs.knight import KnightStatBuilderView
from services.competition import TITLE_RULES, title_progress


class UIReleaseTests(unittest.TestCase):
    def test_version_page_matches_current_release_and_broadcast(self):
        self.assertEqual(menu.VERSION, "v0.9.2d")
        overview = menu.VersionPage(123).make_embed()
        self.assertIn(menu.VERSION, overview.title)
        self.assertIn("Gallop", overview.description)
        self.assertIn("final scorecard", overview.description)

    def test_original_eighteen_titles_preserved_and_twelve_tournament_added(self):
        self.assertEqual(len(TITLE_RULES), 30)
        self.assertEqual(len(set(TITLE_RULES)), 30)
        for key, (display, description, field, threshold) in TITLE_RULES.items():
            self.assertTrue(key and display and description and field)
            self.assertGreater(threshold, 0)
        self.assertEqual(len(title_progress(1, 123, {"matches": []})), 30)

    def test_all_twelve_new_titles_are_unlockable(self):
        old_keys = {
            "the_unhorsed", "shield_splitter", "mud_king",
            "frozen_terror", "crowd_favourite", "the_reluctant_rider",
        }
        arenas = [
            "royal_lists", "wind_swept", "festival_arena",
            "war_torn", "muddy_field", "frozen_ground",
        ]
        matches = []
        for index in range(30):
            passes = [
                {"category": "lance_break", "result": "Arthur: lance break",
                 "points_a": 1, "points_b": 0, "notes": []},
                {"category": "unhorsing", "result": "Arthur: unhorsing",
                 "points_a": 3, "points_b": 0, "notes": []},
            ]
            matches.append({
                "id": f"win{index}", "guild_id": 99, "mode": "challenge",
                "arena_key": arenas[index % len(arenas)],
                "a": {"user_id": 5, "knight": "Arthur", "horse": "Swift",
                      "horse_id": "h5", "score": 3},
                "b": {"user_id": 6, "knight": "Basil", "horse": "Slow",
                      "horse_id": "h6", "score": 0},
                "passes": passes,
            })
        for index in range(3):
            matches.append({
                "id": f"draw{index}", "guild_id": 99, "mode": "challenge",
                "arena_key": "royal_lists",
                "a": {"user_id": 5, "knight": "Arthur", "horse": "Swift",
                      "horse_id": "h5", "score": 0},
                "b": {"user_id": 6, "knight": "Basil", "horse": "Slow",
                      "horse_id": "h6", "score": 0},
                "passes": [],
            })
        progress = title_progress(99, 5, {"matches": matches})
        from services.tournament_awards import TOURNAMENT_TITLES
        career_keys = [key for key in TITLE_RULES if key not in TOURNAMENT_TITLES]
        self.assertEqual(len(career_keys), 18)
        self.assertTrue(all(progress[k]["earned"] for k in career_keys if k not in old_keys))
        self.assertTrue(all(not progress[k]["earned"] for k in TOURNAMENT_TITLES))

    def test_main_menu_admin_visibility(self):
        public = menu.MainMenuView(123, False)
        admin = menu.MainMenuView(123, True)
        public_buttons = [c.label for c in public.children if isinstance(c, discord.ui.Button)]
        admin_buttons = [c.label for c in admin.children if isinstance(c, discord.ui.Button)]
        self.assertNotIn("Admin", public_buttons)
        self.assertIn("Admin", admin_buttons)
        self.assertIn("Main Menu", public_buttons)

    def test_actionable_views_with_home(self):
        views = [
            menu.MainMenuView(123), menu.StartView(123), menu.KnightPage(123),
            menu.HorsePage(123), menu.StableView(123), menu.EquipmentPage(123),
            menu.EquipmentPicker(123, "lance"), menu.ArenaPage(123),
            menu.DuelPage(123), menu.ProfilePage(123),
            menu.LeaderboardPage(123, None), menu.TitlePage(123, None),
            menu.InjuryPage(123, None),
            menu.AdminPage(123), menu.ConfirmKnightDelete(123),
            menu.ConfirmHorseDelete(123, "none"), menu.HomeOnlyView(123),
            KnightStatBuilderView(123, "Sir Test"),
            HorseStatBuilderView(123, "Thunder", "Destrier"),
        ]
        for view in views:
            with self.subTest(view=type(view).__name__):
                items = view.children
                self.assertTrue(any(getattr(item, "label", None) == "Main Menu" for item in items))
                self.assertLessEqual(len(items), 25)
                rows = {}
                for item in items:
                    row = getattr(item, "row", None)
                    self.assertIn(row, range(5))
                    rows.setdefault(row, []).append(item)
                for row, children in rows.items():
                    if any(isinstance(c, discord.ui.Select) for c in children):
                        self.assertEqual(len(children), 1, f"select must occupy full row {row}")
                    else:
                        self.assertLessEqual(len(children), 5)
                self.assertLessEqual(len(view.make_embed().to_dict().get("description", "")), 4096) if hasattr(view, "make_embed") else None

    def test_title_browser_pagination(self):
        view = menu.TitlePage(123, None, page=2)
        self.assertEqual(view.page, 2)
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        self.assertEqual(len(selects), 1)
        self.assertEqual(len(selects[0].options), 6)


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_panel_rechecks_permission(self):
        restricted = menu.AdminPage(123)
        response = SimpleNamespace(send_message=AsyncMock())
        intr = SimpleNamespace(user=SimpleNamespace(
            id=123, guild_permissions=SimpleNamespace(manage_guild=False)
        ), guild_id=55, response=response)
        result = await restricted.interaction_check(intr)
        self.assertFalse(result)
        response.send_message.assert_awaited_once()

    async def test_non_owner_cannot_operate_other_menu(self):
        view = menu.KnightPage(123)
        response = SimpleNamespace(send_message=AsyncMock())
        intr = SimpleNamespace(user=SimpleNamespace(id=987), guild_id=5, response=response)
        result = await view.interaction_check(intr)
        self.assertFalse(result)
        response.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
