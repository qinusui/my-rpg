#!/usr/bin/env python3
"""
Unified background manager for my-rpg — switching + generation in one tool.

Quick reference:
  bg.py --init                           One-time WT profile detection
  bg.py --set <location_id>              Switch to location background (auto-polls)
  bg.py --combat <mode> --monster <key>  Switch to combat background (auto-polls)
  bg.py --mood <key>                     Apply mood or narrative beat atmosphere
  bg.py --reset                          Restore original WT background
  bg.py --status                         Show current config + pending tasks

  bg.py --submit <scene_id> --prompt "..." [--style scene|combat|boss] [--tags "..."] [--mood ...]
  bg.py --poll                           Manually check pending tasks (rarely needed)
  bg.py --skip <scene_id>                Delete image + record prompt for regeneration
  bg.py --pin <scene_id>                 Copy image to _shared for cross-world reuse
  bg.py --export [--filter-tag <t>] [--filter-mood <m>] [--filter-world <w>]
                                         Export images to zip for sharing between players
  bg.py --import <zip_path>             Import shared images, dedup by SHA256
"""

import json
import os
import sys
import argparse
import io
import time
import random
import shutil
import urllib.request
import hashlib
import zipfile
import tempfile
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "rules", "settings.json")
PENDING_FILE = os.path.join(ROOT, "rules", "_shared", "_pending_tasks.json")
INDEX_FILE = os.path.join(ROOT, "rules", "_shared", "index.json")
STATE_SNAPSHOT_FILE = os.path.join(ROOT, "state.json")

from image_gen import get_generator
try:
    from config_loader import load_config
except ImportError:
    from tools.config_loader import load_config

# ═══════════════════════════════════════════════════════════════
# Config helpers
# ═══════════════════════════════════════════════════════════════

def _is_bg_enabled(category=None):
    bg_cfg = load_config().get("display", {}).get("background_image", True)
    if isinstance(bg_cfg, bool):
        return bg_cfg
    if not bg_cfg.get("enabled", True):
        return False
    if category:
        return bg_cfg.get(category, True)
    return True


def _is_auto_generate_enabled():
    bg_cfg = load_config().get("display", {}).get("background_image", True)
    if isinstance(bg_cfg, bool):
        return bg_cfg
    if not bg_cfg.get("enabled", True):
        return False
    return bg_cfg.get("auto_generate", True)


def _get_style_prompt():
    cfg = load_config()
    return cfg.get("image_gen", {}).get("style_prompt", "").strip()


def _get_active_world():
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("active_world", "shattered_crown")



# ═══════════════════════════════════════════════════════════════
# Settings cache
# ═══════════════════════════════════════════════════════════════

def _load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# WT path detection & profile management
# ═══════════════════════════════════════════════════════════════

def _find_wt_settings():
    store = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Microsoft", "Windows Terminal", "settings.json")
    preinstalled_base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages")
    preinstalled = None
    if os.path.isdir(preinstalled_base):
        for name in os.listdir(preinstalled_base):
            if name.startswith("Microsoft.WindowsTerminal"):
                candidate = os.path.join(preinstalled_base, name, "LocalState", "settings.json")
                if os.path.isfile(candidate):
                    preinstalled = candidate
                    break
    if os.path.isfile(store):
        return store, "Store"
    if preinstalled and os.path.isfile(preinstalled):
        return preinstalled, "Preinstalled"
    return None, "WT settings.json not found"


def _load_wt_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_wt_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _find_profile(wt_data, profile_guid):
    for p in wt_data.get("profiles", {}).get("list", []):
        if p.get("guid", "").lower() == profile_guid.lower():
            return p, "profile"
    for p in wt_data.get("profiles", {}).get("list", []):
        g = p.get("guid", "")
        if g and profile_guid.startswith(g[:20]):
            return p, "profile"
    defaults = wt_data.get("profiles", {}).get("defaults")
    if defaults:
        return defaults, "defaults"
    return None, None


def _auto_detect_profile(wt_data):
    default_guid = wt_data.get("defaultProfile")
    if default_guid:
        profiles = wt_data.get("profiles", {}).get("list", [])
        for p in profiles:
            if p.get("guid", "").lower() == default_guid.lower() and not p.get("hidden"):
                return default_guid, p.get("name", "default")
    return None, "Could not auto-detect profile"


# ═══════════════════════════════════════════════════════════════
# Background config (merged shared + world)
# ═══════════════════════════════════════════════════════════════

def _load_backgrounds_config():
    settings = _load_settings()
    world = settings.get("active_world", "shattered_crown")

    shared_path = os.path.join(ROOT, "rules", "_shared", "backgrounds.json")
    shared = {}
    if os.path.exists(shared_path):
        with open(shared_path, "r", encoding="utf-8") as f:
            shared = json.load(f)

    world_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    world_cfg = {}
    if os.path.exists(world_path):
        with open(world_path, "r", encoding="utf-8") as f:
            world_cfg = json.load(f)

    return {
        "locations": {**shared.get("locations", {}), **world_cfg.get("locations", {})},
        "combat":    {**shared.get("combat", {}), **world_cfg.get("combat", {})},
        "moods":     {**shared.get("moods", {}), **world_cfg.get("moods", {})},
        "narrative": {**shared.get("narrative", {}), **world_cfg.get("narrative", {})},
    }


