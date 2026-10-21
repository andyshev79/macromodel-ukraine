from macromodel.blocks.labour import COEF_ROWS, annual, coef_table, okun


def test_unemployment_filled_after_survey_stopped():
    a = annual()
    assert a.loc["2016":"2025", "U"].notna().all()


def test_okun_slope_negative():
    r = okun()
    assert -0.6 < r["coef"]["GDP"] < -0.2 and r["r2"] > 0.8


def test_coef_table_matches_rows():
    assert [(r["eq"], r["var"]) for r in coef_table()] == COEF_ROWS
