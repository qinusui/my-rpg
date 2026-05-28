import json
import os
import time

from world_loader import ROOT

CONFIG_FILE = os.path.join(ROOT, "config.json")

_CACHE = {
    "data": None,
    "mtime": None,
    "checked_at": 0.0,
}

_CHECK_TTL_SECONDS = 1.0


def _safe_load(path):
    if not os.path.exists(path):
        return {}, None
    try:
        mtime = os.path.getmtime(path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), mtime
    except (OSError, json.JSONDecodeError):
        return {}, None


def load_config(force_reload=False):
    now = time.time()

    if not force_reload and _CACHE["data"] is not None:
        if now - _CACHE["checked_at"] < _CHECK_TTL_SECONDS:
            return _CACHE["data"]
        try:
            current_mtime = os.path.getmtime(CONFIG_FILE)
        except OSError:
            current_mtime = None
        if current_mtime == _CACHE["mtime"]:
            _CACHE["checked_at"] = now
            return _CACHE["data"]

    data, mtime = _safe_load(CONFIG_FILE)
    _CACHE["data"] = data
    _CACHE["mtime"] = mtime
    _CACHE["checked_at"] = now
    return data
