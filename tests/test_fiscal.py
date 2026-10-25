from macromodel.blocks.fiscal import annual, calibration, coef_table


def test_budget_history():
    a = annual()
    assert a.loc["2022":"2025", "BUDGET_REV"].notna().all()
    assert a.loc["2025", ["BUDGET_EXP", "BUDGET_DEFENCE", "DEBT_PAY_EXT"]].notna().all()
    assert (a.loc["2022":"2025", "REV_OWN"] > 0).all()


def test_calibration_is_plausible():
    c = calibration()
    assert 25 < c[("REV", "OWN")] < 40
    assert 0 < c[("FIN", "GRANT_SHARE")] < 1
    assert 40 < c[("DEBT", "FX_SCHED")] < 46
    a = annual().loc["2025"]
    assert 0.6 < a["EXT_DEBT_USD"] * a["FX_EOP"] / a["DEBT"] < 0.95  # FX share of debt
    assert a["DEBT_REPAY_EXT"] < a["DEBT_PAY_EXT"]


def test_coef_table_has_notes():
    assert all(r["note"] for r in coef_table())
