"""Fetch NBU data and write quarterly FX anchors to data/anchors_nbu.csv.

Usage: python scripts/fetch_nbu.py [--start 2015-01-01]
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from macromodel.aggregate import to_quarter
from macromodel.loaders import nbu

ROOT = Path(__file__).resolve().parents[1]

p = argparse.ArgumentParser()
p.add_argument("--start", default="2015-01-01")
args = p.parse_args()

nbu.download_raw(ROOT / "data" / "raw")
fx = nbu.exchange_rate(date.fromisoformat(args.start), date.today())
anchors = pd.DataFrame({
    "FX_AVG": to_quarter(fx, "AVG"),
    "FX_EOP": to_quarter(fx, "END"),
}).T
anchors.index.name = "code"
out = ROOT / "data" / "anchors_nbu.csv"
anchors.to_csv(out)
print(f"saved {out}")
