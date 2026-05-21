#!/usr/bin/env python3
"""
Background image generator via Bailian wanx-v1.

Usage:
  python tools/bg_generator.py --submit <scene_id> --prompt "..." [--style scene|combat|boss] [--tags "..."] [--mood "..."]  Submit async task
  python tools/bg_generator.py --poll                               Check pending tasks, download completed
  python tools/bg_generator.py --generate <scene_id> --prompt "..." [--style ...]  Submit + block until done
  python tools/bg_generator.py --status                             Show pending tasks
  python tools/bg_generator.py --clean                              Remove failed tasks
  python tools/bg_generator.py --skip <scene_id>                    Delete image + record prompt for regeneration avoidance
  python tools/bg_generator.py --pin <scene_id>                     Copy image + metadata to _shared for cross-world reuse
  python tools/bg_generator.py --rejected [scene_id]                Show rejected prompts (all if scene_id omitted)
"""

import json
import os
import sys
import argparse
import io
import time
import shutil
import urllib.request
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "rules", "settings.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")
PENDING_FILE = os.path.join(ROOT, "rules", "_shared", "_pending_tasks.json")

from image_gen import get_generator


def _is_auto_generate_enabled():
    """Check config.json display.background_image.auto_generate.

    Supports backward-compatible boolean master switch as well.
    """
    if not os.path.exists(CONFIG_FILE):
        return True
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    bg_cfg = cfg.get("display", {}).get("background_image", True)
    if isinstance(bg_cfg, bool):
        return bg_cfg
    if not bg_cfg.get("enabled", True):
        return False
    return bg_cfg.get("auto_generate", True)


def _get_active_world():
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings.get("active_world", "shattered_crown")


def _load_pending():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_pending(tasks):
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def _ensure_world_backgrounds_config(world):
    """Create world backgrounds.json if it doesn't exist."""
    path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "_comment": f"{world} 专属背景图。引擎会合并 shared + world（world 覆盖同名 key）。",
            "locations": {},
            "combat": {},
            "moods": {}
        }, f, ensure_ascii=False, indent=2)


