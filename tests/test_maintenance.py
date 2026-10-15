"""v0.9.0 storage safety, verified restore and conservative repair regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import maintenance as m
from services.storage import save_json, load_json


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.data = root / "data"
        self.backups = root / "backups"
        self.data.mkdir()
        self.patches = [
            patch.object(m, "DATA_DIR", self.data),
            patch.object(m, "BACKUP_DIR", self.backups),
        ]
        for ctx in self.patches:
            ctx.start()

    def tearDown(self):
        for ctx in reversed(self.patches):
            ctx.stop()
        self.temp.cleanup()

    def write(self, name, payload):
        save_json(str(self.data / name), payload)

    def test_backup_roundtrip_and_checksums(self):
        original = {"matches": [{"id": "a", "guild_id": 1, "a": {}, "b": {}}]}
        self.write("matches.json", original)
        self.write("tournaments.json", {"guilds": {}})
        name = m.create_backup()
        self.assertIn(name, m.backup_names())
        self.assertEqual(len(m.verify_backup(name)), 2)
        self.write("matches.json", {"matches": []})
        safety = m.restore_backup(name)
        self.assertNotEqual(safety, name)
        self.assertEqual(load_json(str(self.data / "matches.json"), {}), original)
        self.assertEqual(len(m.verify_backup(safety)), 2)

    def test_tampered_snapshot_is_never_restored(self):
        self.write("knights.json", {"knights": {"123": {"name": "Test"}}})
        snapshot = m.create_backup()
        (self.backups / snapshot / "knights.json").write_text('{"knights":{}}')
        with self.assertRaisesRegex(m.MaintenanceError, "verification failed"):
            m.restore_backup(snapshot)
        self.assertIn("123", load_json(str(self.data / "knights.json"), {})["knights"])

    def test_backup_id_cannot_traverse_directories(self):
        for name in ("../storage", "/tmp/abc", "", "bkp-evil", "bkp-20261225T000000Z-zzzzzzzz"):
            with self.assertRaises(m.MaintenanceError):
                m.verify_backup(name)

    def test_missing_files_are_initialized_only_after_confirmed_repair(self):
        check = m.inspect()
        self.assertTrue(check["healthy"])
        self.assertEqual(len(check["warnings"]), len(m.SCHEMAS))
        plan = m.repair()
        self.assertFalse(plan["applied"])
        self.assertEqual(len(plan["changes"]), len(m.SCHEMAS))
        self.assertFalse(list(self.data.iterdir()))
        applied = m.repair(apply=True)
        self.assertTrue(applied["applied"])
        self.assertEqual(len(applied["changes"]), len(m.SCHEMAS))
        self.assertTrue((self.backups / applied["backup"]).exists())
        self.assertEqual(load_json(str(self.data / "matches.json"), {}), {"matches": []})
        self.assertEqual(m.repair()["changes"], [])

    def test_duplicate_identical_matches_are_repaired_without_changing_wins(self):
        first = {"id": "match-1", "guild_id": 12, "mode": "challenge",
                 "a": {"user_id": 1, "score": 3}, "b": {"user_id": 2, "score": 0},
                 "passes": []}
        self.write("matches.json", {"matches": [first, dict(first), {"id": "match-2"}]})
        plan = m.repair()
        self.assertIn("duplicate", " ".join(plan["changes"]))
        m.repair(apply=True)
        saved = load_json(str(self.data / "matches.json"), {})["matches"]
        self.assertEqual([x["id"] for x in saved], ["match-1", "match-2"])

    def test_conflicting_match_ids_block_repairs(self):
        self.write("matches.json", {"matches": [
            {"id": "duplicate", "score": 3},
            {"id": "duplicate", "score": 9},
        ]})
        status = m.inspect()
        self.assertFalse(status["healthy"])
        with self.assertRaisesRegex(m.MaintenanceError, "Unsafe repair"):
            m.repair(apply=True)
        self.assertEqual(len(load_json(str(self.data / "matches.json"), {})["matches"]), 2)

    def test_corrupt_json_is_quarantined_before_verified_restore(self):
        self.write("knights.json", {"knights": {"42": {"name": "Saved"}}})
        snapshot = m.create_backup()
        (self.data / "knights.json").write_text('{"broken"', encoding="utf-8")
        with self.assertRaises(m.MaintenanceError):
            m.repair(apply=True)
        quarantine = m.restore_backup(snapshot)
        self.assertTrue(quarantine.startswith("quarantine-"))
        self.assertEqual((self.backups / quarantine / "knights.json").read_text(), '{"broken"')
        self.assertEqual(load_json(str(self.data / "knights.json"), {})["knights"]["42"]["name"], "Saved")

    def test_wrong_json_shapes_block_restore_backup_creation(self):
        (self.data / "horses.json").write_text('{"horses":[]}', encoding="utf-8")
        self.assertFalse(m.inspect()["healthy"])
        with self.assertRaises(m.MaintenanceError):
            m.create_backup()
        with self.assertRaises(m.MaintenanceError):
            m.repair(apply=True)

    def test_atomic_json_write_survives_repeated_updates(self):
        for index in range(5):
            self.write("progression.json", {"guilds": {"1": {"counter": index}}})
        self.assertEqual(load_json(str(self.data / "progression.json"), {})["guilds"]["1"]["counter"], 4)
        self.assertEqual(list(self.data.glob("*.tmp")), [])

    def test_unknown_fields_survive_safe_repair(self):
        self.write("knights.json", {"custom_legacy": [42, 21]})
        m.repair(apply=True)
        value = load_json(str(self.data / "knights.json"), {})
        self.assertEqual(value["custom_legacy"], [42, 21])
        self.assertEqual(value["knights"], {})


if __name__ == "__main__":
    unittest.main()
