from macromodel.blocks.capacity import annual, calibration, coef_table


def test_history():
    a = annual()
    assert round(a.loc["2021", "PROD_G"], 1) == 5.6
    assert a.loc["2015":"2024", "EI"].notna().all()


def test_calibration():
    c = calibration()
    assert c[("CAP", "PROD_MAX")] == 6.0
    assert 1 < c[("CAP", "EI")] < 4
    assert all(r["note"] for r in coef_table())
