import unittest
from unittest.mock import patch

import tools.session_enrich as session_enrich


class TestSessionExportSchema(unittest.TestCase):
    def test_export_contains_clocks_and_computed_flags(self):
        fake_state = {
            "player_name": "测试者",
            "player_class": "wanderer",
            "player_race": "human",
            "turn_count": 12,
            "chapter": 3,
            "current_location": "alley",
            "clocks": {
                "strength": {"filled": 5, "max": 6},
                "constitution": {"filled": 2, "max": 8},
            },
            "inventory": [],
            "history": ["h1"],
            "clues": ["c1"],
            "dm_log": [],
        }

        captured = {}

        def fake_save(path, data):
            captured["path"] = path
            captured["data"] = data

        with patch("tools.session_enrich.load_json", return_value=fake_state), \
             patch("tools.session_enrich.save_json", side_effect=fake_save):
            session_enrich.export_session("cloud_chamber", "rules/cloud_chamber", "schema_check")

        exported = captured["data"]
        self.assertIn("clocks", exported)
        self.assertIn("flags_active", exported)
        self.assertIsInstance(exported["flags_active"], list)
        self.assertNotIn("attributes", exported)


if __name__ == "__main__":
    unittest.main()
