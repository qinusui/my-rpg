"""
Windows Terminal background image switcher for my-rpg.

Usage:
  python tools/bg_switcher.py --init              Auto-detect WT config and cache paths
  python tools/bg_switcher.py --set freeport_city  Switch to scene background
  python tools/bg_switcher.py --combat [default|boss] [--monster <key>]  Switch to combat bg
  python tools/bg_switcher.py --reset              Restore default (no background)
  python tools/bg_switcher.py --opacity 0.35       Change opacity without changing image
  python tools/bg_switcher.py --mood danger        Apply mood preset (opacity shift + optional image switch)
  python tools/bg_switcher.py --narrative discovery  Switch to narrative beat background
  python tools/bg_switcher.py --status             Show current background config
"""

import json
import os
import sys
import time
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "rules", "settings.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")


# ── config.json helpers ─────────────────────────────────────

def _load_config():
    """Read config.json, return {} if missing or malformed."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _is_bg_enabled(category=None):
    """Check if background image is enabled, optionally for a specific category.

    Supports backward-compatible boolean and new nested format:
      false / {"enabled": false}        → all off
      true  / {"enabled": true, ...}    → check category or all on
    """
    bg_cfg = _load_config().get("display", {}).get("background_image", True)
    if isinstance(bg_cfg, bool):
        return bg_cfg
    if not bg_cfg.get("enabled", True):
        return False
    if category:
        return bg_cfg.get(category, True)
    return True


def _is_fg_enabled():
    """Check if foreground color changes are enabled in config.json."""
    return _load_config().get("display", {}).get("foreground_color", True)


def _is_title_enabled():
    """Check if terminal title bar updates are enabled in config.json."""
    return _load_config().get("display", {}).get("title_bar", True)


def _write_foreground(term, color):
    """Write foreground color to WT profile. color=None removes the field (restore default)."""
    wt_path = term["wt_settings_path"]
    profile_guid = term["profile_guid"]
    wt_data = _load_wt_json(wt_path)
    profile, _source = _find_profile(wt_data, profile_guid)
    if profile is None:
        return
    if color is None:
        profile.pop("foreground", None)
    else:
        profile["foreground"] = color
    _save_wt_json(wt_path, wt_data)


# ── WT path detection ──────────────────────────────────────

def _find_wt_settings():
    """Return (path, version_label) or (None, error_message)."""
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
    return None, "WT settings.json not found (checked Store and Preinstalled paths)"


# ── settings cache ─────────────────────────────────────────

def _load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_wt_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_wt_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    # WT detects file change and hot-reloads automatically


# ── profile lookup ─────────────────────────────────────────

def _find_profile(wt_data, profile_guid):
    """Find profile in WT settings by GUID. Falls back to defaults profile."""
    for p in wt_data.get("profiles", {}).get("list", []):
        if p.get("guid", "").lower() == profile_guid.lower():
            return p, "profile"
    # If no exact match, try partial startswith (WT guids sometimes differ in case)
    for p in wt_data.get("profiles", {}).get("list", []):
        g = p.get("guid", "")
        if g and profile_guid.startswith(g[:20]):
            return p, "profile"
    # Last resort: use defaults
    defaults = wt_data.get("profiles", {}).get("defaults")
    if defaults:
        return defaults, "defaults"
    return None, None


# ── init ───────────────────────────────────────────────────

def cmd_init():
    """Auto-detect WT config, verify profile, cache to rules/settings.json."""
    wt_path, label = _find_wt_settings()
    if wt_path is None:
        print(json.dumps({"error": label}, ensure_ascii=False))
        sys.exit(1)

    profile_guid = os.environ.get("WT_PROFILE_ID", "")
    if not profile_guid:
        print(json.dumps({"error": "WT_PROFILE_ID not set — not running in Windows Terminal?"},
                         ensure_ascii=False))
        sys.exit(1)

    wt_data = _load_wt_json(wt_path)
    profile, source = _find_profile(wt_data, profile_guid)
    if profile is None:
        print(json.dumps({"error": f"Profile {profile_guid[:20]}... not found in WT settings"},
                         ensure_ascii=False))
        sys.exit(1)

    profile_name = profile.get("name", "(defaults)")
    current_bg = profile.get("backgroundImage", None)
    current_opacity = profile.get("backgroundImageOpacity", None)
    current_fg = profile.get("foreground", None)

    settings = _load_settings()
    settings["terminal"] = {
        "wt_settings_path": wt_path,
        "wt_version": label,
        "profile_guid": profile_guid,
        "profile_name": profile_name,
        "profile_source": source,
        "original_background": current_bg,
        "original_opacity": current_opacity,
        "original_foreground": current_fg,
        "current_scene": None,
        "current_opacity": current_opacity if current_opacity is not None else 0.3,
    }
    _save_settings(settings)

    print(json.dumps({
        "init": "ok",
        "wt_path": wt_path,
        "version": label,
        "profile": profile_name,
        "source": source,
        "previous_bg": current_bg,
        "previous_opacity": current_opacity,
        "previous_foreground": current_fg,
    }, ensure_ascii=False))


# ── set background ─────────────────────────────────────────

def _load_backgrounds_config():
    """Load merged config: shared base + world overrides (world wins on same key)."""
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
        "combat": {**shared.get("combat", {}), **world_cfg.get("combat", {})},
        "moods": {**shared.get("moods", {}), **world_cfg.get("moods", {})},
    }


def _resolve_bg_path(filename):
    """Resolve a background filename to absolute path. World dir first, then shared."""
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


def cmd_set(scene, transition=True):
    """Switch background to a named scene (location or combat key)."""
    if not _is_bg_enabled("locations"):
        print(json.dumps({"skipped": "background_image locations disabled in config.json"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    bg_config = _load_backgrounds_config()
    # Search locations first, then combat
    entry = bg_config.get("locations", {}).get(scene) or bg_config.get("combat", {}).get(scene)
    if not entry:
        print(json.dumps({"error": f"Scene '{scene}' not found in backgrounds.json"},
                         ensure_ascii=False))
        sys.exit(1)

    bg_file = entry.get("file")
    if not bg_file:
        print(json.dumps({"error": f"Scene '{scene}' has no 'file' defined"},
                         ensure_ascii=False))
        sys.exit(1)

    bg_path = _resolve_bg_path(bg_file)
    if not os.path.isfile(bg_path):
        print(json.dumps({"error": f"Image not found: {bg_path}"}, ensure_ascii=False))
        sys.exit(1)

    # Detect source: world-specific or shared fallback
    world = settings.get("active_world", "shattered_crown")
    world_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    in_world = False
    if os.path.exists(world_path):
        with open(world_path, "r", encoding="utf-8") as f:
            world_cfg = json.load(f)
        in_world = scene in world_cfg.get("locations", {}) or scene in world_cfg.get("combat", {})

    if in_world:
        opacity = term.get("current_opacity", 0.3)
        source = "world"
    else:
        opacity = 0.12  # unfamiliar — shared fallback, fog-like
        source = "shared"

    _write_background(term, bg_path, opacity, transition=transition)

    term["current_scene"] = scene
    term["current_opacity"] = opacity
    _save_settings(settings)

    print(json.dumps({
        "scene_set": scene,
        "image": bg_path,
        "opacity": opacity,
        "source": source,
        "mood": entry.get("mood", ""),
        "transitioned": transition,
    }, ensure_ascii=False))


def cmd_combat(mode="default", transition=True, monster_key=None):
    """Switch to combat background. mode: default | boss.

    When monster_key is provided, tries to find a custom illustration
    in combat config. Falls back to the generic mode (default/boss) if
    no custom image exists for this monster yet.
    """
    if not _is_bg_enabled("combat"):
        print(json.dumps({"skipped": "background_image combat disabled in config.json"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    bg_config = _load_backgrounds_config()
    combat_cfg = bg_config.get("combat", {})

    # Try monster-specific illustration first
    entry = None
    source = "generic"
    if monster_key and monster_key in combat_cfg:
        entry = combat_cfg[monster_key]
        source = "monster_specific"
    else:
        entry = combat_cfg.get(mode, combat_cfg.get("default"))
        if monster_key:
            source = "fallback_generic"

    if not entry:
        print(json.dumps({"error": f"Combat mode '{mode}' not configured"}, ensure_ascii=False))
        sys.exit(1)

    bg_path = _resolve_bg_path(entry["file"])
    if not os.path.isfile(bg_path):
        print(json.dumps({"error": f"Image not found: {bg_path}"}, ensure_ascii=False))
        sys.exit(1)

    combat_opacity = entry.get("opacity", term.get("current_opacity", 0.35))
    _write_background(term, bg_path, combat_opacity, transition=transition)

    term["current_scene"] = f"combat_{monster_key}" if monster_key else f"combat_{mode}"
    term["current_opacity"] = combat_opacity
    _save_settings(settings)

    result = {
        "combat_mode": mode,
        "image": bg_path,
        "opacity": combat_opacity,
        "source": source,
        "transitioned": transition,
    }
    if monster_key:
        result["monster_key"] = monster_key
        if source == "fallback_generic":
            result["hint"] = (
                f"No custom illustration for '{monster_key}' yet — "
                f"DM can submit generation: python tools/bg_generator.py "
                f"--submit combat_{monster_key} --prompt \"...\" --style combat"
            )
    print(json.dumps(result, ensure_ascii=False))


def _write_background(term, image_path, opacity, transition=True):
    """Write backgroundImage + opacity to the WT profile.

    When transition=True, fades out → switches image → fades in for a
    smooth crossfade effect (~1.4s total).  When False, writes instantly
    (used by --no-fade or when speed matters).
    """
    if not transition:
        _write_bg_atomic(term, image_path, opacity)
        return

    current_opacity = term.get("current_opacity", opacity)

    # Fade out to 2% (not 0 — WT ignores opacity=0 and pops the image)
    _fade_opacity(term, current_opacity, 0.02, steps=10, duration=0.55)

    # Switch image while nearly invisible
    _write_bg_atomic(term, image_path, 0.02)

    # Fade in to target
    _fade_opacity(term, 0.02, opacity, steps=12, duration=0.85)


def _write_bg_atomic(term, image_path, opacity):
    """Write image + opacity + stretchMode in a single save (no animation)."""
    wt_path = term["wt_settings_path"]
    profile_guid = term["profile_guid"]
    wt_data = _load_wt_json(wt_path)

    profile, source = _find_profile(wt_data, profile_guid)
    if profile is None:
        print(json.dumps({"error": "Profile not found in WT settings (settings may have changed)"},
                         ensure_ascii=False))
        sys.exit(1)

    profile["backgroundImage"] = image_path.replace("\\", "/")
    profile["backgroundImageOpacity"] = round(float(opacity), 2)
    profile["backgroundImageStretchMode"] = "uniformToFill"

    _save_wt_json(wt_path, wt_data)


def _fade_opacity(term, from_opacity, to_opacity, steps=8, duration=0.4):
    """Gradually change opacity with an ease-in-out curve.

    Writes directly to WT settings.json at each step.  WT hot-reloads
    each write, producing a smooth fade when steps are small enough.
    """
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


def _smoothstep(t):
    """Ken Perlin smoothstep — zero derivative at both endpoints."""
    return t * t * (3 - 2 * t)


def _write_opacity_only(wt_path, profile_guid, opacity):
    """Write only the opacity field — leaves image path and stretch mode untouched."""
    wt_data = _load_wt_json(wt_path)
    profile, source = _find_profile(wt_data, profile_guid)
    if profile is None:
        return
    profile["backgroundImageOpacity"] = opacity
    _save_wt_json(wt_path, wt_data)


def cmd_reset():
    """Remove background image, restore original if any."""
    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    wt_path = term["wt_settings_path"]
    profile_guid = term["profile_guid"]
    wt_data = _load_wt_json(wt_path)
    profile, source = _find_profile(wt_data, profile_guid)
    if profile is None:
        print(json.dumps({"error": "Profile not found"}, ensure_ascii=False))
        sys.exit(1)

    original_bg = term.get("original_background")
    original_opacity = term.get("original_opacity")
    original_fg = term.get("original_foreground")

    # Restore or remove background
    if original_bg:
        profile["backgroundImage"] = original_bg
        if original_opacity is not None:
            profile["backgroundImageOpacity"] = original_opacity
    else:
        profile.pop("backgroundImage", None)
        profile.pop("backgroundImageOpacity", None)
        profile.pop("backgroundImageStretchMode", None)

    # Restore foreground
    if original_fg:
        profile["foreground"] = original_fg
    else:
        profile.pop("foreground", None)

    _save_wt_json(wt_path, wt_data)

    term["current_scene"] = None
    _save_settings(settings)

    print(json.dumps({"reset": "ok", "restored_original": bool(original_bg),
                      "restored_foreground": bool(original_fg)}, ensure_ascii=False))


def cmd_opacity(value, transition=True):
    """Change background opacity without changing the image."""
    if not _is_bg_enabled():
        print(json.dumps({"skipped": "background_image disabled in config.json"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    target = max(0.05, min(1.0, float(value)))
    current = term.get("current_opacity", 0.3)

    if transition and abs(current - target) > 0.01:
        _fade_opacity(term, current, target, steps=8, duration=0.30)
    else:
        wt_path = term["wt_settings_path"]
        _write_opacity_only(wt_path, term["profile_guid"], round(target, 2))

    term["current_opacity"] = target
    _save_settings(settings)

    print(json.dumps({"opacity": target, "transitioned": transition}, ensure_ascii=False))


def cmd_mood(name, transition=True):
    """Apply a mood preset — switches image/opacity/foreground together."""
    if not _is_bg_enabled("moods"):
        print(json.dumps({"skipped": "background_image moods disabled in config.json"}, ensure_ascii=False))
        return

    bg_config = _load_backgrounds_config()
    moods = bg_config.get("moods", {})
    mood = moods.get(name)
    if not mood:
        print(json.dumps({
            "error": f"Mood '{name}' not found in backgrounds.json moods",
        }, ensure_ascii=False))
        sys.exit(1)

    opacity = mood.get("opacity")
    if opacity is None:
        print(json.dumps({"error": f"Mood '{name}' has no opacity defined"},
                         ensure_ascii=False))
        sys.exit(1)

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    # Apply foreground color if enabled and defined
    fg_applied = None
    if "foreground" in mood and _is_fg_enabled():
        fg = mood["foreground"]
        _write_foreground(term, fg)
        fg_applied = fg

    # Check for image variants — switch image + opacity together
    variants = mood.get("variants")
    if variants:
        import random
        chosen = random.choice(variants)
        bg_path = _resolve_bg_path(chosen)
        if os.path.isfile(bg_path):
            _write_background(term, bg_path, opacity, transition=transition)
            term["current_scene"] = f"mood_{name}"
            term["current_opacity"] = opacity
            _save_settings(settings)
            result = {
                "mood_applied": name,
                "image": bg_path,
                "opacity": opacity,
                "variant": chosen,
                "transitioned": transition,
            }
            if fg_applied:
                result["foreground"] = fg_applied
            print(json.dumps(result, ensure_ascii=False))
            return

    # Fallback: opacity-only
    cmd_opacity(opacity, transition=transition)
    result = {"mood_applied": name, "opacity": opacity, "transitioned": transition}
    if fg_applied:
        result["foreground"] = fg_applied
    print(json.dumps(result, ensure_ascii=False))


def cmd_narrative(beat, transition=True):
    """Switch to a narrative beat background (discovery, escape, stealth, etc.)."""
    if not _is_bg_enabled("locations"):
        print(json.dumps({"skipped": "background_image locations disabled in config.json"}, ensure_ascii=False))
        return

    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"error": "Not initialized — run --init first"}, ensure_ascii=False))
        sys.exit(1)

    bg_config = _load_backgrounds_config()
    narrative_cfg = bg_config.get("narrative", {})
    entry = narrative_cfg.get(beat)
    if not entry:
        print(json.dumps({
            "error": f"Narrative beat '{beat}' not found in backgrounds.json narrative",
        }, ensure_ascii=False))
        sys.exit(1)

    bg_file = entry.get("file")
    if not bg_file:
        print(json.dumps({"error": f"Narrative beat '{beat}' has no 'file' defined"},
                         ensure_ascii=False))
        sys.exit(1)

    bg_path = _resolve_bg_path(bg_file)
    if not os.path.isfile(bg_path):
        print(json.dumps({"error": f"Image not found: {bg_path}"}, ensure_ascii=False))
        sys.exit(1)

    opacity = entry.get("opacity", 0.30)
    _write_background(term, bg_path, opacity, transition=transition)

    term["current_scene"] = f"narrative_{beat}"
    term["current_opacity"] = opacity
    _save_settings(settings)

    print(json.dumps({
        "narrative_beat": beat,
        "image": bg_path,
        "opacity": opacity,
        "mood": entry.get("mood", ""),
        "transitioned": transition,
    }, ensure_ascii=False))


def cmd_status():
    """Show current background configuration."""
    settings = _load_settings()
    term = settings.get("terminal")
    if not term:
        print(json.dumps({"status": "not_initialized"}, ensure_ascii=False))
    else:
        print(json.dumps({
            "status": "ok",
            "profile": term.get("profile_name", "?"),
            "scene": term.get("current_scene"),
            "opacity": term.get("current_opacity"),
        }, ensure_ascii=False))


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="WT Background Switcher for my-rpg")
    parser.add_argument("--init", action="store_true", help="Auto-detect WT config and cache")
    parser.add_argument("--set", help="Switch background to named scene")
    parser.add_argument("--combat", nargs="?", const="default", help="Switch to combat bg (default|boss)")
    parser.add_argument("--monster", help="Monster key for custom combat illustration")
    parser.add_argument("--reset", action="store_true", help="Restore default (remove background)")
    parser.add_argument("--opacity", type=float, help="Adjust opacity (0.05-1.0)")
    parser.add_argument("--mood", help="Apply mood preset from backgrounds.json")
    parser.add_argument("--narrative", help="Switch to narrative beat background (discovery/escape/stealth/revelation/aftermath)")
    parser.add_argument("--status", action="store_true", help="Show current config")
    parser.add_argument("--no-fade", action="store_true", help="Skip fade transition (instant switch)")
    args = parser.parse_args()

    transition = not args.no_fade

    if args.init:
        cmd_init()
    elif args.set:
        cmd_set(args.set, transition=transition)
    elif args.combat:
        cmd_combat(args.combat, transition=transition, monster_key=args.monster)
    elif args.reset:
        cmd_reset()
    elif args.opacity is not None:
        cmd_opacity(args.opacity, transition=transition)
    elif args.mood:
        cmd_mood(args.mood, transition=transition)
    elif args.narrative:
        cmd_narrative(args.narrative, transition=transition)
    elif args.status:
        cmd_status()
    else:
        parser.print_help()
