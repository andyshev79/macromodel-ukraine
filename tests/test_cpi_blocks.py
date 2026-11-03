import json
import os
import re
import subprocess
import sys
from pathlib import Path

from macromodel.blocks import cpi_blocks as B

ROOT = Path(__file__).resolve().parents[1]


def test_block_weights():
    w = B.estimate()["W"]["coef"]
    # weights of the NBU blocks are positive and add up to about one
    assert all(w[k] > 0 for k in B.BLOCKS)
    assert 0.9 < sum(w[k] for k in B.BLOCKS) < 1.1
    assert w["CORE"] > w["RAW"] > w["FUEL"]


def test_block_equations():
    e = B.estimate()
    assert 0.1 < e["CORE"]["coef"]["FX"] < 0.4 and e["CORE"]["coef"]["WAGE"] > 0
    assert 0 < e["CORE"]["coef"]["CORE_L1"] < 1 and 0 < e["ADM"]["coef"]["ADM_L1"] < 1
    assert e["FUEL"]["coef"]["FX"] > 0.5 and e["FUEL"]["coef"]["BRENT"] > 0.2
    assert e["RAW"]["coef"]["FUEL_L1"] > 0  # diesel for farmers and transport


def test_cpi_blocks_payload():
    res = subprocess.run([sys.executable, str(ROOT / "sheet" / "cpi_blocks_payload.py")], capture_output=True, text=True,
                         check=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
    out = json.loads(res.stdout)
    n = len(B.coef_rows())
    assert f"COEFS!A{B.COEF_FIRST}:L{B.COEF_FIRST + n - 1}" in out
    b3 = next(v for k, v in out.items() if k.startswith("B3_PRICES!A37"))
    assert b3[15][0] == "CPI_Q" and "B3_PRICES!$D$52:$O$52" in out["ANCHORS!BB10"][0][0]
    # ru_RU locale: decimal commas inside formulas
    assert not any(re.search(r"\d\.\d", c) for r in b3 for c in r if isinstance(c, str) and c.startswith("="))


def test_annual_cpi_comes_from_the_quarters_only():
    """2026-11-03, Andrey: the old annual CPI equation stood next to the quarters and showed other numbers; it is gone.
    Row 19 is December y/y, row 20 the average of the quarters, and the blocks take the rate effect straight from B7."""
    import json, os, subprocess, sys
    env = {**os.environ, "PYTHONPATH": "."}
    run = lambda p: json.loads(subprocess.run([sys.executable, p], capture_output=True, text=True, env=env, check=True).stdout)
    b3 = run("sheet/b3_payload.py")
    top = b3["B3_PRICES!A1:H35"]
    assert top[18][:2] == ["CPI_DEC", "ИПЦ, декабрь к декабрю"] and top[18][4] == "=ANCHORS!BC10"
    assert top[19][0] == "CPI_YOY" and top[19][4] == "=AVERAGE(ANCHORS!AZ10:BC10)"
    assert not any("CPI_M" == r[0] for r in top if r) and "ANCHORS!BC10" not in b3
    blocks = run("sheet/cpi_blocks_payload.py")["B3_PRICES!A37:P75"][14]
    assert blocks[0] == "CPI_B" and blocks[6].endswith("+B7_MONETARY!$E$42") and not any("$34" in str(c) for c in blocks)
