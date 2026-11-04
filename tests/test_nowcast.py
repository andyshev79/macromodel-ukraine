"""Nowcast layer: partial-quarter rule, bridges, fade, sheet formulas."""
import json
import os
import subprocess
import sys

import pandas as pd

from macromodel import nowcast as N
from sheet import nowcast_layout as L


def test_partial_quarter_fills_last_month():
    m = pd.Series([1.0, 3.0], index=pd.PeriodIndex(["2026-07", "2026-08"], freq="M"))
    assert N.quarterly(m)["2026Q3"] == (1 + 3 + 3) / 3
    assert N.quarterly(m, 1)["2026Q3"] == 1.0


def test_bridges_sane():
    br = N.bridges()
    assert set(br) == set(L.SECTORS)
    for s in "BCD":   # industry sections map almost 1:1 to their GVA
        assert 0.8 < br[s]["b"] < 1.2 and br[s]["r2"] > 0.7
    assert all(N.RHO_CLIP[0] <= r["rho"] <= N.RHO_CLIP[1] for r in br.values())


def test_backtest_beats_naive():
    bt = N.backtest()
    assert (bt["m3"] < bt["naive"]).all()
    assert (bt.loc[list("BCDF"), "m3"] <= bt.loc[list("BCDF"), "m1"]).all()


def test_b1_formula_has_nowcast_term():
    out = subprocess.run([sys.executable, "sheet/b1_payload.py"], capture_output=True, text=True, check=True,
                         env={**os.environ, "PYTHONPATH": "."})
    rows = json.loads(out.stdout)["B1_REAL!A32:BK47"]
    gva_b = next(r for r in rows if r and r[0] == "GVA_B")
    assert gva_b[7 + 46].endswith(f"+NOWCAST!J{L.AF_ROW['B']})/100)")   # 2026Q3 = column BB in B1, J in NOWCAST
    gva_j = next(r for r in rows if r and r[0] == "GVA_J")
    assert "NOWCAST" not in gva_j[7 + 46]
