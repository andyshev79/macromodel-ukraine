"""Monthly CPI by NBU blocks, 6-month nowcast and accuracy log (CPI_M sheet, 2026-11-12)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from macromodel import cpi_monthly as M
from sheet import cpi_m_layout as L

ROOT = Path(__file__).resolve().parents[1]


def _hist():
    return pd.read_csv(M.HIST_CSV, index_col=0, parse_dates=False).pipe(
        lambda d: d.set_index(pd.PeriodIndex(d.index, freq="M")))


def test_block_weights_add_up():
    w = pd.read_csv(ROOT / "data" / "cpi_m" / "weights.csv")
    by_block = w.groupby("block")["weight"].sum()
    assert 0.95 < by_block.sum() < 1.05
    assert (w["weight"] >= 0).all()
    assert by_block["CORE"] > by_block["RAW"] > by_block["FUEL"]


def test_monthly_layout_rows():
    assert L.month_row(L.HIST_FIRST) == L.T_FIRST
    assert L.month_row("2026-10") == 274 and L.month_row("2027-04") == 280


def test_backtest_beats_naive_and_benchmark():
    bt = pd.read_csv(ROOT / "data" / "cpi_m" / "backtest.csv")
    bt = bt[~bt["war"]]
    for h in (1, 3, 6):
        s = bt[bt["h"] == h]
        e = lambda c: (s[c] - s["fact"]).abs().mean()
        assert e("NOWCAST") < e("NAIVE") and e("NOWCAST") < e("BENCH"), h


def test_payload_links_b3_to_cpi_m():
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    out = json.loads(subprocess.run([sys.executable, str(ROOT / "sheet" / "cpi_blocks_payload.py")], capture_output=True,
                                    text=True, check=True, cwd=ROOT, env=env).stdout)
    b3 = next(v for k, v in out.items() if k.startswith("B3_PRICES!A29"))
    flat = [c for r in b3 for c in r if isinstance(c, str)]
    assert any("CPI_M!" in c for c in flat)
    assert not any(re.search(r"\d\.\d", c) for c in flat if c.startswith("="))
