from macromodel.blocks.prices import COEF_ROWS, annual, coef_table, estimate


def test_annual_history():
    a = annual()
    assert round(a.loc["2025", "CPI"], 1) == 12.2
    assert round(a.loc["2022", "DEFL"], 1) == 35.3


def test_equations_fit():
    est = estimate()
    assert est["CPI"]["r2"] > 0.85 and est["PPI"]["r2"] > 0.85 and est["DEFL"]["r2"] > 0.9
    assert 0 < est["CPI"]["coef"]["WAGE"] < 1
    assert 0 < est["DEFL"]["coef"]["CPI"] + est["DEFL"]["coef"]["PPI"] < 1.2


def test_coef_table_matches_rows():
    assert [(r["eq"], r["var"]) for r in coef_table()] == COEF_ROWS