def _register_scene(world, scene_id, filename):
    """Write scene entry into world's backgrounds.json locations block."""
    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    with open(bg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg.setdefault("locations", {})
    cfg["locations"][scene_id] = {
        "file": filename,
        "mood": f"AI 生成 — {scene_id}"
    }

    with open(bg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _register_combat_entry(world, scene_id, filename):
    """Write combat entry into world's backgrounds.json combat block.

    scene_id follows naming convention: combat_<monster_key>
    The monster key is extracted by stripping the 'combat_' prefix.
    """
    monster_key = scene_id
    if scene_id.startswith("combat_"):
        monster_key = scene_id[len("combat_"):]

    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    with open(bg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg.setdefault("combat", {})
    cfg["combat"][monster_key] = {
        "file": filename,
        "opacity": 0.40,
        "mood": f"AI 生成 — {monster_key}"
    }

    with open(bg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _install_image(temp_path, world, scene_id, filename):
    """Copy a generated image from temp to the world backgrounds directory.

    Returns the final Path.
    """
    bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
    os.makedirs(bg_dir, exist_ok=True)
    dst = os.path.join(bg_dir, filename)
    shutil.copy2(str(temp_path), dst)
    # Clean up temp file
    try:
        os.unlink(str(temp_path))
    except OSError:
        pass
    return dst


# ── metadata / rejected / pin helpers ──────────────────────────

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
    """Write .meta.json alongside the generated image."""
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
    path = _meta_path(world, scene_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _enrich_negative(negative, scene_id, world):
    """Append hints from previously rejected prompts to steer away from them."""
    rejected = _load_rejected(world)
    entry = rejected.get(scene_id)
    if not entry or not entry.get("rejected_prompts"):
        return negative
    last_prompt = entry["rejected_prompts"][-1]
    hint = f", 不同于: {last_prompt[:80]}"
    return (negative or "") + hint


# ── shared image index (cross-world reuse) ─────────────────────

INDEX_FILE = os.path.join(ROOT, "rules", "_shared", "index.json")
CACHE_TAG_THRESHOLD = 3  # minimum overlapping tags for a cache hit


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
    """Search the shared index for a reusable image.

    mood must match exactly.  Tags are matched by intersection —
    at least CACHE_TAG_THRESHOLD overlapping tags required.

    Returns the best-matching entry (most tag overlap), or None.
    """
    if not mood or not tags:
        return None
    query_tags = set(t.strip() for t in tags.split(",") if t.strip())
    if not query_tags:
        return None

    entries = _load_index()
    best = None
    best_overlap = 0
    for entry in entries:
        if entry.get("mood") != mood:
            continue
        entry_tags = set(entry.get("tags", []))
        overlap = len(query_tags & entry_tags)
        if overlap >= CACHE_TAG_THRESHOLD and overlap > best_overlap:
            best = entry
            best_overlap = overlap
    return best


def _index_add(file, mood, tags, provider, pinned_from):
    """Add an entry to the shared index (idempotent — skips duplicates)."""
    entries = _load_index()
    # Avoid duplicates
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


def cmd_submit(scene_id, prompt, negative=None, size=None, style="scene", tags=None, mood=None):
    if not _is_auto_generate_enabled():
        print(json.dumps({"skipped": "auto_generate disabled in config.json"}, ensure_ascii=False))
        return

    gen = get_generator()
    if not gen.is_available():
        print(json.dumps({"error": f"Image generator '{gen.name}' is not available — check API key or service"},
                         ensure_ascii=False))
        sys.exit(1)

    world = _get_active_world()

    # Check shared index before calling API
    cached = _find_cached(mood, tags)
    if cached:
        cached_file = cached["file"]
        # Register scene pointing to the shared image
        _ensure_world_backgrounds_config(world)
        if style in ("combat", "boss"):
            _register_combat_entry(world, scene_id, cached_file)
        else:
            _register_scene(world, scene_id, cached_file)
        _write_meta(world, scene_id, cached_file, prompt, tags, mood, style)
        print(json.dumps({
            "submitted": "ok",
            "generated": scene_id,
            "world": world,
            "style": style,
            "status": "CACHED",
            "source": cached.get("pinned_from", "?"),
            "file": cached_file,
        }, ensure_ascii=False))
        return

    negative = negative or gen.get_default_negative()
    negative = _enrich_negative(negative, scene_id, world)
    size = size or gen.get_default_size()

    if hasattr(gen, 'submit') and hasattr(gen, 'poll'):
        # Async path: submit to API, store in pending queue
        task_id = gen.submit(prompt, negative, size, style)
        pending = _load_pending()
        pending.append({
            "task_id": task_id,
            "scene_id": scene_id,
            "world": world,
            "prompt": prompt,
            "tags": tags or "",
            "mood": mood or "",
            "style": style,
            "submitted_at": datetime.now().isoformat(),
            "status": "PENDING",
        })
        _save_pending(pending)
        print(json.dumps({
            "submitted": "ok",
            "task_id": task_id,
            "scene_id": scene_id,
            "world": world,
            "style": style,
            "status": "PENDING",
        }, ensure_ascii=False))
    else:
        # Sync path: generate immediately
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
        else:
            _register_scene(world, scene_id, filename)
        _write_meta(world, scene_id, filename, prompt, tags, mood, style)
        _index_add(filename, mood, tags, gen.name, world)

        print(json.dumps({
            "submitted": "ok",
            "generated": scene_id,
            "path": str(out_path),
            "world": world,
            "style": style,
            "status": "DONE",
        }, ensure_ascii=False))


def cmd_poll():
    gen = get_generator()
    if not hasattr(gen, 'submit') and hasattr(gen, 'poll'):
        print(json.dumps({"poll": "sync_provider", "hint": f"'{gen.name}' generates synchronously — nothing to poll"},
                         ensure_ascii=False))
        return

    if not gen.is_available():
        print(json.dumps({"error": f"Image generator '{gen.name}' is not available"}, ensure_ascii=False))
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
            # Task completed — install image
            scene_id = task["scene_id"]
            world = task["world"]
            style = task.get("style", "scene")
            filename = f"{scene_id}.png"

            try:
                out_path = _install_image(tmp_path, world, scene_id, filename)
                size = os.path.getsize(out_path)
                _ensure_world_backgrounds_config(world)
                if style in ("combat", "boss"):
                    _register_combat_entry(world, scene_id, filename)
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
                    "task_id": task_id,
                    "scene_id": scene_id,
                    "world": world,
                    "style": style,
                    "status": "DONE",
                    "path": str(out_path),
                    "size_bytes": size,
                })
            except Exception as e:
                task["status"] = "FAILED"
                task["error"] = f"Install failed: {e}"
                results.append({"task_id": task_id, "status": "FAILED", "error": str(e)})
        else:
            # Still running
            task["status"] = "RUNNING"
            results.append({"task_id": task_id, "status": "RUNNING"})

    _save_pending(pending)
    print(json.dumps({"poll": "ok", "results": results}, ensure_ascii=False))


def cmd_generate(scene_id, prompt, negative=None, size=None, style="scene", tags=None, mood=None):
    """Blocking generation — submit + wait, works for both sync and async providers."""
    if not _is_auto_generate_enabled():
        print(json.dumps({"skipped": "auto_generate disabled in config.json"}, ensure_ascii=False))
        return

    gen = get_generator()
    if not gen.is_available():
        print(json.dumps({"error": f"Image generator '{gen.name}' is not available"},
                         ensure_ascii=False))
        sys.exit(1)

    world = _get_active_world()
    negative = negative or gen.get_default_negative()
    negative = _enrich_negative(negative, scene_id, world)
    size = size or gen.get_default_size()

    print(json.dumps({"generating": scene_id, "style": style, "provider": gen.name}, ensure_ascii=False))
    sys.stdout.flush()

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
    else:
        _register_scene(world, scene_id, filename)
    _write_meta(world, scene_id, filename, prompt, tags, mood, style)
    _index_add(filename, mood, tags, gen.name, world)

    size_bytes = os.path.getsize(out_path)
    print(json.dumps({
        "generated": scene_id,
        "path": str(out_path),
        "style": style,
        "size_bytes": size_bytes,
    }, ensure_ascii=False))


def cmd_status():
    pending = _load_pending()
    active = [t for t in pending if t.get("status") in ("PENDING", "RUNNING")]
    done = [t for t in pending if t.get("status") == "DONE"]
    failed = [t for t in pending if t.get("status") == "FAILED"]

    print(json.dumps({
        "pending": len(active),
        "done": len(done),
        "failed": len(failed),
        "tasks": [{
            "task_id": t["task_id"],
            "scene_id": t.get("scene_id"),
            "status": t.get("status"),
            "submitted_at": t.get("submitted_at", "?"),
        } for t in (active + failed)],
    }, ensure_ascii=False))


def cmd_clean():
    pending = _load_pending()
    kept = [t for t in pending if t.get("status") not in ("FAILED",)]
    removed = len(pending) - len(kept)
    _save_pending(kept)
    print(json.dumps({"clean": "ok", "removed_failed": removed}, ensure_ascii=False))


def cmd_skip(scene_id):
    """Delete a generated image and its meta, record prompt for regeneration avoidance."""
    world = _get_active_world()
    bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
    img_path = None
    prompt = ""

    # Find the image file (try .png first, then check meta for filename)
    meta_path = _meta_path(world, scene_id)
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        prompt = meta.get("prompt", "")
        filename = meta.get("file", f"{scene_id}.png")
        img_path = os.path.join(bg_dir, filename)
        os.remove(meta_path)
    else:
        # Fallback: no meta, try common extensions
        for ext in (".png", ".jpg"):
            candidate = os.path.join(bg_dir, f"{scene_id}{ext}")
            if os.path.exists(candidate):
                img_path = candidate
                break
        # Try to find prompt from pending tasks
        pending = _load_pending()
        for t in pending:
            if t.get("scene_id") == scene_id and t.get("prompt"):
                prompt = t.get("prompt", "")
                break

    if img_path and os.path.exists(img_path):
        os.remove(img_path)

    # Record rejected prompt
    if prompt:
        rejected = _load_rejected(world)
        rejected.setdefault(scene_id, {"rejected_prompts": []})
        rejected[scene_id]["rejected_prompts"].append(prompt)
        # Keep only last 5 rejected prompts
        rejected[scene_id]["rejected_prompts"] = rejected[scene_id]["rejected_prompts"][-5:]
        _save_rejected(world, rejected)

    # Also remove from backgrounds.json registry
    bg_path = os.path.join(ROOT, "rules", world, "backgrounds.json")
    if os.path.exists(bg_path):
        with open(bg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        removed_entry = False
        for section in ("locations", "combat"):
            if scene_id in cfg.get(section, {}):
                del cfg[section][scene_id]
                removed_entry = True
        # For combat entries, scene_id has "combat_" prefix but registry uses monster key
        if scene_id.startswith("combat_"):
            monster_key = scene_id[len("combat_"):]
            if monster_key in cfg.get("combat", {}):
                del cfg["combat"][monster_key]
                removed_entry = True
        if removed_entry:
            with open(bg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "skipped": scene_id,
        "deleted_image": img_path,
        "prompt_recorded": bool(prompt),
    }, ensure_ascii=False))


def cmd_pin(scene_id):
    """Copy image + metadata to _shared, making it available across all worlds."""
    world = _get_active_world()

    # Load the meta file
    meta_path = _meta_path(world, scene_id)
    if not os.path.exists(meta_path):
        print(json.dumps({"error": f"No .meta.json found for '{scene_id}' — has it been generated?"},
                         ensure_ascii=False))
        sys.exit(1)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    filename = meta.get("file", f"{scene_id}.png")
    style = meta.get("style", "scene")
    tags = meta.get("tags", [])
    mood = meta.get("mood", "")

    # Determine category
    category = "combat" if style in ("combat", "boss") else "locations"

    # Copy image to _shared/backgrounds/
    src_img = os.path.join(ROOT, "rules", world, "backgrounds", filename)
    shared_bg_dir = os.path.join(ROOT, "rules", "_shared", "backgrounds")
    os.makedirs(shared_bg_dir, exist_ok=True)
    dst_img = os.path.join(shared_bg_dir, filename)

    if os.path.exists(src_img):
        import shutil
        shutil.copy2(src_img, dst_img)

    # Add entry to _shared/backgrounds.json
    shared_path = os.path.join(ROOT, "rules", "_shared", "backgrounds.json")
    with open(shared_path, "r", encoding="utf-8") as f:
        shared = json.load(f)

    shared.setdefault(category, {})
    shared[category][scene_id] = {
        "file": filename,
        "mood": mood or f"AI 生成 — {scene_id}",
        "tags": tags,
        "pinned_from": world,
        "pinned_at": datetime.now().isoformat(),
    }
    if category == "combat":
        shared[category][scene_id]["opacity"] = 0.40

    with open(shared_path, "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)

    # Mark local meta as pinned
    meta["pinned"] = True
    meta["pinned_at"] = datetime.now().isoformat()
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    _index_add(filename, mood or meta.get("mood", ""),
               tags or ",".join(meta.get("tags", [])),
               meta.get("style", "?"),
               world)

    print(json.dumps({
        "pinned": scene_id,
        "from_world": world,
        "to_shared": filename,
        "category": category,
        "tags": tags,
    }, ensure_ascii=False))


def cmd_rejected(scene_id=None):
    """Show rejected prompts for a scene or all scenes."""
    world = _get_active_world()
    rejected = _load_rejected(world)

    if scene_id:
        entry = rejected.get(scene_id)
        if not entry:
            print(json.dumps({"rejected": scene_id, "prompts": []}, ensure_ascii=False))
        else:
            print(json.dumps({"rejected": scene_id, "prompts": entry.get("rejected_prompts", [])},
                             ensure_ascii=False))
    else:
        print(json.dumps({
            "rejected_scenes": list(rejected.keys()),
            "total": sum(len(v.get("rejected_prompts", [])) for v in rejected.values()),
        }, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Background image generator via Bailian wanx-v1")
    parser.add_argument("--submit", type=str, metavar="SCENE_ID", help="Submit async generation task")
    parser.add_argument("--prompt", type=str, help="Chinese prompt for image generation")
    parser.add_argument("--negative", type=str, default=None, help="Negative prompt (provider default if omitted)")
    parser.add_argument("--size", type=str, default=None, help="Image size (provider default if omitted)")
    parser.add_argument("--style", type=str, default="scene", choices=["scene", "combat", "boss"],
                        help="Style preset: scene (location), combat (enemy), boss (epic boss)")
    parser.add_argument("--tags", type=str, help="Comma-separated Chinese tags (auto-generated by DM from sensory desc)")
    parser.add_argument("--mood", type=str, help="Mood label for the scene (tension/danger/safe/etc.)")
    parser.add_argument("--poll", action="store_true", help="Check pending tasks and download completed")
    parser.add_argument("--generate", type=str, metavar="SCENE_ID", help="Submit + block until done")
    parser.add_argument("--status", action="store_true", help="Show pending task summary")
    parser.add_argument("--clean", action="store_true", help="Remove failed tasks")
    parser.add_argument("--skip", type=str, metavar="SCENE_ID", help="Delete generated image + record prompt for regeneration avoidance")
    parser.add_argument("--pin", type=str, metavar="SCENE_ID", help="Copy image + metadata to _shared for cross-world reuse")
    parser.add_argument("--rejected", type=str, nargs="?", const="__ALL__", metavar="SCENE_ID",
                        help="Show rejected prompts for a scene (or all if omitted)")
    args = parser.parse_args()

    if args.submit:
        if not args.prompt:
            print(json.dumps({"error": "--prompt is required with --submit"}, ensure_ascii=False))
            sys.exit(1)
        cmd_submit(args.submit, args.prompt, args.negative, args.size, args.style, args.tags, args.mood)
    elif args.generate:
        if not args.prompt:
            print(json.dumps({"error": "--prompt is required with --generate"}, ensure_ascii=False))
            sys.exit(1)
        cmd_generate(args.generate, args.prompt, args.negative, args.size, args.style, args.tags, args.mood)
    elif args.poll:
        cmd_poll()
    elif args.status:
        cmd_status()
    elif args.clean:
        cmd_clean()
    elif args.skip:
        cmd_skip(args.skip)
    elif args.pin:
        cmd_pin(args.pin)
    elif args.rejected is not None:
        cmd_rejected(args.rejected if args.rejected != "__ALL__" else None)
    else:
        parser.print_help()
