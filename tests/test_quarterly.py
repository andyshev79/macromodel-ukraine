import pandas as pd

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


def test_wage_factors():
    from macromodel.blocks import wages
    r = wages.estimate()
    c, t = r["coef"], {k: r["coef"][k] / r["se"][k] for k in r["coef"]}
    assert 0.1 < c["MINW"] < 0.3 and t["MINW"] >= 1.96
    assert 0.2 < c["PUB"] < 1 and t["PUB"] >= 1.96
    assert c["DU"] < 0 and t["DU"] <= -1.96
    assert c["CPI_L"] < 0.5  # weak indexation: no wage-price spiral
    assert wages.min_wage()["2026"] == 8647
    rows = [k for k in wages.ROW]
    assert wages.ROW[rows[-1]] - wages.COEF_FIRST == len(rows) - 1


def test_b4_wage_links():
    import json, os, subprocess, sys
    env = {**os.environ, "PYTHONPATH": "."}
    out = json.loads(subprocess.run([sys.executable, "sheet/b4_payload.py"], capture_output=True, text=True, check=True, env=env).stdout)
    rows = out[next(k for k in out if k.startswith("B4_LABOUR"))]
    code = {r[0]: i + 1 for i, r in enumerate(rows) if r and r[0]}
    assert out["B3_PRICES!E12:H12"][0][0] == f"=B4_LABOUR!E{code['WAGE_ECON']}"
    assert out["B2_DEMAND!E14:H14"][0][0] == f"=B4_LABOUR!E{code['INCOME']}"
    assert out["B8_CAPACITY!E12:G12"][0][0] == f"=B4_LABOUR!E{code['Y_EMPL_G']}"
    # quarter columns D:S = 2025Q1..2028Q4; the forecast wage is the same quarter a year before x (1 + growth)
    assert rows[code["WAGE"] - 1][9] == f"=F{code['WAGE']}*(1+J{code['NW_F']}/100)"
    assert out["ANCHORS!BB20:BK20"][0][0] == f"=B4_LABOUR!J{code['WAGE']}"
    # Q4 also moves by a third of the change in the December premium
    assert rows[code["WAGE"] - 1][10] == (f"=G{code['WAGE']}*(1+K{code['NW_F']}/100)"
                                          f"*(1+K{code['DEC_P']}/300)/(1+G{code['DEC_P']}/300)")
    lean = json.loads(subprocess.run([sys.executable, "sheet/b4_payload.py", "--coefs"], capture_output=True, text=True, check=True, env=env).stdout)
    assert not any(k.startswith("SCENARIOS") for k in lean)


def test_labour_quarterly():
    from macromodel.blocks import labour_q as L
    w = L.wage_estimate()
    t = {k: w["coef"][k] / w["se"][k] for k in w["coef"]}
    assert w["n"] >= 45 and all(abs(t[k]) >= 1.96 for k in L.WAGE_REGS)
    assert w["coef"]["DU"] < 0 and 0.1 < w["coef"]["MINW"] < 0.3
    o = L.okun_estimate()
    assert o["coef"]["GDP"] < 0
    s = L.seasonal()
    assert s["WAGE"]["4"] > 1 > s["WAGE"]["1"]  # December bonuses, low Q1
    assert s["LF"]["3"] > s["LF"]["1"] and s["U"]["3"] < 0 < s["U"]["1"]  # farm work in summer
    assert L.min_wage_q()["2024Q2"] == 8000 and L.min_wage_q()["2026Q1"] == 8647
    rows = L.coef_rows()
    assert L.COEF_FIRST + len(rows) - 1 == 150


def test_december_premium():
    from macromodel.blocks import labour_q as L
    w = L.wage_m()
    assert w[pd.Period("2010-01", "M")] < w[pd.Period("2009-12", "M")]  # MacroStat 2010-2013 rows fixed
    p = L.dec_premium()
    assert p.between(8, 25).all() and p[2021] > 20 and 2022 not in p.index
    d = L.dec_drivers()
    assert d["mid"] > d["pre"] > d["war"] and d["fit"]["coef"]["G"] > 0


def test_fuel_shock():
    from macromodel.blocks.shocks import fuel
    f = fuel()
    assert 0.03 < f["coef"] < 0.2 and f["coef"] / f["se"] >= 1.96
    assert f["food"] / f["food_se"] >= 1.96
    assert 5 < f["norm"] < 25 and f["last"] > 20
