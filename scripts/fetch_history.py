"""Download the history of all anchors and supporting series.

Writes two sets:
- data/history/: quarterly from 2015, the span of the ANCHORS sheet: anchors_q.csv,
  series_q.csv, catalog.csv and history.xlsx (the same tables as sheets);
- data/history/long/: the longest history for estimation: quarterly from --long-start
  (2005; most quarterly sources begin in 2007-2013) and annual_y.csv by year, where
  years before the quarterly data come from annual sources (Gosstat GDP, World Bank).

Usage: python scripts/fetch_history.py [--start 2015] [--long-start 2005] [--refresh-from 2025] [--offline]
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
p.add_argument("--long-start", type=int, default=2005)
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

# long history: same recipes, earlier start; the cache is already fresh, so no re-download
long_dir = out / "long"
long_dir.mkdir(exist_ok=True)
d = history.Data(ROOT / "data" / "raw", args.long_start, None)
la, ls, lc, lerr = history.build(ROOT / "data" / "raw", args.long_start, None)
annual, acat, aerr = history.build_annual(d, la, ls, lc, args.long_start)
errors += [e for e in lerr + aerr if e not in errors]
la.to_csv(long_dir / "anchors_q.csv")
ls.to_csv(long_dir / "series_q.csv")
lc.to_csv(long_dir / "catalog_q.csv", index=False)
annual.to_csv(long_dir / "annual_y.csv")
acat.to_csv(long_dir / "catalog_y.csv", index=False)
with pd.ExcelWriter(long_dir / "history_long.xlsx") as xw:
    annual.to_excel(xw, sheet_name="ANNUAL_Y")
    acat.to_excel(xw, sheet_name="CATALOG_Y", index=False)
    la.to_excel(xw, sheet_name="ANCHORS_Q")
    ls.to_excel(xw, sheet_name="SERIES_Q")
    lc.to_excel(xw, sheet_name="CATALOG_Q", index=False)

print(catalog[["table", "code", "first", "last", "n"]].to_string(index=False))
print(acat[["code", "first", "last", "n"]].to_string(index=False))
for e in errors:
    print("ERROR", e)
print(f"saved to {out}")
