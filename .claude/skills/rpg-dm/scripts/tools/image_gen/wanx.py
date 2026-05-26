"""Bailian image generation provider (Alibaba Cloud).

Supports both wanx-v1 (ImageSynthesis API) and wan2.6 (ImageGeneration API).
Set model via config.json: image_gen.providers.wanx.model = "wan2.6-image"
"""

import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from .base import ImageGenerator
try:
    from config_loader import load_config
except ImportError:
    from tools.config_loader import load_config

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WANX_DEFAULT_NEGATIVE = "文字, 水印, UI, HUD, 人物, 角色, 人脸, 明亮鲜艳, 卡通, 动漫"
WANX_DEFAULT_SIZE = "1280*720"

ACTIVE_WORLD_FILE = os.path.join(ROOT, "rules", "settings.json")


def _get_active_world():
    try:
        with open(ACTIVE_WORLD_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("active_world", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def _is_placeholder_key(value):
    if not value:
        return True
    cleaned = value.strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    placeholders = {
        "在此填入你的百炼 api key",
        "在此填入你的api key",
        "your_api_key_here",
        "<api_key>",
        "changeme",
    }
    return lowered in placeholders


def _get_api_key():
    """Read API key with backward-compatible fallback chain.

    1. DASHSCOPE_API_KEY env var
    2. image_gen.providers.wanx.api_key
    3. services.dashscope_api_key (legacy)
    """
    env_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not _is_placeholder_key(env_key):
        return env_key

    cfg = load_config()

    key = cfg.get("image_gen", {}).get("providers", {}).get("wanx", {}).get("api_key", "").strip()
    if not _is_placeholder_key(key):
        return key

    key = cfg.get("services", {}).get("dashscope_api_key", "").strip()
    if not _is_placeholder_key(key):
        return key

    return ""


class Provider(ImageGenerator):
    """Bailian provider supporting wanx-v1 (ImageSynthesis) and wan2.6 (ImageGeneration).

    Model can be configured via config.json:
      image_gen.providers.wanx.model = "wan2.6-image"
    Defaults to "wanx-v1" if not set.
    """

    def _get_model(self) -> str:
        cfg = load_config()
        return cfg.get("image_gen", {}).get("providers", {}).get("wanx", {}).get("model", "wanx-v1")

    def _use_generation_api(self) -> bool:
        """wan2.6 models use ImageGeneration API; wanx-v1 uses ImageSynthesis."""
        return self._get_model().startswith("wan2")

    def is_available(self) -> bool:
        try:
            if self._use_generation_api():
                import dashscope.aigc.image_generation  # noqa: F401
            else:
                import dashscope.aigc.image_synthesis  # noqa: F401
        except ImportError:
            return False
        return bool(_get_api_key())

    def get_default_size(self) -> str:
        return WANX_DEFAULT_SIZE

    def get_default_negative(self) -> str:
        return WANX_DEFAULT_NEGATIVE

    # ── async path ────────────────────────────────────────────

    def submit(self, prompt: str, negative: Optional[str] = None,
               size: Optional[str] = None, style: str = "scene") -> str:
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        model = self._get_model()
        negative = negative or WANX_DEFAULT_NEGATIVE
        size = size or WANX_DEFAULT_SIZE

        if self._use_generation_api():
            from dashscope.aigc.image_generation import ImageGeneration
            response = ImageGeneration.async_call(
                model=model,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                negative_prompt=negative,
                size=size,
                n=1,
                api_key=api_key,
            )
        else:
            from dashscope.aigc.image_synthesis import ImageSynthesis
            response = ImageSynthesis.call(
                model=model,
                prompt=prompt,
                negative_prompt=negative,
                n=1,
                size=size,
                api_key=api_key,
            )

        if response.status_code != 200:
            raise RuntimeError(f"wanx API returned {response.status_code}: {response.message}")

        return response.output.task_id

    def poll(self, task_id: str) -> Optional[Path]:
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        if self._use_generation_api():
            from dashscope.aigc.image_generation import ImageGeneration
            resp = ImageGeneration.fetch(task_id, api_key=api_key)
        else:
            from dashscope.aigc.image_synthesis import ImageSynthesis
            resp = ImageSynthesis.fetch(task_id, api_key=api_key)

        if resp.status_code != 200:
            raise RuntimeError(f"wanx poll failed: {resp.message}")

        output = resp.output
        task_status = output.task_status

        if task_status == "SUCCEEDED":
            if self._use_generation_api():
                image_url = output.choices[0].message.content[0]["image"]
            else:
                image_url = output.results[0].url
            suffix = ".png"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            try:
                req = urllib.request.Request(image_url, headers={"User-Agent": "my-rpg-bg-generator/1.0"})
                with urllib.request.urlopen(req, timeout=60) as src:
                    tmp.write(src.read())
                tmp.close()
                return Path(tmp.name)
            except Exception:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
                raise

        if task_status == "FAILED":
            raise RuntimeError(f"wanx task {task_id} failed: {output.message or 'Unknown error'}")

        return None

    # ── synchronous path ─────────────────────────────────────

    def generate(self, prompt: str, negative: Optional[str] = None,
                 size: Optional[str] = None, style: str = "scene") -> Path:
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        model = self._get_model()
        negative = negative or WANX_DEFAULT_NEGATIVE
        size = size or WANX_DEFAULT_SIZE

        if self._use_generation_api():
            from dashscope.aigc.image_generation import ImageGeneration
            result = ImageGeneration.call(
                model=model,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                negative_prompt=negative,
                size=size,
                n=1,
                api_key=api_key,
            )
        else:
            from dashscope.aigc.image_synthesis import ImageSynthesis
            task_id = ImageSynthesis.call(
                model=model,
                prompt=prompt,
                negative_prompt=negative,
                n=1,
                size=size,
                api_key=api_key,
            )
            # For wanx-v1, call() returns async task — wait for it
            result = ImageSynthesis.wait(task_id.output.task_id, api_key=api_key)

        if result.status_code != 200:
            raise RuntimeError(f"wanx generation failed: {result.output}")

        output = result.output
        if hasattr(output, 'task_status') and output.task_status != "SUCCEEDED":
            raise RuntimeError(f"wanx generation failed: {output}")

        if self._use_generation_api():
            image_url = output.choices[0].message.content[0]["image"]
        else:
            image_url = output.results[0].url
        suffix = ".png"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            req = urllib.request.Request(image_url, headers={"User-Agent": "my-rpg-bg-generator/1.0"})
            with urllib.request.urlopen(req, timeout=60) as src:
                tmp.write(src.read())
            tmp.close()
            return Path(tmp.name)
        except Exception:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            raise
