#!/usr/bin/env python3
"""Import real RK3588 snapshot into the production SQLite database.

Usage (run on server):
    python scripts/import_real_run_snapshot.py \
        --snapshot /tmp/real_run_latest \
        --db /var/lib/vision-demo/data/defects.db \
        --image-root /var/lib/vision-demo/static/defects \
        --prefix imported/phase9_soak
"""

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Import RK3588 snapshot into live DB")
    p.add_argument("--snapshot", required=True, help="Path to snapshot directory")
    p.add_argument("--db", required=True, help="SQLite database path")
    p.add_argument("--image-root", required=True, help="Persistent image storage root")
    p.add_argument("--prefix", default="imported/phase9_soak", help="Image subdirectory prefix")
    return p.parse_args()


def main():
    args = parse_args()
    snap = Path(args.snapshot)
    db_path = Path(args.db)
    img_root = Path(args.image_root)
    prefix = args.prefix

    # Load snapshot
    manifest = json.loads((snap / "manifest.json").read_text())
    defects_data = json.loads((snap / "defects_snapshot.json").read_text())
    items = defects_data.get("items", [])

    print(f"source={manifest.get('source')}, is_mock={manifest.get('is_mock')}, items={len(items)}")
    assert manifest.get("is_mock") is False, "Refusing to import mock data"

    # Connect to DB
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    # Create image dest dir
    img_dest = img_root / prefix
    img_dest.mkdir(parents=True, exist_ok=True)

    imported = 0
    skipped = 0
    for item in items:
        # Dedup: check if edge_ts + category + variant already exists
        edge_ts = item["edge_ts"]
        cur.execute(
            "SELECT id FROM defects WHERE edge_ts=? AND category=? AND variant=?",
            (edge_ts, item["category"], item["variant"]),
        )
        if cur.fetchone():
            skipped += 1
            continue

        # Copy image
        old_url = item.get("image_url", "")
        img_name = Path(old_url).name
        src_img = snap / "images" / img_name
        if src_img.exists():
            shutil.copy2(src_img, img_dest / img_name)
            new_url = f"/static/defects/{prefix}/{img_name}"
        else:
            print(f"  WARN: image not found: {src_img}")
            new_url = old_url

        # Insert record
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """INSERT INTO defects
            (image_url, server_ts, line_id, category, defect_type, severity,
             confidence, anomaly_score, bboxes, description, variant, edge_ts,
             pipeline_ms, vlm_metrics, trace_events, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_url,
                now,
                item.get("line_id", ""),
                item["category"],
                item.get("defect_type", ""),
                item.get("severity", "medium"),
                item.get("confidence", 0.0),
                item.get("anomaly_score", 0.0),
                json.dumps(item.get("bboxes", [])),
                item.get("description", ""),
                item.get("variant", "2B_base"),
                edge_ts,
                json.dumps(item.get("pipeline_ms", {})),
                json.dumps(item.get("vlm_metrics")),
                json.dumps(item.get("trace_events")),
                item.get("schema_version", "v1"),
            ),
        )
        imported += 1

    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM defects")
    total = cur.fetchone()[0]
    conn.close()

    print(f"Imported: {imported}, Skipped (dup): {skipped}, Total in DB: {total}")
    print(f"Images copied to: {img_dest}")


if __name__ == "__main__":
    main()
