"""Export/import subsystem for bg.py — image zip export + SHA256-deduped import."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime

try:
    from config_loader import ROOT
except ImportError:
    from tools.config_loader import ROOT

INDEX_FILE = os.path.join(ROOT, "rules", "_shared", "index.json")


def _load_index():
    if not os.path.exists(INDEX_FILE):
        return []
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("entries", [])
    if isinstance(data, list):
        return data
    return []


def _save_index(entries):
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


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

    index_by_file = {}
    for e in index_entries:
        index_by_file[e["file"]] = e

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

    for mood_name, mood_cfg in shared_cfg.get("moods", {}).items():
        for variant in mood_cfg.get("variants", []):
            img_path = os.path.join(shared_bg_dir, variant)
            idx = index_by_file.get(variant, {})
            _match(idx, img_path, mood_cfg.get("label", mood_name),
                   idx.get("pinned_from", "?"),
                   extra_meta={"scene_id": variant, "category": "moods", "mood_name": mood_name})

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

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
            try:
                tmp.write(zf.read(zip_img_path))
                tmp.close()

                if os.path.exists(dst_path):
                    if _sha256(tmp.name) == _sha256(dst_path):
                        skipped += 1
                        os.unlink(tmp.name)
                        continue
                    base, ext = os.path.splitext(fname)
                    fname = f"{base}_imported{ext}"
                    dst_path = os.path.join(shared_bg_dir, fname)

                shutil.move(tmp.name, dst_path)
                added += 1

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
