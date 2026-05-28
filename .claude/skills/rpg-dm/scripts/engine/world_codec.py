"""World constants JSON ↔ Markdown bidirectional codec.

Inspired by Iron Vault's Markdown-as-database approach.
The .md file is both human-readable documentation and a roundtrippable data store.
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.world_loader import atomic_write, world_file

MD_PATH = world_file("world_constants.md")
JSON_PATH = world_file("world_constants.json")

_FIELD_ORDER = ["name_cn", "role", "age", "location", "background_id", "mood", "white_breath_level"]
_SUBSECTIONS = ["traits", "voice", "quirk", "sensory",
                "cognition", "dynamic_personality", "truth_stance",
                "_origin_tied_to", "_note"]


# ── JSON → Markdown ──────────────────────────────────────────

def json_to_md(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# World Constants")
    lines.append("")
    lines.append("> Auto-generated from `world_constants.json`.")
    lines.append("> Edit with care — use `--sync_world_md` to sync back to JSON.")
    lines.append("")

    for npc_key, npc_data in data.get("npcs", {}).items():
        lines.append("---")
        lines.append("")
        lines.append(f"## NPC: {npc_key}")
        lines.append("")
        _emit_npc(lines, npc_data)

    for loc_key, loc_data in data.get("locations", {}).items():
        lines.append("---")
        lines.append("")
        lines.append(f"## Location: {loc_key}")
        lines.append("")
        _emit_location(lines, loc_data)

    return "\n".join(lines) + "\n"


def _emit_npc(lines: List[str], npc: Dict[str, Any]) -> None:
    _emit_scalars(lines, npc)

    # Meta fields (before any ### subsections so they stay in top-level)
    for key in ("_origin_tied_to", "_note"):
        val = npc.get(key)
        if val:
            lines.append(f"- **{key}**: {val}")
            lines.append("")

    _emit_subsection(lines, "Traits", npc.get("traits", []), 0)
    _emit_subsection(lines, "Voice", npc.get("voice", ""), 0)
    _emit_subsection(lines, "Quirk", npc.get("quirk", ""), 0)

    cognition = npc.get("cognition", {})
    if cognition is not None:
        lines.append("### Cognition")
        lines.append("")
        _emit_dict_of_lists(lines, cognition)

    dp = npc.get("dynamic_personality", {})
    if dp:
        lines.append("### Dynamic Personality")
        lines.append("")
        _emit_any_dict(lines, dp)

    ts = npc.get("truth_stance")
    if ts is not None:
        lines.append("### Truth Stance")
        lines.append("")
        _emit_any_dict(lines, ts)


def _emit_location(lines: List[str], loc: Dict[str, Any]) -> None:
    _emit_scalars(lines, loc)
    _emit_subsection(lines, "Sensory", loc.get("sensory", ""), 0)


def _emit_scalars(lines: List[str], data: Dict[str, Any]) -> None:
    for field in _FIELD_ORDER:
        val = data.get(field)
        if val is not None and val != "":
            lines.append(f"- **{field}**: {val}")
    if lines and lines[-1] != "":
        lines.append("")


def _emit_subsection(lines: List[str], heading: str, content: Any, indent: int) -> None:
    prefix = "    " * indent
    if isinstance(content, list):
        if not content:
            return
        lines.append(f"{prefix}### {heading}")
        lines.append("")
        for item in content:
            lines.append(f"{prefix}- {_escape_item(item)}")
        lines.append("")
    elif isinstance(content, str) and content.strip():
        lines.append(f"{prefix}### {heading}")
        lines.append("")
        lines.append(f"{prefix}{content}")
        lines.append("")
    elif isinstance(content, dict) and content:
        lines.append(f"{prefix}### {heading}")
        lines.append("")
        _emit_any_dict(lines, content, indent)
        lines.append("")


def _emit_dict_of_lists(lines: List[str], d: Dict[str, Any], indent: int = 0) -> None:
    prefix = "    " * indent
    for key, val in d.items():
        if isinstance(val, list):
            lines.append(f"{prefix}- **{key}**:")
            for item in val:
                lines.append(f"{prefix}    - {_escape_item(item)}")
    lines.append("")


def _emit_any_dict(lines: List[str], d: Dict[str, Any], indent: int = 0) -> None:
    prefix = "    " * indent
    for key, val in d.items():
        if isinstance(val, list):
            if not val:
                continue
            lines.append(f"{prefix}- **{key}**:")
            for item in val:
                if isinstance(item, dict):
                    for dk, dv in item.items():
                        lines.append(f"{prefix}    - **{dk}**: {dv}")
                else:
                    lines.append(f"{prefix}    - {_escape_item(item)}")
        elif isinstance(val, dict):
            if not val:
                continue
            lines.append(f"{prefix}- **{key}**:")
            for dk, dv in val.items():
                if isinstance(dv, list):
                    lines.append(f"{prefix}    - **{dk}**:")
                    for item in dv:
                        lines.append(f"{prefix}        - {_escape_item(item)}")
                else:
                    lines.append(f"{prefix}    - **{dk}**: {dv}")
        elif isinstance(val, str) and val:
            lines.append(f"{prefix}- **{key}**: {val}")
    lines.append("")


def _escape_item(item: Any) -> str:
    s = str(item)
    if "\n" in s:
        return s.replace("\n", " ")
    return s


# ── Markdown → JSON ──────────────────────────────────────────

def md_to_json(md_text: str) -> Dict[str, Any]:
    """Parse world_constants.md back into a dict.

    Uses a block-based approach: split by ## headers, then parse each block's
    key-value lines and list/dict structures by tracking indentation context.
    """
    result: Dict[str, Any] = {"npcs": {}, "locations": {}}

    # Split into blocks by ## headers
    blocks = _split_blocks(md_text)
    for block_type, block_key, body in blocks:
        if block_type == "npc":
            result["npcs"][block_key] = _parse_npc_block(body)
        elif block_type == "location":
            result["locations"][block_key] = _parse_location_block(body)

    return result


def _split_blocks(md_text: str) -> List[tuple]:
    """Split markdown into (type, key, body_lines) tuples."""
    blocks: List[tuple] = []
    lines = md_text.split("\n")
    current_type = None
    current_key = None
    current_body: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## NPC: "):
            if current_type and current_key:
                blocks.append((current_type, current_key, current_body))
            current_type = "npc"
            current_key = stripped[len("## NPC: "):].strip()
            current_body = []
        elif stripped.startswith("## Location: "):
            if current_type and current_key:
                blocks.append((current_type, current_key, current_body))
            current_type = "location"
            current_key = stripped[len("## Location: "):].strip()
            current_body = []
        elif current_type:
            current_body.append(line)

    if current_type and current_key:
        blocks.append((current_type, current_key, current_body))

    return blocks


def _parse_npc_block(body: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    subsections = _split_subsections(body)

    # Top-level fields (before any ###)
    top_lines = subsections.pop("", [])
    _parse_kv_lines(top_lines, result)

    for heading, sub_lines in subsections.items():
        hl = heading.lower()
        if hl == "traits":
            result["traits"] = _parse_list_items(sub_lines)
        elif hl == "voice":
            result["voice"] = _parse_text_block(sub_lines)
        elif hl == "quirk":
            result["quirk"] = _parse_text_block(sub_lines)
        elif hl == "cognition":
            result["cognition"] = _parse_dict_of_lists(sub_lines)
        elif hl == "dynamic personality":
            result["dynamic_personality"] = _parse_generic_dict(sub_lines)
        elif hl == "truth stance":
            result["truth_stance"] = _parse_generic_dict(sub_lines)
        # Unknown headings: treated as scalar or list

    return result


def _parse_location_block(body: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    subsections = _split_subsections(body)

    top_lines = subsections.pop("", [])
    _parse_kv_lines(top_lines, result)

    for heading, sub_lines in subsections.items():
        if heading.lower() == "sensory":
            result["sensory"] = _parse_text_block(sub_lines)

    return result


def _split_subsections(body: List[str]) -> Dict[str, List[str]]:
    """Split body lines into {heading: lines} dict. '' key = top-level lines."""
    sections: Dict[str, List[str]] = {"": []}
    current_heading = ""

    for line in body:
        stripped = line.strip()
        if stripped.startswith("### "):
            current_heading = stripped[4:].strip()
            sections[current_heading] = []
        else:
            sections[current_heading].append(line)

    return sections


def _parse_kv_lines(lines: List[str], target: Dict[str, Any]) -> None:
    """Parse top-level '- **key**: value' lines into target dict."""
    for line in lines:
        stripped = line.strip()
        kv = _parse_kv(stripped)
        if kv:
            key, val = kv
            if val != "":
                target[key] = _coerce_value(val)


def _coerce_value(val: str) -> Any:
    """Try to parse numeric values; return string otherwise."""
    if not val:
        return val
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _parse_list_items(lines: List[str]) -> List[str]:
    """Extract '- item' lines (non-kv) from a block."""
    items: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- **"):
            items.append(stripped[2:].strip())
    return items


def _parse_text_block(lines: List[str]) -> str:
    """Extract text content from a block (first non-empty, non-header line)."""
    parts: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and not stripped.startswith("- **"):
            parts.append(stripped[2:].strip())
        elif not stripped.startswith("-"):
            parts.append(stripped)
    return " ".join(parts)


def _parse_dict_of_lists(lines: List[str]) -> Dict[str, List[str]]:
    """Parse a block of '- **key**:' followed by indented '- item' lines."""
    result: Dict[str, List[str]] = {}
    current_key: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        kv = _parse_kv(stripped)
        if kv:
            key, val = kv
            if val == "":
                current_key = key
                result.setdefault(key, [])
            else:
                result[key] = [val] if val else []
                current_key = None
        elif stripped.startswith("- ") and not stripped.startswith("- **"):
            if current_key:
                result.setdefault(current_key, []).append(stripped[2:].strip())

    return result


def _parse_generic_dict(lines: List[str]) -> Dict[str, Any]:
    """Parse a block of '- **key**:' followed by either list items or nested kv pairs.

    Uses indentation to track nesting. Each 4-space indent = one level deeper.
    """
    result: Dict[str, Any] = {}
    current_list_key: Optional[str] = None
    parents: List[Dict[str, Any]] = []  # stack of parent dicts by level

    # Find base indent from first non-empty line
    base_indent = None
    for line in lines:
        if line.strip():
            base_indent = len(line) - len(line.lstrip())
            break
    if base_indent is None:
        base_indent = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        rel_indent = (len(line) - len(line.lstrip())) - base_indent
        level = max(0, rel_indent // 4)

        # Pop parents when level decreases
        while len(parents) > level:
            parents.pop()

        # Target is innermost parent dict, or result itself
        target = parents[-1] if parents else result

        kv = _parse_kv(stripped)
        if kv:
            key, val = kv
            if val == "":
                current_list_key = key
                if _peek_is_dict(lines, i):
                    new_dict: Dict[str, Any] = {}
                    target[key] = new_dict
                    parents.append(new_dict)
                else:
                    target.setdefault(key, [])
            else:
                target[key] = _coerce_value(val)
                current_list_key = None
        elif stripped.startswith("- ") and not stripped.startswith("- **"):
            item_val = stripped[2:].strip()
            if current_list_key:
                target.setdefault(current_list_key, []).append(item_val)

    return result


def _peek_is_dict(lines: List[str], start: int) -> bool:
    """Peek ahead to determine if a key-with-colon is a dict (indented kv pairs) or list (indented plain items).

    Also checks indentation: the child must be more indented than the parent to count.
    If the next line is another key at the same level, it's an empty list.
    """
    if start >= len(lines):
        return False
    parent_indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, min(start + 5, len(lines))):
        stripped = lines[j].strip()
        if not stripped:
            continue
        child_indent = len(lines[j]) - len(lines[j].lstrip())
        if child_indent <= parent_indent:
            # Same level or less — empty list
            return False
        if stripped.startswith("- **"):
            return True
        if stripped.startswith("- "):
            return False
    return False


def _parse_kv(line: str) -> Optional[tuple]:
    """Parse '- **key**: value' or '- **key**:' (empty value)."""
    if not line.startswith("- **"):
        return None
    inner = line[4:]  # strip "- **"
    if "**: " in inner:
        key, val = inner.split("**: ", 1)
        return key.strip(), val.strip()
    if "**:" in inner:
        key = inner.split("**:", 1)[0]
        return key.strip(), ""
    return None


# ── Sync ─────────────────────────────────────────────────────

def sync() -> Dict[str, Any]:
    """Read world_constants.json, write world_constants.md. Returns summary."""
    if not os.path.exists(JSON_PATH):
        return {"error": f"{JSON_PATH} not found"}

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    md_text = json_to_md(data)
    os.makedirs(os.path.dirname(MD_PATH), exist_ok=True)

    atomic_write(MD_PATH, lambda f: f.write(md_text), suffix=".md", prefix=".world_md_tmp_")

    npc_count = len(data.get("npcs", {}))
    loc_count = len(data.get("locations", {}))
    return {"synced": MD_PATH, "npcs": npc_count, "locations": loc_count}


def load_from_md() -> Dict[str, Any]:
    """Read world_constants.md, return parsed dict."""
    if not os.path.exists(MD_PATH):
        return {"error": f"{MD_PATH} not found — run sync first"}
    with open(MD_PATH, "r", encoding="utf-8") as f:
        return md_to_json(f.read())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = sync()
    print(json.dumps(result, ensure_ascii=False))
