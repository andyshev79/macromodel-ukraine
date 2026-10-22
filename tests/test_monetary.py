from pathlib import Path

from macromodel.blocks.monetary import COEF_ROWS, annual, coef_table, estimate
from macromodel.loaders.nbu_dk import quarterly

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "manual" / "nbu_dk.xlsx"


def test_credit_history():
    a = annual()
    assert round(a.loc["2025", "LOANS"]) == 887008
    assert a.loc["2016":"2025", ["LOANS_G", "REAL", "DEPS_GDP"]].notna().all().all()


def test_rate_rule_and_pass_through():
    e = estimate()
    assert 0.5 < e["RATE"]["coef"]["CPI"] < 1.2
    assert 0.2 < e["LOAN"]["coef"]["RATE_AVG"] < 0.8


def test_coef_table_matches_rows():
    assert [(r["eq"], r["var"]) for r in coef_table()] == COEF_ROWS


def test_loader_drops_incomplete_quarter():
    if RAW.exists():  # the raw file is not committed
        assert quarterly(RAW).index[-1].endswith(("Q1", "Q2", "Q3", "Q4"))
