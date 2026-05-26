import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from tools.world_loader import world_file


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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_legend(text: str) -> Dict[str, Any]:
    chronicle = load_chronicle()
    parsed = _try_parse_json(text)
    if parsed:
        entry = {
            "content": parsed.get("content", text),
            "spread": parsed.get("spread", "low"),
            "session": _today(),
        }
    else:
        entry = {"content": text, "spread": "low", "session": _today()}
    chronicle.setdefault("legends", []).append(entry)
    save_chronicle(chronicle)
    return {"chronicle": "legend_added", "entry": entry, "total": len(chronicle["legends"])}


def add_relic(text: str) -> Dict[str, Any]:
    chronicle = load_chronicle()
    parsed = _try_parse_json(text)
    if parsed:
        entry = {
            "location": parsed.get("location", ""),
            "description": parsed.get("description", text),
            "permanent": parsed.get("permanent", True),
            "session": _today(),
        }
    else:
        entry = {"location": "", "description": text, "permanent": True, "session": _today()}
    chronicle.setdefault("relics", []).append(entry)
    save_chronicle(chronicle)
    return {"chronicle": "relic_added", "entry": entry, "total": len(chronicle["relics"])}


def add_faction_shift(text: str) -> Dict[str, Any]:
    parsed = _try_parse_json(text)
    if not parsed:
        return {"error": "add_faction_shift requires JSON: {\"faction\":\"...\",\"change\":\"...\",\"reason\":\"...\"}"}
    chronicle = load_chronicle()
    entry = {
        "faction": parsed.get("faction", ""),
        "change": parsed.get("change", ""),
        "reason": parsed.get("reason", "hidden"),
        "session": _today(),
    }
    chronicle.setdefault("faction_shifts", []).append(entry)
    save_chronicle(chronicle)
    return {
        "chronicle": "faction_shift_added",
        "entry": entry,
        "total": len(chronicle["faction_shifts"]),
    }


def add_ending(ending_type: Optional[str], text: str) -> Dict[str, Any]:
    chronicle = load_chronicle()
    entry = {
        "vow": ending_type or "unknown",
        "outcome": ending_type or "unknown",
        "world_change": text,
        "session": _today(),
    }
    chronicle.setdefault("endings", []).append(entry)
    save_chronicle(chronicle)
    return {
        "chronicle": "ending_added",
        "type": ending_type,
        "text": text,
        "total": len(chronicle["endings"]),
    }


def add_broken(text: str) -> Dict[str, Any]:
    parsed = _try_parse_json(text)
    if not parsed:
        return {"error": "add_broken requires JSON: {\"name\":\"...\",\"origin\":\"...\",\"location\":\"...\",\"state\":\"圣徒|群落一员|徘徊者\",\"fragment\":\"...\"}"}
    chronicle = load_chronicle()
    entry = {
        "name": parsed.get("name", ""),
        "origin": parsed.get("origin", ""),
        "location": parsed.get("location", ""),
        "state": parsed.get("state", "徘徊者"),
        "fragment": parsed.get("fragment", ""),
        "session": _today(),
    }
    chronicle.setdefault("broken", []).append(entry)
    save_chronicle(chronicle)
    return {"chronicle": "broken_added", "entry": entry, "total": len(chronicle["broken"])}


def view_chronicle() -> Dict[str, Any]:
    chronicle = load_chronicle()
    result = {"legends": [], "relics": [], "faction_shifts": [], "endings": [], "broken": []}

    for legend in chronicle.get("legends", []):
        if isinstance(legend, dict):
            result["legends"].append({"content": legend.get("content", str(legend)), "spread": legend.get("spread", "low")})

    for relic in chronicle.get("relics", []):
        if isinstance(relic, dict):
            result["relics"].append(
                {
                    "location": relic.get("location", ""),
                    "description": relic.get("description", str(relic)),
                    "permanent": relic.get("permanent", True),
                }
            )

    for shift in chronicle.get("faction_shifts", []):
        if isinstance(shift, dict):
            result["faction_shifts"].append(
                {
                    "faction": shift.get("faction", ""),
                    "change": shift.get("change", ""),
                    "reason": shift.get("reason", "hidden"),
                }
            )

    for ending in chronicle.get("endings", []):
        if isinstance(ending, dict):
            result["endings"].append(
                {
                    "vow": ending.get("vow", "?"),
                    "outcome": ending.get("outcome", "?"),
                    "world_change": ending.get("world_change", ""),
                }
            )

    for broken in chronicle.get("broken", []):
        if isinstance(broken, dict):
            result["broken"].append(
                {
                    "name": broken.get("name", "?"),
                    "origin": broken.get("origin", ""),
                    "location": broken.get("location", ""),
                    "state": broken.get("state", "?"),
                    "fragment": broken.get("fragment", ""),
                }
            )

    result["summary"] = {
        "total_legends": len(chronicle.get("legends", [])),
        "total_relics": len(chronicle.get("relics", [])),
        "total_faction_shifts": len(chronicle.get("faction_shifts", [])),
        "total_endings": len(chronicle.get("endings", [])),
        "total_broken": len(chronicle.get("broken", [])),
    }

    return result


def get_location_hints(location: str) -> List[str]:
    chronicle = load_chronicle()
    hints: List[str] = []

    for relic in chronicle.get("relics", []):
        if isinstance(relic, dict):
            relic_location = relic.get("location", "")
            if relic_location and relic_location != location:
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


def handle_action(action: str, text: Optional[str] = None, ending_type: Optional[str] = None) -> Dict[str, Any]:
    if action == "add_legend":
        return add_legend(text or "")
    if action == "add_relic":
        return add_relic(text or "")
    if action == "add_faction_shift":
        return add_faction_shift(text or "")
    if action == "add_ending":
        return add_ending(ending_type, text or "")
    if action == "add_broken":
        return add_broken(text or "")
    if action == "view":
        return view_chronicle()
    return {"error": f"未知 chronicle 操作: {action}，可用: add_legend, add_relic, add_faction_shift, add_ending, add_broken, view"}
