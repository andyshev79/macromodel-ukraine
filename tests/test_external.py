from macromodel.blocks.external import COEF_ROWS, annual, coef_table, estimate


def test_bop_history():
    a = annual()
    assert round(a.loc["2025", "TRADE_BAL"]) == -55760
    assert a.loc["2022":"2025", "OTHER"].notna().all()


def test_export_prices_follow_commodities():
    r = estimate()["EXP_P"]
    assert 0.3 < r["coef"]["PX"] < 1 and r["r2"] > 0.8


def test_coef_table_matches_rows():
    assert [(r["eq"], r["var"]) for r in coef_table()] == COEF_ROWS
