"""Download the history of all anchors and supporting series, quarterly from 2015.

Writes data/history/anchors_q.csv, series_q.csv, catalog.csv and history.xlsx (the
same three tables as sheets, for import into the Google workbook).

Usage: python scripts/fetch_history.py [--start 2015] [--refresh-from 2025] [--offline]
  --refresh-from  re-download cached years from this one on (default: last year)
  --offline       use cached files only
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from macromodel import history

p = argparse.ArgumentParser()
p.add_argument("--start", type=int, default=2015)
p.add_argument("--refresh-from", type=int, default=date.today().year - 1)
p.add_argument("--offline", action="store_true")
args = p.parse_args()

anchors, series, catalog, errors = history.build(
    ROOT / "data" / "raw", args.start, None if args.offline else args.refresh_from)

out = ROOT / "data" / "history"
out.mkdir(parents=True, exist_ok=True)
anchors.to_csv(out / "anchors_q.csv")
series.to_csv(out / "series_q.csv")
catalog.to_csv(out / "catalog.csv", index=False)
try:
    schedule = history.debt_schedule(ROOT / "data" / "raw")
    schedule.to_csv(out / "debt_schedule_y.csv")
except FileNotFoundError as e:
    schedule = None
    errors.append(f"debt_schedule: {e}")
with pd.ExcelWriter(out / "history.xlsx") as xw:
    anchors.to_excel(xw, sheet_name="ANCHORS_FACT")
    series.to_excel(xw, sheet_name="SERIES_Q")
    catalog.to_excel(xw, sheet_name="CATALOG", index=False)
    if schedule is not None:
        schedule.to_excel(xw, sheet_name="DEBT_SCHEDULE_Y")

print(catalog[["table", "code", "first", "last", "n"]].to_string(index=False))
for e in errors:
    print("ERROR", e)
print(f"saved to {out}")
