import unittest
from unittest.mock import patch

import tools.config_loader as config_loader


class TestConfigLoaderCache(unittest.TestCase):
    def setUp(self):
        config_loader._CACHE["data"] = None
        config_loader._CACHE["mtime"] = None
        config_loader._CACHE["checked_at"] = 0.0

    def test_cache_hit_within_ttl(self):
        with patch("tools.config_loader._safe_load", return_value=({"display": {"title_bar": True}}, 100.0)) as safe_load, \
             patch("tools.config_loader.time.time", side_effect=[1000.0, 1000.2]):
            first = config_loader.load_config()
            second = config_loader.load_config()

        self.assertEqual(first, second)
        self.assertEqual(safe_load.call_count, 1)

    def test_reload_when_mtime_changes(self):
        with patch("tools.config_loader._safe_load", side_effect=[({"narrative": {"style": "epic"}}, 100.0), ({"narrative": {"style": "brutal"}}, 200.0)]), \
             patch("tools.config_loader.time.time", side_effect=[1000.0, 1002.0]), \
             patch("tools.config_loader.os.path.getmtime", return_value=200.0):
            first = config_loader.load_config()
            second = config_loader.load_config()

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
