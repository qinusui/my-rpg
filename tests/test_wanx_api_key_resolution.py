import os
import unittest
from unittest.mock import patch

from tools.image_gen import wanx


class TestWanxApiKeyResolution(unittest.TestCase):
    def test_env_has_highest_priority(self):
        cfg = {
            "image_gen": {"providers": {"wanx": {"api_key": "cfg-new"}}},
            "services": {"dashscope_api_key": "cfg-legacy"},
        }
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "env-key"}, clear=False):
            with patch("tools.image_gen.wanx.load_config", return_value=cfg):
                self.assertEqual(wanx._get_api_key(), "env-key")

    def test_new_config_precedes_legacy_when_env_missing(self):
        cfg = {
            "image_gen": {"providers": {"wanx": {"api_key": "cfg-new"}}},
            "services": {"dashscope_api_key": "cfg-legacy"},
        }
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": ""}, clear=False):
            with patch("tools.image_gen.wanx.load_config", return_value=cfg):
                self.assertEqual(wanx._get_api_key(), "cfg-new")

    def test_legacy_used_when_new_missing(self):
        cfg = {
            "image_gen": {"providers": {"wanx": {"api_key": ""}}},
            "services": {"dashscope_api_key": "cfg-legacy"},
        }
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": ""}, clear=False):
            with patch("tools.image_gen.wanx.load_config", return_value=cfg):
                self.assertEqual(wanx._get_api_key(), "cfg-legacy")

    def test_placeholder_is_not_treated_as_valid_key(self):
        cfg = {
            "image_gen": {"providers": {"wanx": {"api_key": "在此填入你的百炼 API Key"}}},
            "services": {"dashscope_api_key": ""},
        }
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": ""}, clear=False):
            with patch("tools.image_gen.wanx.load_config", return_value=cfg):
                self.assertEqual(wanx._get_api_key(), "")


if __name__ == "__main__":
    unittest.main()
