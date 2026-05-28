import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from tools.world_loader import atomic_write, world_file


def chronicle_path() -> str:
    return world_file("sessions/chronicle.json")


def _default_chronicle() -> Dict[str, Any]:
    return {"legends": [], "relics": [], "faction_shifts": [], "endings": [], "broken": []}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _try_parse_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def load_chronicle() -> Dict[str, Any]:
    path = chronicle_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _default_chronicle()


def save_chronicle(data: Dict[str, Any]) -> None:
    path = chronicle_path()
    atomic_write(path, lambda f: json.dump(data, f, ensure_ascii=False, indent=2), prefix=".chronicle_tmp_")


# ── Generic entry builder ─────────────────────────────────────

def _add_entry(
    category: str,
    text: str,
    build: Callable[[Dict[str, Any], str], Dict[str, Any]],
) -> Dict[str, Any]:
    chronicle = load_chronicle()
    parsed = _try_parse_json(text)
    entry = build(parsed, text) if parsed else build({}, text)
    entry.setdefault("session", _today())
    chronicle.setdefault(category, []).append(entry)
    save_chronicle(chronicle)
    return {"chronicle": f"{category}_added", "entry": entry, "total": len(chronicle[category])}


# ── add_* ── thin wrappers around _add_entry ──────────────────

def add_legend(text: str) -> Dict[str, Any]:
    def build(parsed, raw):
        return {"content": parsed.get("content", raw), "spread": parsed.get("spread", "low")}
    return _add_entry("legends", text, build)


def add_relic(text: str) -> Dict[str, Any]:
    def build(parsed, raw):
        return {
            "location": parsed.get("location", ""),
            "description": parsed.get("description", raw),
            "permanent": parsed.get("permanent", True),
        }
    return _add_entry("relics", text, build)


def add_faction_shift(text: str) -> Dict[str, Any]:
    parsed = _try_parse_json(text)
    if not parsed:
        return {"error": "add_faction_shift requires JSON: {\"faction\":\"...\",\"change\":\"...\",\"reason\":\"...\"}"}
    def build(parsed, raw):
        return {
            "faction": parsed.get("faction", ""),
            "change": parsed.get("change", ""),
            "reason": parsed.get("reason", "hidden"),
        }
    return _add_entry("faction_shifts", text, build)


def add_ending(ending_type: Optional[str], text: str) -> Dict[str, Any]:
    def build(parsed, raw):
        return {
            "vow": ending_type or "unknown",
            "outcome": ending_type or "unknown",
            "world_change": raw,
        }
    return _add_entry("endings", text, build)


def add_broken(text: str) -> Dict[str, Any]:
    parsed = _try_parse_json(text)
    if not parsed:
        return {"error": "add_broken requires JSON: {\"name\":\"...\",\"origin\":\"...\",\"location\":\"...\",\"state\":\"圣徒|群落一员|徘徊者\",\"fragment\":\"...\"}"}
    def build(parsed, raw):
        return {
            "name": parsed.get("name", ""),
            "origin": parsed.get("origin", ""),
            "location": parsed.get("location", ""),
            "state": parsed.get("state", "徘徊者"),
            "fragment": parsed.get("fragment", ""),
        }
    return _add_entry("broken", text, build)


# ── view ──────────────────────────────────────────────────────

_VIEW_FIELDS: Dict[str, List[tuple]] = {
    "legends":         [("content", "content"), ("spread", "spread")],
    "relics":          [("location", "location"), ("description", "description"), ("permanent", "permanent")],
    "faction_shifts":  [("faction", "faction"), ("change", "change"), ("reason", "reason")],
    "endings":         [("vow", "vow"), ("outcome", "outcome"), ("world_change", "world_change")],
    "broken":          [("name", "name"), ("origin", "origin"), ("location", "location"), ("state", "state"), ("fragment", "fragment")],
}

_DEFAULT_VALUES: Dict[str, Any] = {
    "content": "?", "spread": "low", "location": "", "description": "?", "permanent": True,
    "faction": "", "change": "", "reason": "hidden",
    "vow": "?", "outcome": "?", "world_change": "",
    "name": "?", "origin": "", "state": "?", "fragment": "",
}


def view_chronicle() -> Dict[str, Any]:
    chronicle = load_chronicle()
    result: Dict[str, Any] = {}
    for category, fields in _VIEW_FIELDS.items():
        items = []
        for entry in chronicle.get(category, []):
            if isinstance(entry, dict):
                items.append({out_key: entry.get(src_key, _DEFAULT_VALUES.get(src_key, "?"))
                              for out_key, src_key in fields})
        result[category] = items
    result["summary"] = {
        f"total_{category}": len(chronicle.get(category, []))
        for category in _VIEW_FIELDS
    }
    return result


# ── location hints ────────────────────────────────────────────

def get_location_hints(location: str) -> List[str]:
    chronicle = load_chronicle()
    hints: List[str] = []

    for relic in chronicle.get("relics", []):
        if isinstance(relic, dict):
            relic_loc = relic.get("location", "")
            if relic_loc and relic_loc != location:
                continue
            desc = relic.get("description", "")
            if desc:
                hints.append(f"遗迹回声: {desc}")

    for legend in chronicle.get("legends", []):
        if isinstance(legend, dict):
            content = legend.get("content", "")
            spread = legend.get("spread", "low")
            if content:
                hints.append(f"传闻({spread}): {content}")

    for shift in chronicle.get("faction_shifts", []):
        if isinstance(shift, dict):
            faction = shift.get("faction", "未知势力")
            change = shift.get("change", "")
            if change:
                hints.append(f"势力偏移[{faction}]: {change}")

    return hints[:4]


# ── dispatch ──────────────────────────────────────────────────

_ACTION_MAP: Dict[str, Callable] = {
    "add_legend":        lambda t, et: add_legend(t or ""),
    "add_relic":         lambda t, et: add_relic(t or ""),
    "add_faction_shift": lambda t, et: add_faction_shift(t or ""),
    "add_ending":        lambda t, et: add_ending(et, t or ""),
    "add_broken":        lambda t, et: add_broken(t or ""),
    "view":              lambda t, et: view_chronicle(),
}


def handle_action(action: str, text: Optional[str] = None, ending_type: Optional[str] = None) -> Dict[str, Any]:
    handler = _ACTION_MAP.get(action)
    if handler:
        return handler(text, ending_type)
    return {"error": f"未知 chronicle 操作: {action}，可用: {', '.join(_ACTION_MAP)}"}
