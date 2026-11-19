"""v2.9.7a — exploit, recovery, integrity and interactive UI regression audit."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import discord

from services import circuit, tournaments, records, maintenance
from services.storage import save_json
from cogs.circuit import CircuitHub, CircuitPage, HousePage, HouseMissionsPage, HOUSE_LOCKS
from cogs.tournament import (TournamentHub, TournamentPanel,
                             ConfirmTournamentCancel, AdvancedTournamentModal,
                             status_embed)
from cogs.menu import (MainMenuView, VersionPage, StartView, OwnedView)

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(tournaments, "PATH", str(root / "tournaments.json")),
            patch.object(records, "HISTORY_PATH", str(root / "matches.json")),
            patch.object(circuit, "PATH", str(root / "houses.json")),
            patch.object(maintenance, "DATA_DIR", root),
            patch.object(maintenance, "BACKUP_DIR", root / "backups"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def joined(self, *, gid=88, format="single_elimination"):
        tournament = tournaments.create(gid, 15, "The Grand Spring Lists", 4, format=format)
        for uid in (101, 102, 103, 104):
            tournaments.join(gid, uid)
        return tournament


class TournamentProtectionTests(Fixture):
    def test_standard_event_does_not_request_irrelevant_checkin(self):
        self.joined()
        with self.assertRaisesRegex(tournaments.TournamentError, "doesn't require"):
            tournaments.check_in(88, 101)
        panel = TournamentPanel(88)
        check = next(item for item in panel.children if item.label == "Check In")
        self.assertTrue(check.disabled)
        self.assertFalse(next(item for item in panel.children
                              if item.label == "Join Tournament").disabled)

    def test_event_name_rejects_mentions_newlines_and_control_chars(self):
        for name in ("Hello @everyone", "The <@123> Cup",
                     "A\nCup", "Title\x00Cup"):
            with self.subTest(name=name), self.assertRaises(tournaments.TournamentError):
                tournaments.create(88, 15, name, 4)
        self.assertIsNone(tournaments.current(88))

    def test_cancel_registration_preserves_archive_and_allows_restart(self):
        self.joined()
        saved = tournaments.cancel(88, 15)
        self.assertEqual(saved["status"], "cancelled")
        self.assertEqual(len(tournaments.load_db()["guilds"]["88"]["cancelled"]), 1)
        self.assertIsNone(tournaments.current(88))
        self.assertFalse(tournaments.recent(88))
        with self.assertRaisesRegex(tournaments.TournamentError, "no active"):
            tournaments.cancel(88, 15)
        new_event = tournaments.create(88, 15, "Restarted Tournament", 4)
        self.assertNotEqual(new_event["id"], saved["id"])
        self.assertFalse(circuit.seasonal_standings(88)["standings"])

    def test_cancel_running_no_played_bouts_only(self):
        self.joined()
        event = tournaments.start(88)
        pair = tournaments.reserve_next(88)["match"]
        # A reserved but not recorded game may be safely cancelled by admin
        self.assertEqual(tournaments.cancel(88, 15)["status"], "cancelled")
        self.joined()
        live = tournaments.start(88)
        pair = tournaments.reserve_next(88)["match"]
        save_json(records.HISTORY_PATH, {
            "matches": [{
                "id": pair["id"], "guild_id": 88, "tournament_id": live["id"],
                "mode": "challenge", "a": {"user_id": pair["a"], "score": 1},
                "b": {"user_id": pair["b"], "score": 0},
            }],
        })
        with self.assertRaisesRegex(tournaments.TournamentError, "saved match"):
            tournaments.cancel(88, 15)
        self.assertEqual(tournaments.current(88)["status"], "running")

    def test_cancel_permission_boundary_in_service(self):
        self.joined()
        for invalid in (0, -1, None, False, "15"):
            with self.assertRaises(tournaments.TournamentError):
                tournaments.cancel(88, invalid)
        self.assertEqual(tournaments.current(88)["status"], "registration")

    def test_panel_state_and_compact_embed(self):
        empty = TournamentPanel(88)
        self.assertTrue(next(b for b in empty.children if b.label == "Join Tournament").disabled)
        self.assertTrue(next(b for b in empty.children if b.label == "Start Next Match").disabled)
        self.joined(format="round_robin")
        registration = TournamentHub(101, 88, admin=True)
        self.assertFalse(next(b for b in registration.children if b.label == "Start").disabled)
        self.assertTrue(next(b for b in registration.children if b.label == "Create").disabled)
        self.assertIn("round robin", status_embed(88).description.lower())
        tournaments.start(88)
        running = TournamentPanel(88)
        self.assertFalse(next(b for b in running.children
                              if b.label == "Start Next Match").disabled)
        self.assertTrue(next(b for b in running.children
                             if b.label == "Join Tournament").disabled)


class HouseProtectionTests(Fixture):
    def test_cooldown_prevents_immediate_house_hopping_and_rejoining_allowed(self):
        red = circuit.create_house(88, 101, "Red Shield")
        blue = circuit.create_house(88, 103, "Blue Shield")
        circuit.join_house(88, 102, red["id"], now=NOW)
        circuit.leave_house(88, 102, now=NOW)
        with self.assertRaisesRegex(circuit.CircuitError, "24-hour cooldown"):
            circuit.join_house(88, 102, blue["id"], now=NOW + timedelta(minutes=3))
        self.assertIsNone(circuit.house_for(88, 102))
        # Same allegiance is harmless to restore immediately.
        circuit.join_house(88, 102, red["id"], now=NOW + timedelta(minutes=4))
        circuit.leave_house(88, 102, now=NOW + timedelta(minutes=5))
        circuit.join_house(88, 102, blue["id"], now=NOW + timedelta(hours=26))
        self.assertEqual(circuit.house_for(88, 102), blue["id"])

    def test_invalid_user_and_structurally_corrupt_roster_fail_closed(self):
        for uid in (0, -10, False, None):
            with self.assertRaises(circuit.CircuitError):
                circuit.create_house(88, uid, "Broken House")
        red = circuit.create_house(88, 101, "Proper House")
        db = circuit.load_houses()
        db["guilds"]["88"]["houses"][red["id"]]["members"] = [{"not": "hashable"}]
        save_json(circuit.PATH, db)
        with self.assertRaises(circuit.CircuitError):
            circuit.guild_houses(88)
        self.assertTrue(any("houses.json" in issue
                            for issue in maintenance.inspect()["errors"]))

    def test_departure_file_is_included_in_verified_backup(self):
        circuit.create_house(88, 101, "Protected House")
        backup = maintenance.create_backup()
        snapshots = maintenance.verify_backup(backup)
        self.assertIn("houses.json", snapshots)
        self.assertIn(b"Protected House", snapshots["houses.json"])
        self.assertTrue(maintenance.inspect()["healthy"])

    def test_per_guild_house_locks_are_shared_across_views(self):
        self.assertIs(HOUSE_LOCKS[88], HOUSE_LOCKS[88])
        self.assertIsNot(HOUSE_LOCKS[88], HOUSE_LOCKS[99])

    def test_provenance_rejects_mismatched_seed_and_arena(self):
        event = self.joined()
        started = tournaments.start(88)
        p = tournaments.reserve_next(88)["match"]
        good = {
            "id": p["id"], "timestamp": NOW.isoformat(), "guild_id": 88,
            "mode": "challenge", "tournament_id": event["id"],
            "seed": p["seed"], "arena_key": p["arena_key"],
            "a": {"user_id": p["a"], "score": 3}, "b": {"user_id": p["b"], "score": 0},
            "passes": [],
        }
        tournaments.complete_match(88, event["id"], p["id"], p["a"], p["id"])
        data = tournaments.load_db()
        self.assertEqual(len(circuit.verified_results(
            88, tournaments=data, history={"matches": [good]})), 1)
        for changed in ({"seed": p["seed"]+1}, {"arena_key": "impossible_arena"}):
            corrupted = {**good, **changed}
            self.assertFalse(circuit.verified_results(
                88, tournaments=data, history={"matches": [corrupted]}))


class UIContractTests(Fixture):
    @staticmethod
    def check_view(view: discord.ui.View):
        assert len(view.children) <= 25
        assert all(child.row in range(5) for child in view.children)
        for row in range(5):
            children = [x for x in view.children if x.row == row]
            if any(isinstance(x, (discord.ui.Select, discord.ui.UserSelect))
                   for x in children):
                assert len(children) == 1, (type(view).__name__, row)
            else:
                assert len(children) <= 5, (type(view).__name__, row)
        for child in view.children:
            if isinstance(child, discord.ui.Select):
                assert 1 <= len(child.options) <= 25
            if isinstance(child, discord.ui.Button):
                assert len(child.label or "") <= 80

    def test_navigation_groups_and_all_critical_screen_layouts(self):
        pages = [
            MainMenuView(101, True),
            VersionPage(101), StartView(101),
            CircuitHub(101, None), CircuitPage(101, None),
            CircuitPage(101, None, "arenas"),
            CircuitPage(101, None, "houses"),
            CircuitPage(101, None, "herald"),
            CircuitPage(101, None, "hall"),
            HousePage(101, None), HouseMissionsPage(101, None),
            TournamentHub(101, None, True),
            TournamentHub(101, None, False),
            ConfirmTournamentCancel(101, None),
            TournamentPanel(),
        ]
        for view in pages:
            with self.subTest(page=type(view).__name__):
                self.check_view(view)
                if isinstance(view, OwnedView):
                    self.assertTrue(any(getattr(x, "label", "") == "Main Menu"
                                        for x in view.children))
                    card = view.make_embed()
                    self.assertLessEqual(len(card.title or ""), 256)
                    self.assertLessEqual(len(card.description or ""), 4096)
                    self.assertLessEqual(len(card.fields), 25)
                    for field in card.fields:
                        self.assertLessEqual(len(field.name), 256)
                        self.assertLessEqual(len(field.value), 1024)

    def test_custom_tournament_editor_provides_five_short_inputs(self):
        modal = AdvancedTournamentModal()
        self.assertEqual(len(modal.children), 5)
        self.assertTrue(all(len(item.label) <= 45 for item in modal.children))
        self.assertTrue(all(getattr(item, "max_length", 100) <= 100
                            for item in modal.children))



class AssetAuditTests(unittest.TestCase):
    def test_real_pngs_pass_verification_and_metadata_checks(self):
        """Regression: Pillow.verify() must precede channel/size inspection."""
        from PIL import Image
        from services.asset_health import audit_assets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arena = root / "assets/jousting/arenas/royal_lists.png"
            knight = root / "assets/jousting/knights/red_knight/idle/red_knight_idle_left_01.png"
            arena.parent.mkdir(parents=True, exist_ok=True)
            knight.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (320, 180), (25, 50, 90, 255)).save(arena)
            Image.new("RGBA", (64, 64), (255, 20, 30, 0)).save(knight)
            report = audit_assets(root)
            self.assertEqual(report["present"], 2)
            self.assertFalse(report["errors"], report["errors"])
            self.assertGreater(report["missing"], 0)
            self.assertFalse(report["ready_for_full_graphics"])

    def test_corrupt_png_reports_error_without_crashing(self):
        from services.asset_health import audit_assets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "assets/jousting/arenas/royal_lists.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"not really a PNG")
            result = audit_assets(root)
            self.assertTrue(result["errors"])
            self.assertFalse(result["ready_for_full_graphics"])
