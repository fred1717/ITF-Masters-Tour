#!/usr/bin/env python3
"""Export all generated tables (tournaments 1-59) from DB to Excel."""

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from openpyxl import Workbook
from src.modules.db_connection import DatabaseConnection

XLSX_OUT_DIR = Path(ROOT) / "data" / "extracts" / "generated"
XLSX_OUT_DIR.mkdir(parents=True, exist_ok=True)


def _strip_tz(v):
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.replace(tzinfo=None)
    return v


def write_xlsx(out_path, sheet_name, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    if not rows:
        wb.save(out_path)
        return 0
    cols = list(rows[0].keys())
    ws.append(cols)
    for r in rows:
        ws.append([_strip_tz(r.get(c)) for c in cols])
    wb.save(out_path)
    return len(rows)


TABLES = [
    ("Entries", "SELECT * FROM Entries ORDER BY entry_id", "Entries.xlsx"),
    ("DrawPlayers", "SELECT * FROM DrawPlayers ORDER BY draw_id, draw_position", "DrawPlayers.xlsx"),
    ("DrawSeed", "SELECT * FROM DrawSeed WHERE draw_id >= 9 ORDER BY draw_id, seed_number", "DrawSeed.xlsx"),
    ("Matches", "SELECT * FROM Matches ORDER BY match_id", "Matches.xlsx"),
    ("PlayerSuspensions", "SELECT * FROM PlayerSuspensions ORDER BY suspension_id", "PlayerSuspensions.xlsx"),
    ("PointsHistory", "SELECT * FROM PointsHistory ORDER BY id", "PointsHistory.xlsx"),
    ("WeeklyRanking", "SELECT * FROM WeeklyRanking ORDER BY ranking_year, ranking_week, age_category_id, gender_id, rank_position", "WeeklyRanking.xlsx"),
]

db = DatabaseConnection()
db.connect()

print("=== Exporting tables to Excel ===")
for table_name, query, filename in TABLES:
    rows = [dict(r) for r in db.query(query)]
    count = write_xlsx(XLSX_OUT_DIR / filename, table_name, rows)
    print(f"  {filename}: {count} rows")

db.disconnect()
print(f"\nExport complete -> {XLSX_OUT_DIR}")
