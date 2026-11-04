import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def payload():
    out = subprocess.run([sys.executable, str(ROOT / "sheet" / "annual_payload.py"), "--coefs"], capture_output=True,
                         text=True, check=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT)})
    return json.loads(out.stdout)


def test_population_is_controlled_territory_and_falls():
    p = pd.read_csv(ROOT / "data" / "external" / "population_controlled.csv").set_index("quarter")["pop_mln"]
    assert p.index[0] == "2015Q1" and p.index[-1] == "2026Q2"
    assert p["2021Q4"] < 42 and p["2025Q4"] < 30          # not the World Bank whole-Ukraine series (39 in 2025)
    assert (p.diff().dropna() <= 0).all()                 # never rises in history


def test_anchor_rules():
    d = payload()
    assert d["ANCHORS!BB17"] == [["=BA17+(B4_LABOUR!J14+B4_LABOUR!J16)/1000+COEFS!$E$257"]]
    assert d["ANCHORS!BB25"] == [["=AX25*B2_DEMAND!BB61/B2_DEMAND!AX61*BB9/AX9"]]
    assert d["ANCHORS!AJ26"] == [["=AJ8*COEFS!$E$258"]] and "ANCHORS!AI26" not in d   # CFC estimate only from 2022
    assert len(d["ANNUAL!S4:S33"]) == 30


def test_history_recipe_uses_the_file():
    a = pd.read_csv(ROOT / "data" / "history" / "anchors_q.csv", index_col=0)
    assert abs(a.loc["POP", "2025Q4"] - 29.19) < 1e-9
