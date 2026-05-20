#!/usr/bin/env python3
"""
Background image generator via Bailian wanx-v1.

Usage:
  python tools/bg_generator.py --submit <scene_id> --prompt "..." [--style scene|combat|boss]  Submit async task
  python tools/bg_generator.py --poll                               Check pending tasks, download completed
  python tools/bg_generator.py --generate <scene_id> --prompt "..." [--style ...]  Submit + block until done
  python tools/bg_generator.py --status                             Show pending tasks
  python tools/bg_generator.py --clean                              Remove failed tasks
"""

import json
import os
import sys
import argparse
import io
import time
import urllib.request
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "rules", "settings.json")
CONFIG_FILE = os.path.join(ROOT, "config.json")
PENDING_FILE = os.path.join(ROOT, "rules", "_shared", "_pending_tasks.json")

DEFAULT_NEGATIVE = "文字, 水印, UI, HUD, 人物, 角色, 人脸, 明亮鲜艳, 卡通, 动漫"
DEFAULT_SIZE = "1024*1024"

STYLE_PRESETS = {
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


def _get_api_key():
    """Read API key: config.json first, then env var."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        key = cfg.get("services", {}).get("dashscope_api_key", "").strip()
        if key:
            return key
    return os.environ.get("DASHSCOPE_API_KEY", "")


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


def _download_image(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "my-rpg-bg-generator/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


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


def cmd_submit(scene_id, prompt, negative=None, size=None, style="scene"):
    if not _is_auto_generate_enabled():
        print(json.dumps({"skipped": "auto_generate disabled in config.json"}, ensure_ascii=False))
        return

    api_key = _get_api_key()
    if not api_key:
        print(json.dumps({"error": "DASHSCOPE_API_KEY not set — configure in config.json services.dashscope_api_key"},
                         ensure_ascii=False))
        sys.exit(1)

    from dashscope.aigc.image_synthesis import ImageSynthesis

    style_suffix = STYLE_PRESETS.get(style, STYLE_PRESETS["scene"])
    full_prompt = f"{prompt}, {style_suffix}"

    response = ImageSynthesis.call(
        model="wanx-v1",
        prompt=full_prompt,
        negative_prompt=negative or DEFAULT_NEGATIVE,
        n=1,
        size=size or DEFAULT_SIZE,
        api_key=api_key,
    )

    if response.status_code != 200:
        print(json.dumps({
            "error": f"API returned {response.status_code}",
            "message": response.message,
        }, ensure_ascii=False))
        sys.exit(1)

    task_id = response.output.task_id
    world = _get_active_world()

    pending = _load_pending()
    pending.append({
        "task_id": task_id,
        "scene_id": scene_id,
        "world": world,
        "prompt": prompt[:120],
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


def cmd_poll():
    from dashscope.aigc.image_synthesis import ImageSynthesis

    api_key = _get_api_key()
    if not api_key:
        print(json.dumps({"error": "DASHSCOPE_API_KEY not set"}, ensure_ascii=False))
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
            resp = ImageSynthesis.fetch(task_id, api_key=api_key)
        except Exception as e:
            task["status"] = "FAILED"
            task["error"] = str(e)
            results.append({"task_id": task_id, "status": "FAILED", "error": str(e)})
            continue

        if resp.status_code != 200:
            task["status"] = "FAILED"
            task["error"] = resp.message
            results.append({"task_id": task_id, "status": "FAILED", "error": resp.message})
            continue

        output = resp.output
        task_status = output.task_status

        if task_status == "SUCCEEDED":
            scene_id = task["scene_id"]
            world = task["world"]
            style = task.get("style", "scene")
            filename = f"{scene_id}.png"
            bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
            out_path = os.path.join(bg_dir, filename)

            # Download the first result
            image_url = output.results[0].url
            try:
                size = _download_image(image_url, out_path)
                _ensure_world_backgrounds_config(world)
                if style in ("combat", "boss"):
                    _register_combat_entry(world, scene_id, filename)
                else:
                    _register_scene(world, scene_id, filename)
                task["status"] = "DONE"
                task["completed_at"] = datetime.now().isoformat()
                results.append({
                    "task_id": task_id,
                    "scene_id": scene_id,
                    "world": world,
                    "style": style,
                    "status": "DONE",
                    "path": out_path,
                    "size_bytes": size,
                })
            except Exception as e:
                task["status"] = "FAILED"
                task["error"] = f"Download failed: {e}"
                results.append({"task_id": task_id, "status": "FAILED", "error": str(e)})

        elif task_status == "FAILED":
            task["status"] = "FAILED"
            task["error"] = output.message or "Unknown error"
            results.append({"task_id": task_id, "status": "FAILED", "error": task["error"]})

        elif task_status in ("PENDING", "RUNNING"):
            task["status"] = task_status
            results.append({"task_id": task_id, "status": task_status})

    _save_pending(pending)
    print(json.dumps({"poll": "ok", "results": results}, ensure_ascii=False))


def cmd_generate(scene_id, prompt, negative=None, size=None, style="scene"):
    """Submit + blocking wait."""
    cmd_submit(scene_id, prompt, negative, size, style)

    # Read back the task_id we just submitted
    pending = _load_pending()
    try:
        task_id = pending[-1]["task_id"]
    except (IndexError, KeyError):
        print(json.dumps({"error": "Submit succeeded but task_id not found"}, ensure_ascii=False))
        sys.exit(1)

    from dashscope.aigc.image_synthesis import ImageSynthesis
    api_key = _get_api_key()

    print(json.dumps({"generating": scene_id, "task_id": task_id, "style": style}, ensure_ascii=False))
    sys.stdout.flush()

    try:
        result = ImageSynthesis.wait(task_id, api_key=api_key)
    except Exception as e:
        print(json.dumps({"error": f"Wait failed: {e}"}, ensure_ascii=False))
        sys.exit(1)

    if result.status_code != 200 or result.output.task_status != "SUCCEEDED":
        print(json.dumps({"error": "Generation failed", "detail": str(result.output)}, ensure_ascii=False))
        sys.exit(1)

    world = _get_active_world()
    filename = f"{scene_id}.png"
    bg_dir = os.path.join(ROOT, "rules", world, "backgrounds")
    out_path = os.path.join(bg_dir, filename)
    image_url = result.output.results[0].url

    size_bytes = _download_image(image_url, out_path)
    _ensure_world_backgrounds_config(world)
    if style in ("combat", "boss"):
        _register_combat_entry(world, scene_id, filename)
    else:
        _register_scene(world, scene_id, filename)

    # Mark the pending task as done
    for t in pending:
        if t["task_id"] == task_id:
            t["status"] = "DONE"
            t["completed_at"] = datetime.now().isoformat()
    _save_pending(pending)

    print(json.dumps({
        "generated": scene_id,
        "path": out_path,
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Background image generator via Bailian wanx-v1")
    parser.add_argument("--submit", type=str, metavar="SCENE_ID", help="Submit async generation task")
    parser.add_argument("--prompt", type=str, help="Chinese prompt for image generation")
    parser.add_argument("--negative", type=str, default=DEFAULT_NEGATIVE, help="Negative prompt")
    parser.add_argument("--size", type=str, default=DEFAULT_SIZE, help="Image size")
    parser.add_argument("--style", type=str, default="scene", choices=["scene", "combat", "boss"],
                        help="Style preset: scene (location), combat (enemy), boss (epic boss)")
    parser.add_argument("--poll", action="store_true", help="Check pending tasks and download completed")
    parser.add_argument("--generate", type=str, metavar="SCENE_ID", help="Submit + block until done")
    parser.add_argument("--status", action="store_true", help="Show pending task summary")
    parser.add_argument("--clean", action="store_true", help="Remove failed tasks")
    args = parser.parse_args()

    if args.submit:
        if not args.prompt:
            print(json.dumps({"error": "--prompt is required with --submit"}, ensure_ascii=False))
            sys.exit(1)
        cmd_submit(args.submit, args.prompt, args.negative, args.size, args.style)
    elif args.generate:
        if not args.prompt:
            print(json.dumps({"error": "--prompt is required with --generate"}, ensure_ascii=False))
            sys.exit(1)
        cmd_generate(args.generate, args.prompt, args.negative, args.size, args.style)
    elif args.poll:
        cmd_poll()
    elif args.status:
        cmd_status()
    elif args.clean:
        cmd_clean()
    else:
        parser.print_help()
