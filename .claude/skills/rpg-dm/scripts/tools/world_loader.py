"""world_loader.py — Modular world system for RPG engine.

Path resolution, world switching, and world listing.
All tools import world_file() to locate data files within the active world directory.
"""

import json
import os
import sys
import tempfile

# Find project root by walking up until config.json is found
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = _ROOT_DIR
while _ROOT != os.path.dirname(_ROOT):  # don't walk past filesystem root
    if os.path.isfile(os.path.join(_ROOT, "config.json")):
        break
    _ROOT = os.path.dirname(_ROOT)

ROOT = _ROOT
SETTINGS_FILE = os.path.join(ROOT, "rules", "settings.json")


def atomic_write(path, write_func, suffix=".json", prefix=".tmp_"):
    """Atomically write to path via tempfile + .bak backup.

    write_func(f) receives an open file handle and writes content to it.
    The previous version of the file is preserved as <path>.bak on success.
    """
    dir_name = os.path.dirname(path) or "."
    os.makedirs(dir_name, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            write_func(f)
        if os.path.exists(path):
            bak_path = path + ".bak"
            if os.path.exists(bak_path):
                os.remove(bak_path)
            os.rename(path, bak_path)
        os.rename(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _load_settings():
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_active_world():
    return _load_settings()["active_world"]


def world_file(filename):
    """Resolve a file path within the active world directory.

    Usage:
        from world_loader import world_file
        with open(world_file("bestiary.json"), "r") as f:
            bestiary = json.load(f)
    """
    settings = _load_settings()
    active = settings["active_world"]
    world_dir = os.path.join(ROOT, settings["worlds"][active]["path"])
    return os.path.join(world_dir, filename)


def list_worlds():
    settings = _load_settings()
    result = []
    for key, info in settings["worlds"].items():
        result.append({
            "key": key,
            "name_cn": info.get("name_cn", key),
            "active": key == settings["active_world"],
        })
    return result


def switch_world(world_name):
    settings = _load_settings()
    if world_name not in settings["worlds"]:
        return {"error": f"世界观 '{world_name}' 不存在，可用: {list(settings['worlds'].keys())}"}
    settings["active_world"] = world_name
    _save_settings(settings)
    return {"switched": world_name, "name_cn": settings["worlds"][world_name].get("name_cn", world_name)}


def register_world(key, name_cn, path):
    """Register a new world in settings.json."""
    settings = _load_settings()
    settings["worlds"][key] = {"name_cn": name_cn, "path": path}
    _save_settings(settings)
    return {"registered": key, "name_cn": name_cn}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("用法: python tools/world_loader.py [list|switch <world>|register <key> <name_cn> <path>]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        for w in list_worlds():
            marker = " *" if w["active"] else ""
            print(f"  {w['key']} ({w['name_cn']}){marker}")

    elif cmd == "switch":
        if len(sys.argv) < 3:
            print("错误: switch 需要世界观名称")
            sys.exit(1)
        result = switch_world(sys.argv[2])
        if "error" in result:
            print(f"错误: {result['error']}")
            sys.exit(1)
        print(f"已切换到世界观: {result['name_cn']}")

    elif cmd == "register":
        if len(sys.argv) < 5:
            print("错误: register 需要 <key> <name_cn> <path>")
            sys.exit(1)
        result = register_world(sys.argv[2], sys.argv[3], sys.argv[4])
        print(f"已注册世界观: {result['registered']} ({result['name_cn']})")

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