def _resolve_bg_path(filename):
    if filename is None:
        return None
    settings = _load_settings()
    world = settings.get("active_world", "shattered_crown")
    world_bg = os.path.join(ROOT, "rules", world, "backgrounds", filename)
    if os.path.isfile(world_bg):
        return world_bg
    shared_bg = os.path.join(ROOT, "rules", "_shared", "backgrounds", filename)
    if os.path.isfile(shared_bg):
        return shared_bg
    return world_bg


# ═══════════════════════════════════════════════════════════════
# WT write (atomic + fade)
# ═══════════════════════════════════════════════════════════════

def _smoothstep(t):
    return t * t * (3 - 2 * t)


def _write_bg_atomic(term, image_path, opacity):
    wt_path = term["wt_settings_path"]
    wt_data = _load_wt_json(wt_path)
    profile, source = _find_profile(wt_data, term["profile_guid"])
    if profile is None:
        print(json.dumps({"error": "Profile not found in WT settings"}, ensure_ascii=False))
        sys.exit(1)
    profile["backgroundImage"] = image_path.replace("\\", "/")
    profile["backgroundImageOpacity"] = round(float(opacity), 2)
    profile["backgroundImageStretchMode"] = "uniformToFill"
    _save_wt_json(wt_path, wt_data)


def _write_opacity_only(wt_path, profile_guid, opacity):
    wt_data = _load_wt_json(wt_path)
    profile, source = _find_profile(wt_data, profile_guid)
    if profile is None:
        return
    profile["backgroundImageOpacity"] = opacity
    _save_wt_json(wt_path, wt_data)


def _fade_opacity(term, from_opacity, to_opacity, steps=8, duration=0.4):
    if abs(from_opacity - to_opacity) < 0.01:
        return
    wt_path = term["wt_settings_path"]
    profile_guid = term["profile_guid"]
    for i in range(1, steps + 1):
        t = i / steps
        eased = _smoothstep(t)
        current = from_opacity + (to_opacity - from_opacity) * eased
        _write_opacity_only(wt_path, profile_guid, round(current, 3))
        time.sleep(duration / steps)


def _write_background(term, image_path, opacity, transition=True):
    if not transition:
        _write_bg_atomic(term, image_path, opacity)
        return
    current_opacity = term.get("current_opacity", opacity)
    _fade_opacity(term, current_opacity, 0.02, steps=10, duration=0.55)
    _write_bg_atomic(term, image_path, 0.02)
    _fade_opacity(term, 0.02, opacity, steps=12, duration=0.85)


# ═══════════════════════════════════════════════════════════════
# Pending tasks (async generation)
# ═══════════════════════════════════════════════════════════════

def _load_pending():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_pending(tasks):
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# Shared index (cross-world reuse)
# ═══════════════════════════════════════════════════════════════

CACHE_TAG_THRESHOLD = 3


def _load_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(entries):
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _find_cached(mood, tags):
    if not mood or not tags:
        return None
    query_tags = set(t.strip() for t in tags.split(",") if t.strip())
    if not query_tags:
        return None
    entries = _load_index()
    best, best_overlap = None, 0
    for entry in entries:
        if entry.get("mood") != mood:
            continue
        overlap = len(query_tags & set(entry.get("tags", [])))
        if overlap >= CACHE_TAG_THRESHOLD and overlap > best_overlap:
            best, best_overlap = entry, overlap
    return best


def _index_add(file, mood, tags, provider, pinned_from):
    entries = _load_index()
    for e in entries:
        if e.get("file") == file:
            return
    entries.append({
        "file": file,
        "mood": mood or "",
        "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
        "provider": provider,
        "pinned_from": pinned_from,
        "pinned_at": datetime.now().isoformat(),
    })
    _save_index(entries)


# ═══════════════════════════════════════════════════════════════
# Background registration helpers
# ═══════════════════════════════════════════════════════════════

def _ensure_world_backgrounds_config(world):
    path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "_comment": f"{world} 专属背景图。引擎合并 shared + world（world 覆盖同名 key）。",
            "locations": {}, "combat": {}, "moods": {}, "narrative": {}
        }, f, ensure_ascii=False, indent=2)


