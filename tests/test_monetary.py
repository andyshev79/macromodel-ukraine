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


def test_rate_rule_reacts_more_than_one_to_one():
    """Andrey, 30.10: the rate must not stay below inflation; long-run response to end-of-year CPI is 1 + PHI > 1."""
    from macromodel.blocks.monetary import TRANSMISSION
    c = {r["var"]: r["coef"] for r in coef_table() if r["eq"] == "RATE"}
    assert 1 + c["PHI"] > 1 and 0 < c["RHO"] < 1 and c["TARGET"] == 5
    # NBU forecast 29.10.2026: 16.5 end-2026; CPI 7.3 (2027) and 5 (2028) -> rule within 1 p.p. of 14.6 and 11.7
    rule = lambda prev, cpi: c["RHO"] * prev + (1 - c["RHO"]) * (TRANSMISSION["NEUTRAL"][0] + cpi + c["PHI"] * (cpi - c["TARGET"]))
    r27 = rule(16.5, 7.3)
    assert abs(r27 - 14.6) < 1 and abs(rule(r27, 5.0) - 11.7) < 1
    # at 14% inflation the rule gives a rate above inflation (the old OLS rule gave 13.2)
    assert rule(16.5, 14.0) > 14.0
