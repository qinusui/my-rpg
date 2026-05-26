#!/usr/bin/env python3
"""Batch submit image generation tasks for all backgrounds of a world.

Reads the merged backgrounds registry (_shared + world), submits one async
generation task per unique scene, and writes results into the world's registry.

Usage:
  python tools/batch_generate.py cloud_chamber --dry-run
  python tools/batch_generate.py cloud_chamber
  python tools/batch_generate.py cloud_chamber --only moods,narrative
"""

import json
import os
import sys
import argparse
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from bg import _do_submit


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get_style_prompt():
    cfg = load_json(os.path.join(ROOT, "config.json"))
    return cfg.get("image_gen", {}).get("style_prompt", "").strip()


def merge_registries(world):
    """Merge _shared + world backgrounds (world wins)."""
    shared = load_json(os.path.join(ROOT, "rules", "_shared", "backgrounds.json"))
    world_cfg = load_json(os.path.join(ROOT, "rules", world, "backgrounds.json"))

    merged = {
        "locations": {},
        "combat": {},
        "moods": {},
        "narrative": {},
    }

    for section in merged:
        merged[section].update(shared.get(section, {}))
        merged[section].update(world_cfg.get(section, {}))

    return merged


def build_tasks(registry, categories=None):
    """Return list of (scene_id, style, label, mood_desc) tuples."""
    tasks = []
    allowed = set(categories) if categories else {"locations", "combat", "moods", "narrative"}

    if "locations" in allowed:
        for scene_id, entry in registry.get("locations", {}).items():
            label = scene_id.replace("_", " ")
            tasks.append((scene_id, "scene", label, entry.get("mood", "")))

    if "combat" in allowed:
        for scene_id, entry in registry.get("combat", {}).items():
            label = scene_id.replace("_", " ")
            tasks.append((scene_id, "combat", label, entry.get("mood", "")))

    if "moods" in allowed:
        for mood_key, entry in registry.get("moods", {}).items():
            variants = entry.get("variants", [])
            if variants:
                for vf in variants:
                    sid = vf.replace(".jpg", "").replace(".png", "")
                    label = sid.replace("mood_", "").replace("_", " ")
                    tasks.append((sid, "scene", label, entry.get("label", "")))
            else:
                sid = f"mood_{mood_key}"
                tasks.append((sid, "scene", mood_key, entry.get("label", "")))

    if "narrative" in allowed:
        for scene_id, entry in registry.get("narrative", {}).items():
            tasks.append((scene_id, "scene", scene_id, entry.get("mood", "")))

    return tasks


def main():
    parser = argparse.ArgumentParser(description="Batch submit image generation tasks")
    parser.add_argument("world", help="Target world key")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", type=str, help="Comma-separated: locations,combat,moods,narrative")
    parser.add_argument("--delay", type=float, default=0.8)
    args = parser.parse_args()

    categories = [c.strip() for c in args.only.split(",")] if args.only else None

    registry = merge_registries(args.world)
    tasks = build_tasks(registry, categories)

    style_prompt = _get_style_prompt()
    print(f"World: {args.world}")
    print(f"Style: {style_prompt or '(none)'}")
    print(f"Tasks: {len(tasks)}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'SUBMIT'}")
    print("=" * 60)

    submitted = 0
    skipped = 0

    for i, (scene_id, style, label, mood_desc) in enumerate(tasks):
        prompt = f"dark fantasy, {label}"
        print(f"\n[{i+1}/{len(tasks)}] {scene_id}  [{style}]")
        print(f"  prompt: {prompt}")

        if args.dry_run:
            continue

        result = _do_submit(scene_id, prompt, style=style, tags=label)
        status = result.get("status", result.get("error", "?"))
        print(f"  → {status}")
        if status in ("PENDING", "DONE", "CACHED"):
            submitted += 1
        else:
            skipped += 1

        if args.delay > 0 and i < len(tasks) - 1:
            time.sleep(args.delay)

    print(f"\n{'=' * 60}")
    if args.dry_run:
        print(f"Dry run done. Would submit {len(tasks)} tasks.")
    else:
        print(f"Done. {submitted} submitted, {skipped} skipped.")


if __name__ == "__main__":
    main()