def _register_scene(world, scene_id, filename):
    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    with open(bg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("locations", {})
    cfg["locations"][scene_id] = {"file": filename, "mood": f"AI 生成 — {scene_id}"}
    with open(bg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _register_combat_entry(world, scene_id, filename):
    monster_key = scene_id[len("combat_"):] if scene_id.startswith("combat_") else scene_id
    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    with open(bg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("combat", {})
    cfg["combat"][monster_key] = {"file": filename, "opacity": 0.40, "mood": f"AI 生成 — {monster_key}"}
    with open(bg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _register_category(world, scene_id, filename, category):
    """Register a background under moods or narrative bucket (keyed by suffix after prefix_)."""
    key = scene_id[len(category.rstrip("s")) + 1:]  # "mood_safe" → "safe", "narrative_escape" → "escape"
    # Default opacity mapping by mood name
    mood_opacity = {
        "safe": 0.2, "normal": 0.3, "tension": 0.4, "danger": 0.45, "tragedy": 0.15,
        "discovery": 0.35, "escape": 0.4, "stealth": 0.25, "revelation": 0.35, "aftermath": 0.2,
    }
    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    with open(bg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault(category, {})
    cfg[category][key] = {
        "file": filename,
        "opacity": mood_opacity.get(key, 0.3),
        "label": f"AI 生成 — {key}",
    }
    with open(bg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _install_image(temp_path, world, scene_id, filename):
    bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
    os.makedirs(bg_dir, exist_ok=True)
    dst = os.path.join(bg_dir, filename)
    shutil.copy2(str(temp_path), dst)
    try:
        os.unlink(str(temp_path))
    except OSError:
        pass
    return dst


# ═══════════════════════════════════════════════════════════════
# Metadata / rejected helpers
# ═══════════════════════════════════════════════════════════════

def _meta_path(world, scene_id):
    return os.path.join(ROOT, "rules", world, "backgrounds", f"{scene_id}.meta.json")


def _rejected_path(world):
    return os.path.join(ROOT, "rules", world, "backgrounds", "_rejected.json")


def _load_rejected(world):
    path = _rejected_path(world)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_rejected(world, data):
    path = _rejected_path(world)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_meta(world, scene_id, filename, prompt, tags, mood, style):
    meta = {
        "file": filename,
        "scene_id": scene_id,
        "mood": mood or "",
        "prompt": prompt,
        "tags": [t.strip() for t in (tags or "").split(",") if t.strip()],
        "style": style,
        "generated_at": datetime.now().isoformat(),
        "pinned": False,
    }
    with open(_meta_path(world, scene_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _enrich_negative(negative, scene_id, world):
    rejected = _load_rejected(world)
    entry = rejected.get(scene_id)
    if not entry or not entry.get("rejected_prompts"):
        return negative
    last_prompt = entry["rejected_prompts"][-1]
    return (negative or "") + f", 不同于: {last_prompt[:80]}"


# ═══════════════════════════════════════════════════════════════
# Auto-poll — process completed async tasks before switching
# ═══════════════════════════════════════════════════════════════

def _auto_poll():
    """Process any completed async generation tasks. Called before --set/--combat."""
    gen = get_generator()
    if not hasattr(gen, 'poll'):
        return

    pending = _load_pending()
    active = [t for t in pending if t.get("status") in ("PENDING", "RUNNING")]
    if not active:
        return

    for task in active:
        task_id = task["task_id"]
        try:
            tmp_path = gen.poll(task_id)
        except Exception:
            task["status"] = "FAILED"
            continue

        if tmp_path is not None:
            scene_id = task["scene_id"]
            world = task["world"]
            style = task.get("style", "scene")
            filename = f"{scene_id}.png"
            try:
                _install_image(tmp_path, world, scene_id, filename)
                _ensure_world_backgrounds_config(world)
                if style in ("combat", "boss"):
                    _register_combat_entry(world, scene_id, filename)
                elif scene_id.startswith("mood_"):
                    _register_category(world, scene_id, filename, "moods")
                elif scene_id.startswith("narrative_"):
                    _register_category(world, scene_id, filename, "narrative")
                else:
                    _register_scene(world, scene_id, filename)
                _write_meta(world, scene_id, filename,
                            task.get("prompt", ""), task.get("tags", ""),
                            task.get("mood", ""), style)
                _index_add(filename, task.get("mood", ""), task.get("tags", ""),
                           gen.name, world)
                task["status"] = "DONE"
                task["completed_at"] = datetime.now().isoformat()
            except Exception:
                task["status"] = "FAILED"
        else:
            task["status"] = "RUNNING"

    _save_pending(pending)


# ═══════════════════════════════════════════════════════════════
# Commands: switching
# ═══════════════════════════════════════════════════════════════

def cmd_init(profile_guid_override=None):
    wt_path, label = _find_wt_settings()
    if wt_path is None:
        print(json.dumps({"error": label}, ensure_ascii=False))
        sys.exit(1)

    wt_data = _load_wt_json(wt_path)

    if profile_guid_override:
        profile_guid = profile_guid_override
    else:
        profile_guid = os.environ.get("WT_PROFILE_ID", "")
    if not profile_guid:
        profile_guid, auto_label = _auto_detect_profile(wt_data)
        if profile_guid is None:
            print(json.dumps({"error": auto_label}, ensure_ascii=False))
            sys.exit(1)
        print(f"[auto-detected profile: {auto_label}]", file=sys.stderr)

    profile, source = _find_profile(wt_data, profile_guid)
    if profile is None:
        print(json.dumps({"error": f"Profile {profile_guid[:20]}... not found"}, ensure_ascii=False))
        sys.exit(1)

    profile_name = profile.get("name", "(defaults)")
    current_bg = profile.get("backgroundImage", None)
    current_opacity = profile.get("backgroundImageOpacity", None)

    settings = _load_settings()
    settings["terminal"] = {
        "wt_settings_path": wt_path,
        "wt_version": label,
        "profile_guid": profile_guid,
        "profile_name": profile_name,
        "profile_source": source,
        "original_background": current_bg,
        "original_opacity": current_opacity,
        "current_scene": None,
        "current_opacity": current_opacity if current_opacity is not None else 0.3,
    }
    _save_settings(settings)

    print(json.dumps({
        "init": "ok", "wt_path": wt_path, "version": label,
        "profile": profile_name, "source": source,
        "previous_bg": current_bg, "previous_opacity": current_opacity,
    }, ensure_ascii=False))


def cmd_set(scene, transition=True):
    if not _is_bg_enabled("locations"):
        print(json.dumps({"skipped": "background_image locations disabled"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    # Auto-poll to pick up any newly generated images
    _auto_poll()

    bg_config = _load_backgrounds_config()
    entry = bg_config.get("locations", {}).get(scene) or bg_config.get("combat", {}).get(scene)
    if not entry:
        print(json.dumps({
            "scene_set": scene, "needs_background": True,
            "hint": "此地点尚无背景图——DM 应基于 --lookup_location 的感官数据提交生图任务",
        }, ensure_ascii=False))
        return

    bg_file = entry.get("file")
    if not bg_file:
        print(json.dumps({"error": f"Scene '{scene}' has no 'file' defined"}, ensure_ascii=False))
        sys.exit(1)

    bg_path = _resolve_bg_path(bg_file)
    if not os.path.isfile(bg_path):
        print(json.dumps({"error": f"Image not found: {bg_path}"}, ensure_ascii=False))
        sys.exit(1)

    # Use entry's opacity if defined, otherwise inherit current
    opacity = entry.get("opacity", term.get("current_opacity", 0.3))

    _write_background(term, bg_path, opacity, transition=transition)

    term["current_scene"] = scene
    term["current_opacity"] = opacity
    _save_settings(settings)

    print(json.dumps({
        "scene_set": scene, "image": bg_path, "opacity": opacity,
        "mood": entry.get("mood", ""), "transitioned": transition,
    }, ensure_ascii=False))


def cmd_combat(mode="battle", transition=True, monster_key=None):
    if not _is_bg_enabled("combat"):
        print(json.dumps({"skipped": "background_image combat disabled"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    # Auto-poll to pick up any newly generated monster-specific images
    _auto_poll()

    bg_config = _load_backgrounds_config()
    combat_cfg = bg_config.get("combat", {})

    entry = None
    source = "generic"
    if monster_key and monster_key in combat_cfg:
        entry = combat_cfg[monster_key]
        source = "monster_specific"
    else:
        entry = combat_cfg.get(mode, combat_cfg.get("battle"))
        if monster_key:
            source = "fallback_generic"

    if not entry:
        print(json.dumps({"error": f"Combat mode '{mode}' not configured"}, ensure_ascii=False))
        sys.exit(1)

    bg_path = _resolve_bg_path(entry["file"])
    if not os.path.isfile(bg_path):
        print(json.dumps({"error": f"Image not found: {bg_path}"}, ensure_ascii=False))
        sys.exit(1)

    combat_opacity = entry.get("opacity", term.get("current_opacity", 0.40))
    _write_background(term, bg_path, combat_opacity, transition=transition)

    term["current_scene"] = f"combat_{monster_key}" if monster_key else f"combat_{mode}"
    term["current_opacity"] = combat_opacity
    _save_settings(settings)

    result = {
        "combat_mode": mode, "image": bg_path, "opacity": combat_opacity,
        "source": source, "transitioned": transition,
    }
    if monster_key:
        result["monster_key"] = monster_key
        if source == "fallback_generic":
            result["hint"] = (
                f"No custom illustration for '{monster_key}' yet. "
                f"DM can submit: bg.py --submit combat_{monster_key} --prompt \"...\" --style combat --tags \"...\""
            )

    print(json.dumps(result, ensure_ascii=False))


def cmd_mood(name, transition=True):
    """Apply mood or narrative beat — checks both sections transparently."""
    if not _is_bg_enabled("moods"):
        print(json.dumps({"skipped": "background_image moods disabled"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    bg_config = _load_backgrounds_config()
    # Check moods first, then narrative beats
    entry = bg_config.get("moods", {}).get(name) or bg_config.get("narrative", {}).get(name)
    if not entry:
        print(json.dumps({"error": f"Atmosphere '{name}' not found in moods or narrative"}, ensure_ascii=False))
        sys.exit(1)

    opacity = entry.get("opacity")
    if opacity is None:
        print(json.dumps({"error": f"Atmosphere '{name}' has no opacity defined"}, ensure_ascii=False))
        sys.exit(1)

    # Check for image variants — switch image + opacity together
    variants = entry.get("variants")
    if variants:
        chosen = random.choice(variants)
        bg_path = _resolve_bg_path(chosen)
        if os.path.isfile(bg_path):
            _write_background(term, bg_path, opacity, transition=transition)
            term["current_scene"] = f"mood_{name}"
            term["current_opacity"] = opacity
            _save_settings(settings)
            print(json.dumps({
                "mood_applied": name, "image": bg_path, "opacity": opacity,
                "variant": chosen, "transitioned": transition,
            }, ensure_ascii=False))
            return

    # Single file entry (no variants) — switch image directly
    single_file = entry.get("file")
    if single_file:
        bg_path = _resolve_bg_path(single_file)
        if os.path.isfile(bg_path):
            _write_background(term, bg_path, opacity, transition=transition)
            term["current_scene"] = f"mood_{name}"
            term["current_opacity"] = opacity
            _save_settings(settings)
            print(json.dumps({
                "mood_applied": name, "image": bg_path, "opacity": opacity,
                "variant": single_file, "transitioned": transition,
            }, ensure_ascii=False))
            return

    # Fallback: opacity-only adjustment
    _fade_opacity(term, term.get("current_opacity", 0.3), opacity, steps=8, duration=0.30)
    term["current_opacity"] = opacity
    _save_settings(settings)
    print(json.dumps({"mood_applied": name, "opacity": opacity, "transitioned": transition}, ensure_ascii=False))


def cmd_reset():
    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized"}, ensure_ascii=False))
        sys.exit(1)

    wt_path = term["wt_settings_path"]
    wt_data = _load_wt_json(wt_path)
    profile, source = _find_profile(wt_data, term["profile_guid"])
    if profile is None:
        print(json.dumps({"error": "Profile not found"}, ensure_ascii=False))
        sys.exit(1)

    original_bg = term.get("original_background")
    original_opacity = term.get("original_opacity")
    if original_bg:
        profile["backgroundImage"] = original_bg
        if original_opacity is not None:
            profile["backgroundImageOpacity"] = original_opacity
    else:
        profile.pop("backgroundImage", None)
        profile.pop("backgroundImageOpacity", None)
        profile.pop("backgroundImageStretchMode", None)

    _save_wt_json(wt_path, wt_data)
    term["current_scene"] = None
    _save_settings(settings)
    print(json.dumps({"reset": "ok", "restored_original": bool(original_bg)}, ensure_ascii=False))


def cmd_status():
    settings = _load_settings()
    term = settings.get("terminal")

    if not term:
        print(json.dumps({
            "status": "not_initialized",
        }, ensure_ascii=False))
        return

    pending = _load_pending()
    active = [t for t in pending if t.get("status") in ("PENDING", "RUNNING")]

    print(json.dumps({
        "status": "ok",
        "profile": term.get("profile_name", "?"),
        "scene": term.get("current_scene"),
        "opacity": term.get("current_opacity"),
        "pending_tasks": len(active),
        "pending_scenes": [t.get("scene_id") for t in active],
    }, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════
# Commands: generation
# ═══════════════════════════════════════════════════════════════

def cmd_submit(scene_id, prompt, negative=None, size=None, style="scene", tags=None, mood=None):
    if not _is_auto_generate_enabled():
        print(json.dumps({"skipped": "auto_generate disabled"}, ensure_ascii=False))
        return

    gen = get_generator()
    if not gen.is_available():
        print(json.dumps({"error": f"Generator '{gen.name}' not available"}, ensure_ascii=False))
        sys.exit(1)

    world = _get_active_world()

    style_prompt = _get_style_prompt()
    if style_prompt:
        prompt = f"{prompt}, {style_prompt}"

    # Check shared index before calling API
    cached = _find_cached(mood, tags)
    if cached:
        cached_file = cached["file"]
        _ensure_world_backgrounds_config(world)
        if style in ("combat", "boss"):
            _register_combat_entry(world, scene_id, cached_file)
        elif scene_id.startswith("mood_"):
            _register_category(world, scene_id, cached_file, "moods")
        elif scene_id.startswith("narrative_"):
            _register_category(world, scene_id, cached_file, "narrative")
        else:
            _register_scene(world, scene_id, cached_file)
        _write_meta(world, scene_id, cached_file, prompt, tags, mood, style)
        print(json.dumps({
            "submitted": "ok", "generated": scene_id, "world": world,
            "style": style, "status": "CACHED",
            "source": cached.get("pinned_from", "?"), "file": cached_file,
        }, ensure_ascii=False))
        return

    negative = negative or gen.get_default_negative()
    negative = _enrich_negative(negative, scene_id, world)
    size = size or gen.get_default_size()

    if hasattr(gen, 'submit') and hasattr(gen, 'poll'):
        task_id = gen.submit(prompt, negative, size, style)
        pending = _load_pending()
        pending.append({
            "task_id": task_id, "scene_id": scene_id, "world": world,
            "prompt": prompt, "tags": tags or "", "mood": mood or "",
            "style": style, "submitted_at": datetime.now().isoformat(), "status": "PENDING",
        })
        _save_pending(pending)
        print(json.dumps({
            "submitted": "ok", "task_id": task_id, "scene_id": scene_id,
            "world": world, "style": style, "status": "PENDING",
        }, ensure_ascii=False))
    else:
        try:
            tmp_path = gen.generate(prompt, negative, size, style)
        except Exception as e:
            print(json.dumps({"error": f"Generation failed: {e}"}, ensure_ascii=False))
            sys.exit(1)

        filename = f"{scene_id}.png"
        out_path = _install_image(tmp_path, world, scene_id, filename)
        _ensure_world_backgrounds_config(world)
        if style in ("combat", "boss"):
            _register_combat_entry(world, scene_id, filename)
        elif scene_id.startswith("mood_"):
            _register_category(world, scene_id, filename, "moods")
        elif scene_id.startswith("narrative_"):
            _register_category(world, scene_id, filename, "narrative")
        else:
            _register_scene(world, scene_id, filename)
        _write_meta(world, scene_id, filename, prompt, tags, mood, style)
        _index_add(filename, mood, tags, gen.name, world)

        print(json.dumps({
            "submitted": "ok", "generated": scene_id, "path": str(out_path),
            "world": world, "style": style, "status": "DONE",
        }, ensure_ascii=False))


def cmd_poll():
    gen = get_generator()
    if not hasattr(gen, 'poll'):
        print(json.dumps({"poll": "sync_provider", "hint": f"'{gen.name}' generates synchronously — nothing to poll"},
                         ensure_ascii=False))
        return
    if not gen.is_available():
        print(json.dumps({"error": f"Generator '{gen.name}' not available"}, ensure_ascii=False))
        sys.exit(1)

    pending = _load_pending()
    active = [t for t in pending if t.get("status") in ("PENDING", "RUNNING")]
    if not active:
        print(json.dumps({"poll": "nothing_pending"}, ensure_ascii=False))
        return

    results = []
    for task in active:
        task_id = task["task_id"]
        try:
            tmp_path = gen.poll(task_id)
        except Exception as e:
            task["status"] = "FAILED"
            task["error"] = str(e)
            results.append({"task_id": task_id, "status": "FAILED", "error": str(e)})
            continue

        if tmp_path is not None:
            scene_id = task["scene_id"]
            world = task["world"]
            style = task.get("style", "scene")
            filename = f"{scene_id}.png"
            try:
                out_path = _install_image(tmp_path, world, scene_id, filename)
                _ensure_world_backgrounds_config(world)
                if style in ("combat", "boss"):
                    _register_combat_entry(world, scene_id, filename)
                elif scene_id.startswith("mood_"):
                    _register_category(world, scene_id, filename, "moods")
                elif scene_id.startswith("narrative_"):
                    _register_category(world, scene_id, filename, "narrative")
                else:
                    _register_scene(world, scene_id, filename)
                _write_meta(world, scene_id, filename,
                            task.get("prompt", ""), task.get("tags", ""),
                            task.get("mood", ""), style)
                _index_add(filename, task.get("mood", ""), task.get("tags", ""),
                           gen.name, world)
                task["status"] = "DONE"
                task["completed_at"] = datetime.now().isoformat()
                results.append({
                    "task_id": task_id, "scene_id": scene_id, "world": world,
                    "style": style, "status": "DONE", "path": str(out_path),
                    "size_bytes": os.path.getsize(out_path),
                })
            except Exception as e:
                task["status"] = "FAILED"
                task["error"] = f"Install failed: {e}"
                results.append({"task_id": task_id, "status": "FAILED", "error": str(e)})
        else:
            task["status"] = "RUNNING"
            results.append({"task_id": task_id, "status": "RUNNING"})

    _save_pending(pending)
    print(json.dumps({"poll": "ok", "results": results}, ensure_ascii=False))


def cmd_skip(scene_id):
    world = _get_active_world()
    bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
    img_path = None
    prompt = ""

    meta_path = _meta_path(world, scene_id)
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        prompt = meta.get("prompt", "")
        filename = meta.get("file", f"{scene_id}.png")
        img_path = os.path.join(bg_dir, filename)
        os.remove(meta_path)
    else:
        for ext in (".png", ".jpg"):
            candidate = os.path.join(bg_dir, f"{scene_id}{ext}")
            if os.path.exists(candidate):
                img_path = candidate
                break
        pending = _load_pending()
        for t in pending:
            if t.get("scene_id") == scene_id and t.get("prompt"):
                prompt = t.get("prompt", "")
                break

    if img_path and os.path.exists(img_path):
        os.remove(img_path)

    if prompt:
        rejected = _load_rejected(world)
        rejected.setdefault(scene_id, {"rejected_prompts": []})
        rejected[scene_id]["rejected_prompts"].append(prompt)
        rejected[scene_id]["rejected_prompts"] = rejected[scene_id]["rejected_prompts"][-5:]
        _save_rejected(world, rejected)

    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    if os.path.exists(bg_path):
        with open(bg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        removed = False
        for section in ("locations", "combat"):
            if scene_id in cfg.get(section, {}):
                del cfg[section][scene_id]
                removed = True
        if scene_id.startswith("combat_"):
            monster_key = scene_id[len("combat_"):]
            if monster_key in cfg.get("combat", {}):
                del cfg["combat"][monster_key]
                removed = True
        if removed:
            with open(bg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(json.dumps({"skipped": scene_id, "deleted_image": img_path, "prompt_recorded": bool(prompt)}, ensure_ascii=False))


def cmd_pin(scene_id):
    world = _get_active_world()
    meta_path = _meta_path(world, scene_id)
    if not os.path.exists(meta_path):
        print(json.dumps({"error": f"No .meta.json found for '{scene_id}'"}, ensure_ascii=False))
        sys.exit(1)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    filename = meta.get("file", f"{scene_id}.png")
    style = meta.get("style", "scene")
    tags = meta.get("tags", [])
    mood = meta.get("mood", "")

    src_img = os.path.join(ROOT, "rules", world, "backgrounds", filename)
    shared_bg_dir = os.path.join(ROOT, "rules", "_shared", "backgrounds")
    os.makedirs(shared_bg_dir, exist_ok=True)
    dst_img = os.path.join(shared_bg_dir, filename)
    if os.path.exists(src_img):
        shutil.copy2(src_img, dst_img)

    shared_path = os.path.join(ROOT, "rules", "_shared", "backgrounds.json")
    with open(shared_path, "r", encoding="utf-8") as f:
        shared = json.load(f)

    category = "combat" if style in ("combat", "boss") else "locations"
    shared.setdefault(category, {})
    shared[category][scene_id] = {
        "file": filename, "mood": mood or f"AI 生成 — {scene_id}",
        "tags": tags, "pinned_from": world, "pinned_at": datetime.now().isoformat(),
    }
    if category == "combat":
        shared[category][scene_id]["opacity"] = 0.40

    with open(shared_path, "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)

    meta["pinned"] = True
    meta["pinned_at"] = datetime.now().isoformat()
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    _index_add(filename, mood or meta.get("mood", ""),
               tags or ",".join(meta.get("tags", [])),
               meta.get("style", "?"), world)

    print(json.dumps({"pinned": scene_id, "from_world": world, "to_shared": filename, "category": category, "tags": tags}, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════
# Export / Import
# ═══════════════════════════════════════════════════════════════

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_export_entries(tag, mood, world):
    """Collect image entries matching filters. Returns [(file_path, manifest_entry), ...]."""
    shared_bg_dir = os.path.join(ROOT, "rules", "_shared", "backgrounds")
    index_entries = _load_index()

    # Build lookup: filename -> index entry (for tags)
    index_by_file = {}
    for e in index_entries:
        index_by_file[e["file"]] = e

    # Collect from _shared/backgrounds.json
    shared_path = os.path.join(ROOT, "rules", "_shared", "backgrounds.json")
    shared_cfg = {}
    if os.path.exists(shared_path):
        with open(shared_path, "r", encoding="utf-8") as f:
            shared_cfg = json.load(f)

    results = []

    def _match(index_entry, img_file, img_mood, source_world, extra_meta=None):
        if not os.path.exists(img_file):
            return
        if tag:
            entry_tags = index_entry.get("tags", []) if index_entry else []
            if tag not in entry_tags and tag not in [t.lower() for t in entry_tags]:
                return
        if mood and img_mood != mood:
            return
        if world and source_world != world:
            return
        manifest = {
            "file": os.path.basename(img_file),
            "mood": img_mood,
            "tags": index_entry.get("tags", []) if index_entry else [],
            "source_world": source_world,
        }
        if extra_meta:
            manifest.update(extra_meta)
        results.append((img_file, manifest))

    # Shared locations + combat + narrative
    for category in ["locations", "combat", "narrative"]:
        for scene_id, cfg in shared_cfg.get(category, {}).items():
            fname = cfg.get("file", "")
            if not fname:
                continue
            img_path = os.path.join(shared_bg_dir, fname)
            idx = index_by_file.get(fname, {})
            _match(idx, img_path, cfg.get("mood", idx.get("mood", "")),
                   cfg.get("pinned_from", idx.get("pinned_from", "?")),
                   extra_meta={"scene_id": scene_id, "category": category})

    # Shared moods
    for mood_name, mood_cfg in shared_cfg.get("moods", {}).items():
        for variant in mood_cfg.get("variants", []):
            img_path = os.path.join(shared_bg_dir, variant)
            idx = index_by_file.get(variant, {})
            _match(idx, img_path, mood_cfg.get("label", mood_name),
                   idx.get("pinned_from", "?"),
                   extra_meta={"scene_id": variant, "category": "moods", "mood_name": mood_name})

    # World-specific images (check all world dirs)
    rules_dir = os.path.join(ROOT, "rules")
    for w in os.listdir(rules_dir):
        w_path = os.path.join(rules_dir, w)
        w_bg_dir = os.path.join(w_path, "backgrounds")
        if not os.path.isdir(w_bg_dir) or w.startswith("_"):
            continue
        for f in os.listdir(w_bg_dir):
            if not f.endswith((".png", ".jpg")):
                continue
            meta_path = os.path.join(w_bg_dir, f.replace(".png", ".meta.json").replace(".jpg", ".meta.json"))
            extra = {}
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta = json.load(mf)
                extra = {
                    "scene_id": meta.get("scene_id", ""),
                    "category": meta.get("style", "scene"),
                    "prompt": meta.get("prompt", ""),
                    "generated_at": meta.get("generated_at", ""),
                }
            img_path = os.path.join(w_bg_dir, f)
            idx = index_by_file.get(f, {})
            img_mood = extra.get("mood") or idx.get("mood", "")
            _match(idx, img_path, img_mood, w, extra_meta=extra)

    # Deduplicate by file basename
    seen = set()
    unique = []
    for img_path, manifest in results:
        if manifest["file"] not in seen:
            seen.add(manifest["file"])
            unique.append((img_path, manifest))
    return unique


def cmd_export(tag=None, mood=None, world=None, output=None):
    entries = _collect_export_entries(tag, mood, world)
    if not entries:
        print(json.dumps({"error": "No images matched the filters"}, ensure_ascii=False))
        sys.exit(1)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path = output or os.path.join(ROOT, "exports", f"bg_export_{ts}.zip")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    manifest = {
        "exported_at": datetime.now().isoformat(),
        "filter": {"tag": tag, "mood": mood, "world": world},
        "image_count": len(entries),
        "images": [m for _, m in entries],
    }

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for img_path, entry in entries:
            zf.write(img_path, f"images/{entry['file']}")

    total_kb = os.path.getsize(out_path) // 1024
    print(json.dumps({
        "exported": out_path, "image_count": len(entries),
        "size_kb": total_kb,
        "filters": {"tag": tag, "mood": mood, "world": world},
    }, ensure_ascii=False))


def cmd_import(zip_path):
    if not os.path.exists(zip_path):
        print(json.dumps({"error": f"File not found: {zip_path}"}, ensure_ascii=False))
        sys.exit(1)

    shared_bg_dir = os.path.join(ROOT, "rules", "_shared", "backgrounds")
    os.makedirs(shared_bg_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Validate manifest
        if "manifest.json" not in zf.namelist():
            print(json.dumps({"error": "Not a valid bg export: manifest.json missing"}, ensure_ascii=False))
            sys.exit(1)

        manifest = json.loads(zf.read("manifest.json"))
        image_list = manifest.get("images", [])

        added = 0
        skipped = 0
        new_index_entries = []

        for entry in image_list:
            fname = entry["file"]
            zip_img_path = f"images/{fname}"
            if zip_img_path not in zf.namelist():
                skipped += 1
                continue

            dst_path = os.path.join(shared_bg_dir, fname)

            # Extract to temp first for SHA256 comparison
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
            try:
                tmp.write(zf.read(zip_img_path))
                tmp.close()

                # Check if identical file already exists
                if os.path.exists(dst_path):
                    if _sha256(tmp.name) == _sha256(dst_path):
                        skipped += 1
                        os.unlink(tmp.name)
                        continue
                    # Different image, same name — add suffix
                    base, ext = os.path.splitext(fname)
                    fname = f"{base}_imported{ext}"
                    dst_path = os.path.join(shared_bg_dir, fname)

                shutil.move(tmp.name, dst_path)
                added += 1

                # Build index entry
                idx_entry = {
                    "file": fname,
                    "mood": entry.get("mood", ""),
                    "tags": entry.get("tags", []),
                    "provider": "import",
                    "pinned_from": entry.get("source_world", "?"),
                    "pinned_at": datetime.now().isoformat(),
                }
                new_index_entries.append(idx_entry)

            except Exception as e:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
                raise e

    # Merge into index
    if new_index_entries:
        existing = _load_index()
        existing_files = {e["file"] for e in existing}
        for e in new_index_entries:
            if e["file"] not in existing_files:
                existing.append(e)
                existing_files.add(e["file"])
        _save_index(existing)

    print(json.dumps({
        "imported": zip_path,
        "added": added,
        "skipped_duplicates": skipped,
        "total_in_zip": len(image_list),
    }, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Unified background manager for my-rpg")
    # Switching
    parser.add_argument("--init", action="store_true", help="Auto-detect WT config and cache")
    parser.add_argument("--profile", help="WT profile GUID (overrides auto-detection)")
    parser.add_argument("--set", help="Switch background to named scene")
    parser.add_argument("--combat", nargs="?", const="battle", help="Switch to combat bg (skirmish|battle|boss|ambush)")
    parser.add_argument("--monster", help="Monster key for custom combat illustration")
    parser.add_argument("--mood", help="Apply mood or narrative beat atmosphere")
    parser.add_argument("--reset", action="store_true", help="Restore default (remove background)")
    parser.add_argument("--status", action="store_true", help="Show current config + pending tasks")
    # Generation
    parser.add_argument("--submit", type=str, metavar="SCENE_ID", help="Submit async generation task")
    parser.add_argument("--prompt", type=str, help="Chinese prompt for image generation")
    parser.add_argument("--negative", type=str, default=None)
    parser.add_argument("--size", type=str, default=None)
    parser.add_argument("--style", type=str, default="scene", choices=["scene", "combat", "boss"])
    parser.add_argument("--tags", type=str, help="Comma-separated Chinese tags")
    parser.add_argument("--poll", action="store_true", help="Check pending tasks and download completed")
    parser.add_argument("--skip", type=str, metavar="SCENE_ID", help="Delete image + record rejected prompt")
    parser.add_argument("--pin", type=str, metavar="SCENE_ID", help="Copy image to _shared for cross-world reuse")
    parser.add_argument("--export", nargs="?", const="__all__", metavar="OUTPUT", help="Export images to zip (optionally filtered by --filter-tag/--filter-mood/--filter-world)")
    parser.add_argument("--import", dest="import_zip", type=str, metavar="ZIP", help="Import images from a bg export zip")
    # Filters for export
    parser.add_argument("--filter-tag", type=str, help="Only export images with this tag")
    parser.add_argument("--filter-mood", type=str, help="Only export images with this mood")
    parser.add_argument("--filter-world", type=str, help="Only export images from this world")
    # Options
    parser.add_argument("--no-fade", action="store_true", help="Skip fade transition")

    args = parser.parse_args()
    transition = not args.no_fade

    if args.init:
        cmd_init(profile_guid_override=args.profile)
    elif args.submit:
        if not args.prompt:
            print(json.dumps({"error": "--prompt is required with --submit"}, ensure_ascii=False))
            sys.exit(1)
        cmd_submit(args.submit, args.prompt, args.negative, args.size, args.style, args.tags, args.mood)
    elif args.set:
        cmd_set(args.set, transition=transition)
    elif args.combat:
        cmd_combat(args.combat, transition=transition, monster_key=args.monster)
    elif args.mood:
        cmd_mood(args.mood, transition=transition)
    elif args.reset:
        cmd_reset()
    elif args.status:
        cmd_status()
    elif args.poll:
        cmd_poll()
    elif args.skip:
        cmd_skip(args.skip)
    elif args.pin:
        cmd_pin(args.pin)
    elif args.export:
        output = None if args.export == "__all__" else args.export
        cmd_export(tag=args.filter_tag, mood=args.filter_mood, world=args.filter_world, output=output)
    elif args.import_zip:
        cmd_import(args.import_zip)
    else:
        parser.print_help()
