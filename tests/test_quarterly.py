import json
import os
import subprocess
import sys

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
    # 2026Q3 (column J): July-August fact, September from its median change
    assert isinstance(rows[code["WAGE"] - 1][9], float)
    assert rows[code["ADJ"] - 1][9] == f"=J{code['WAGE_G']}-J{code['NW_F']}"
    assert out["ANCHORS!BB20:BK20"][0][0] == f"=B4_LABOUR!J{code['WAGE']}"
    # Q4 also moves by a third of the change in the December premium
    assert rows[code["WAGE"] - 1][10] == (f"=G{code['WAGE']}*(1+(K{code['NW_F']}+K{code['ADJ']})/100)"
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
    assert L.COEF_FIRST + len(rows) - 1 == 167  # MIL_ rows 164-167


def test_wage_nowcast():
    from macromodel.blocks import labour_q as L
    n = L.nowcast()
    assert n["q"] == "2026Q3" and n["fact_months"] == ["2026-07", "2026-08"]
    assert 1 < n["filled"]["2026-09"] < 4  # September usually adds about 2%
    assert 32000 < n["value"] < 32600
    assert 0.3 < L.residual_rho() < 0.8


def payload(name):
    env = {**os.environ, "PYTHONPATH": "."}
    return json.loads(subprocess.run([sys.executable, f"sheet/{name}.py"], capture_output=True, text=True, check=True, env=env).stdout)


def test_wage_logic_check():
    from macromodel.blocks import labour_q as L
    c = L.qq_corridor()
    assert (c["LO"] < c["MED"]).all() and (c["MED"] < c["HI"]).all()
    assert c.loc["1", "HI"] < c.loc["4", "LO"] + 1  # Q1 falls back after the December peak
    out = payload("b4_payload")
    rows = out[next(k for k in out if k.startswith("B4_LABOUR"))]
    code = {r[0]: i + 1 for i, r in enumerate(rows) if r and r[0]}
    assert code["WHY"] > code["QQ_CHK"] > code["INCOME"]  # appended: annual rows keep their numbers
    assert out["CHECKS!A33:Q35"][1][-1] == f'=COUNTIF(B4_LABOUR!P{code["QQ_CHK"]}:S{code["QQ_CHK"]};"ВНИМАНИЕ")'


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


def test_military_block():
    p = payload("b4_payload")
    b4 = next(v for k, v in p.items() if k.startswith("B4_LABOUR!A1:"))
    r = {row[0]: i + 1 for i, row in enumerate(b4) if row and row[0]}
    lf = b4[r["LF_SA"] - 1]
    assert f"*J{r['DEMOB']}" in lf[9]  # demobilised return to the labour force
    assert f"J{r['MIL_N']}/F{r['MIL_N']}" in b4[r["MIL_FUND"] - 1][9]  # fund follows headcount
    assert f"J{r['MIL_G']}" in b4[r["PUB_G"] - 1][9]  # wage equation sees pay rates; the fund goes to income
    assert "MIL_FUND" in str(b4[r["MIL_REAL"] - 1]) or f"{r['MIL_FUND']}" in b4[r["MIL_REAL"] - 1][4]
    sc = next(v for k, v in p.items() if k.startswith("SCENARIOS!A80:"))
    assert sc[-1][0].startswith("Как считается") and sc[-6][0] == "Численность военных — активный"


def test_defence_split():
    from macromodel.blocks.real_sector import defence_share
    assert 0.75 < defence_share() < 0.95  # military pay dominates section O in 2025
    p = payload("b1_payload")
    sec = p["B1_REAL!A59:H69"]
    r = {row[0]: 59 + i for i, row in enumerate(sec) if row and row[0]}
    assert p["B1_REAL!A17:G29"][10][4] == f"=E{r['GVA_O']}"  # row 27 takes section O from the split
    assert "B4_LABOUR!H17:K17" in sec[r["MIL_NY"] - 59][4]  # defence follows military headcount
    assert "OK: численность военных" in sec[r["O_CHK"] - 59][4]


def test_peace_gov_imports():
    p = payload("b2_payload")
    rows = {r[0]: r for r in p["B2_DEMAND!A18:G27"] if r and r[0]}
    assert "B1_REAL!F$68" in rows["GDPE_GOV"][5]  # G follows section O output in B1
    assert "COEFS!$E$169*F$15" in rows["GDPE_IMP"][5]  # defence imports follow real defence spending
    c = {r[0]: r[4] for r in p["COEFS!A168:L170"]}
    assert 0.4 < c["GDPE_GOV_O_SH"] < 0.7 and 0.05 < c["GDPE_IMP_DEF_SH"] < 0.25
    assert "COEFS!$E$170*COEFS!$E$30" in p["B2_DEMAND!BB37"][0][0]  # stock draw when ports reopen
    assert 0.4 < p["COEFS!A168:L170"][2][4] < 0.8


def test_construction_reconstruction():
    p = payload("b1_payload")
    f = p["B1_REAL!A17:G29"][6]
    assert f[0] == "GVA_F" and "COEFS!$E$171*SCENARIOS!M124" in f[5]


def test_manufacturing_blocks():
    from macromodel.blocks.real_sector import manuf_blocks
    m = manuf_blocks()
    assert abs(sum(m["w"].values()) - 1) < 1e-9 and all(v > 0 for v in m["w"].values())
    assert m["fits"]["MACH"]["coef"]["GFCF"] > 0 and m["fits"]["LINK"]["r2"] > 0.9
    p = payload("b1_payload")
    sec = p["B1_REAL!A71:H82"]
    r = {row[0]: 71 + i for i, row in enumerate(sec) if row and row[0]}
    assert p["B1_REAL!A17:G29"][4][5] == f"=F{r['GVA_C_BU']}"  # row 21 takes the bottom-up block sum
    assert "B2_DEMAND" not in sec[r["C_OPK"] - 71][5]  # no loop through GDP of the same year
