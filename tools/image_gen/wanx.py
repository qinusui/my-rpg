"""Bailian wanx-v1 image generation provider (Alibaba Cloud)."""

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

STYLE_SUFFIX = {
    "scene": (
        "暗黑奇幻概念艺术风格，电影级布光，体积光，"
        "氛围感强，低饱和度色调，油画画风，广角定场镜头，"
        "无人物无角色，纯粹环境场景"
    ),
    "combat": (
        "暗黑奇幻概念艺术风格，动态战斗场景，戏剧性侧光，"
        "怪物居于画面焦点，环境作为衬托，低饱和度，"
        "电影级布光，油画画风"
    ),
    "boss": (
        "史诗级暗黑奇幻概念艺术风格，强烈的明暗对比（chiaroscuro），"
        "巨大体量感，压迫性构图，灾难氛围，电影级布光，"
        "低饱和度，油画画风"
    ),
}

CLOUD_CHAMBER_STYLE_SUFFIX = {
    "scene": (
        "后启示录废土概念艺术风格，锈蚀金属与混凝土废墟，"
        "弥漫的雾霾与乙醇蒸气，冷灰色调与低饱和度，"
        "电影级体积光穿过尘埃，环境氛围感极强，"
        "广角定场镜头，无人物无角色，纯粹环境场景"
    ),
    "combat": (
        "后启示录废土概念艺术风格，动态战斗场景，冷白侧光穿过雾气，"
        "扭曲的变异生物居于画面焦点，工业废墟作为衬托，"
        "低饱和度冷色调，电影级布光，粗粝质感"
    ),
    "boss": (
        "史诗级后启示录概念艺术风格，强烈的明暗对比（chiaroscuro），"
        "巨型未知机械或变异巨兽，压迫性构图，"
        "灾难氛围与工业恐惧，电影级布光，"
        "低饱和度冷灰色调，粗粝质感"
    ),
}

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
    """Bailian wanx-v1 provider.

    Implements both generate() (blocking) and submit()/poll() (async).
    bg_generator.py detects submit/poll via hasattr and prefers the
    async path when available.
    """

    def is_available(self) -> bool:
        try:
            import dashscope.aigc.image_synthesis  # noqa: F401
        except ImportError:
            return False
        return bool(_get_api_key())

    def get_style_suffix(self, style: str) -> str:
        world = _get_active_world()
        if world == "cloud_chamber":
            return CLOUD_CHAMBER_STYLE_SUFFIX.get(style, CLOUD_CHAMBER_STYLE_SUFFIX["scene"])
        return STYLE_SUFFIX.get(style, STYLE_SUFFIX["scene"])

    def get_default_size(self) -> str:
        return WANX_DEFAULT_SIZE

    def get_default_negative(self) -> str:
        return WANX_DEFAULT_NEGATIVE

    # ── async path ────────────────────────────────────────────

    def submit(self, prompt: str, negative: Optional[str] = None,
               size: Optional[str] = None, style: str = "scene") -> str:
        from dashscope.aigc.image_synthesis import ImageSynthesis

        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        style_suffix = self.get_style_suffix(style)
        full_prompt = f"{prompt}, {style_suffix}"

        response = ImageSynthesis.call(
            model="wanx-v1",
            prompt=full_prompt,
            negative_prompt=negative or WANX_DEFAULT_NEGATIVE,
            n=1,
            size=size or WANX_DEFAULT_SIZE,
            api_key=api_key,
        )

        if response.status_code != 200:
            raise RuntimeError(f"wanx API returned {response.status_code}: {response.message}")

        return response.output.task_id

    def poll(self, task_id: str) -> Optional[Path]:
        from dashscope.aigc.image_synthesis import ImageSynthesis

        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY not set")

        resp = ImageSynthesis.fetch(task_id, api_key=api_key)
        if resp.status_code != 200:
            raise RuntimeError(f"wanx poll failed: {resp.message}")

        output = resp.output
        task_status = output.task_status

        if task_status == "SUCCEEDED":
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

        # PENDING or RUNNING
        return None

    # ── synchronous path (submit + block) ─────────────────────

    def generate(self, prompt: str, negative: Optional[str] = None,
                 size: Optional[str] = None, style: str = "scene") -> Path:
        task_id = self.submit(prompt, negative, size, style)

        from dashscope.aigc.image_synthesis import ImageSynthesis
        api_key = _get_api_key()

        result = ImageSynthesis.wait(task_id, api_key=api_key)
        if result.status_code != 200 or result.output.task_status != "SUCCEEDED":
            raise RuntimeError(f"wanx generation failed: {result.output}")

        image_url = result.output.results[0].url
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
