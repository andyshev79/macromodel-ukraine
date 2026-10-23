from macromodel import quarterly


def test_quarterly_sample_and_drivers():
    est = quarterly.estimate()
    assert set(est) == set(quarterly.EQUATIONS)
    for r in est.values():
        assert r["n"] >= 30 and set(r["oos"]) == set(quarterly.TEST_YEARS)
    # equations used in the model have drivers significant at 5%
    assert all(est[eq]["min_t"] >= 1.96 for eq in quarterly.USED)
    assert est["CPI"]["n"] >= 50  # long history from 2011


def test_cpi_speed_between_zero_and_one():
    v, se = quarterly.cpi_speed()
    assert 0 < v < 1 and se > 0


def test_blocks_take_quarterly_rows():
    from macromodel.blocks import demand, monetary, prices, real_sector
    rows = prices.coef_table() + demand.coef_table() + monetary.coef_table() + real_sector.coef_table()
    used = {r["eq"] for r in rows if "квартальные" in r["method"]}
    assert used == quarterly.USED


def test_shock_estimates_in_range():
    from macromodel.blocks.shocks import estimated
    e = estimated()
    assert 0.05 < e["TARIFF_W"][0] < 0.25 and e["TARIFF_W"][0] / e["TARIFF_W"][1] >= 1.96
    assert 0.05 < e["MET_C"][0] < 0.6 and e["MET_C"][0] / e["MET_C"][1] >= 1.96
    assert 0.03 < e["MET_X"][0] < 0.3


def test_manufacturing_quarterly_rows():
    from macromodel.blocks.real_sector import coef_table
    rows = {(r["eq"], r["var"]): r for r in coef_table()}
    hh = rows[("GVA_C", "HH")]
    assert 0 < hh["coef"] < 1 and hh["period"].startswith("2013")
    assert ("GVA_C", "EA_GDP") not in rows
