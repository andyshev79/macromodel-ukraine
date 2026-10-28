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
                                          f"*(1+K{code['DEC_P']}/300)/(1+G{code['DEC_P']}/300)"
                                          f"*(1-K{code['WAGE_LOSS']}/100)/(1-G{code['WAGE_LOSS']}/100)")
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


def payload(name, *args):
    env = {**os.environ, "PYTHONPATH": "."}
    return json.loads(subprocess.run([sys.executable, f"sheet/{name}.py", *args], capture_output=True, text=True, check=True, env=env).stdout)


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
    sec = p["B1_REAL!A65:H75"]
    r = {row[0]: 65 + i for i, row in enumerate(sec) if row and row[0]}
    assert p["B1_REAL!A17:G31"][10][4] == f"=E{r['GVA_O']}"  # row 27 takes section O from the split
    assert "B4_LABOUR!H17:K17" in sec[r["MIL_NY"] - 65][4]  # defence follows military headcount
    assert "OK: численность военных" in sec[r["O_CHK"] - 65][4]


def test_peace_gov_imports():
    p = payload("b2_payload")
    rows = {r[0]: r for r in p["B2_DEMAND!A18:G27"] if r and r[0]}
    assert "B1_REAL!F$74" in rows["GDPE_GOV"][5]  # G follows section O output in B1
    assert "COEFS!$E$169*F$15" in rows["GDPE_IMP"][5]
    assert rows["GDPE_EXP"][5].startswith("=COEFS!$E$196*B10_AGRO!F41+")  # agro part of exports follows B10  # defence imports follow real defence spending
    c = {r[0]: r[4] for r in p["COEFS!A168:L170"]}
    assert 0.4 < c["GDPE_GOV_O_SH"] < 0.7 and 0.05 < c["GDPE_IMP_DEF_SH"] < 0.25
    inv = p["B2_DEMAND!BB32:BK37"][5][0]
    assert "B10_AGRO!$D$42:$G$42" in inv and "BB$30-1" in inv and "*AT35" in inv  # unshipped grain goes to stocks, last year's out
    assert 0.4 < p["COEFS!A168:L170"][2][4] < 0.8


def test_construction_reconstruction():
    p = payload("b1_payload")
    f = p["B1_REAL!A17:G31"][6]
    assert f[0] == "GVA_F" and f[5] == "=B9_CONSTRUCTION!F26"


def test_construction_block():
    from macromodel.blocks.construction import area_growth, coef_rows, fact_ytd, history, kind_facts, weights
    p = payload("b9_payload")
    t = p["B9_CONSTRUCTION!A1:H55"]
    assert [r[0] for r in t[21:26]] == ["F_CIVIL", "F_INFRA", "F_FORT", "CONSTR", "GVA_F"]
    assert t[24][4].startswith(f"=({fact_ytd()['months']}*E19+")  # 2026 anchored to the monthly facts
    assert "COEFS!$E$171*F13" in t[22][5] and "SCENARIOS!M131" in t[14][5]
    c = {r["code"]: r["coef"] for r in coef_rows()}
    assert abs(c["F_W_CIVIL"] + c["F_W_INFRA"] + c["F_W_FORT"] - 1) < 1e-9
    assert c["F_CIVIL_HH"] > 0 and 0.5 < c["F_LINK_CONSTR"] < 1.2
    h = history()
    assert h["lo"] < 0 < h["hi"] and 20 < h["gfcf_usd"] < 80
    assert -30 < fact_ytd()["yoy"] < 30
    w = weights()  # Ukrstat index by kind: weights sum to one, engineering works are the largest kind
    assert abs(sum(w.values()) - 1) < 1e-9 and w["ENG"] > w["NRES"] > w["RES"] > 0
    k = kind_facts()
    assert abs(k["facts"]["TOT"][str(k["year"])] - fact_ytd()["yoy"]) < 0.05  # same series as MacroStat
    assert set(area_growth()["growth"]) >= {"RES_DONE", "START"}
    assert [r[0] for r in t[52:55]] == ["KIND_BLD", "KIND_ENG", "START_CHK"] and "G41" in t[52][4]


def test_manufacturing_blocks():
    from macromodel.blocks.real_sector import manuf_blocks
    m = manuf_blocks()
    assert abs(sum(m["w"].values()) - 1) < 1e-9 and all(v > 0 for v in m["w"].values())
    assert m["fits"]["MACH"]["coef"]["GFCF"] > 0 and m["fits"]["LINK"]["r2"] > 0.9
    p = payload("b1_payload")
    sec = p["B1_REAL!A77:H88"]
    r = {row[0]: 77 + i for i, row in enumerate(sec) if row and row[0]}
    assert p["B1_REAL!A17:G31"][4][5] == f"=F{r['GVA_C_BU']}"  # row 21 takes the bottom-up block sum
    assert "B2_DEMAND" not in sec[r["C_OPK"] - 77][5]  # no loop through GDP of the same year


def test_agro_block():
    from macromodel.blocks.agro import ROW, coef_rows, crops, history
    p = payload("b10_payload")
    t = p["B10_AGRO!A1:I50"]
    assert [r[0] for r in t[18:26]] == ["WHEAT", "CORN", "BARLEY", "SUNFLOWER", "SOY", "RAPESEED", "HARVEST", "HARVEST_G"]
    assert t[18][5].endswith(f"*(1+COEFS!$E${ROW['A_SHIFT_WHEAT']}/100)")  # wheat area cut for the 2027 crop
    assert [r[0] for r in t[29:42]][-1] == "STOCK_D" and t[38][0] == "AGRO_EXP"
    assert "MIN(F33;F34)" in t[34][5]  # exports limited by ports and land routes
    c = crops()
    assert 70 < c.sum()["2025"] < 85 and set(c.index) == {"WHEAT", "CORN", "BARLEY", "SUNFLOWER", "SOY", "RAPESEED"}
    h = history()
    assert 0.3 < h["agro_sh"] < 0.6 and 5 < h["sigma"] < 20 and h["h1_now"] > 0
    b1 = payload("b1_payload")["B1_REAL!A1:H15"]
    assert b1[10][0] == "HARVEST" and b1[10][4] == "=B10_AGRO!E25"


def test_scenario_logic():
    t = payload("scenario_logic_payload")["SCENARIOS!A142:F189"]
    lim = {r[0]: r[3] for r in t[3:13]}
    assert lim["LIM_PORTS"] == 160 and lim["LIM_CAP"] == 24 and lim["FACT_PORTS"] == 84.8
    chk = [r for r in t[16:46]]
    assert t[14][3] == '=COUNTIF(D158:F187;"ВНИМАНИЕ*")' and chk[0][0] == "L_PORTS" and chk[-1][0] == "O_139"
    assert all(str(f).startswith("=") for r in chk for f in r[3:4])
    assert "C110:L110" in next(r for r in chk if r[0] == "L_MIL")[3]  # military headcount rows
    assert "C123:E123" in next(r for r in chk if r[0] == "C_PEACE")[3]  # peace effect rows


def test_other_split():
    from macromodel.blocks.real_sector import other_coef_rows, other_parts
    p = payload("b1_payload")
    sec = p["B1_REAL!A91:H98"]
    r = {row[0]: 91 + i for i, row in enumerate(sec) if row and row[0]}
    s2 = p["B1_REAL!A17:G31"]
    assert [x[0] for x in s2[11:14]] == ["GVA_OT_TAX", "GVA_OT_MKT", "GVA_OT_PUB"]  # rows 28-30: the three parts, no lump
    assert [x[5] for x in s2[11:14]] == [f"=F{r[k]}" for k in ("OT_TAX", "OT_MKT", "OT_PUB")]
    q = p["B1_REAL!A32:BK47"]
    assert q[-1][-1] == "=SUM(BK35:BK46)" and "$E$30:$G$30" in q[-2][-1]  # GDP = sectors + parts
    w = other_parts()["w"]
    assert abs(sum(w.values()) - 1) < 1e-9 and all(v > 0.1 for v in w.values())
    c = {(row["eq"], row["var"]): row["coef"] for row in other_coef_rows()}
    assert c[("GVA_OT_TAX", "HH")] > 0 and c[("GVA_OT_MKT", "HH")] > 0
    assert len(p["COEFS!A204:L216"]) == 13


def test_pub_services():
    from macromodel.blocks.real_sector import pub_prices
    p = payload("b1_payload")
    t = p["B1_REAL!A100:H110"]
    r = {row[0]: 100 + i for i, row in enumerate(t) if row and row[0]}
    assert p["B1_REAL!A91:H98"][4][5] == f"=F{r['PUB_REAL']}"  # row 95 takes real growth = fund over rates
    assert t[r["PUB_RATE"] - 100][4].startswith("=MAX(")  # rates never below the CPI floor
    assert "SCENARIOS!M194" in t[r["PUB_FUND"] - 100][5]
    pp = pub_prices()
    assert 0.5 < pp["coef"]["MINW"] < 1.2 and pp["r2"] > 0.5  # history: the deflator followed the minimum wage
    assert "SCENARIOS!A191:O194" in p  # pay fund defaults, written only without --coefs


def test_b5_quarterly():
    from macromodel.blocks import external as X
    p = payload("b5_payload")
    t = p["B5_EXTERNAL!A43:T95"]
    r = {row[0]: 43 + i for i, row in enumerate(t) if row and row[0] and " " not in row[0]}
    row = lambda k: t[r[k] - 43]
    assert isinstance(row("FXQ_RULE")[9], float)  # facts stay numbers: no loop via ANCHORS row 12
    assert "B4_LABOUR!G14:J14" in row("REMQ_G")[10]  # migration added back to last quarter's growth, does not compound
    assert row("OTHERQ")[9] == "=COEFS!$E$57/4"  # 2026Q3 tranche, not other flows, closes the reserve change
    assert row("RES_PRE")[10] == "=J72-K70+K71" and p["ANCHORS!BC24:BK24"][0][0] == "=B5_EXTERNAL!K72"
    assert "B5_EXTERNAL!H80:K80" in payload("b6_payload")["B6_FISCAL!A1:H47"][42][4]  # euro revaluation of FX debt
    fit = X.remit_fit()
    assert 0.8 < fit["coef"]["REM_L"] < 1 and fit["r2"] > 0.7
    assert "SCENARIOS!A196:O199" in p and "SCENARIOS!A196:O199" not in payload("b5_payload", "--coefs")
    sq = payload("scenarios_q_payload")
    assert "B5_EXTERNAL!J69" in sq["ANCHORS!BB29:BC29"][0][0] and "B5_EXTERNAL!J45" in sq["ANCHORS!BB12:BK12"][0][0]


def test_trade_real_wage():
    from macromodel.blocks.real_sector import trade_fit
    r = trade_fit()
    assert r["coef"]["RW_NEG"] > 0.5 and r["coef"]["RW_NEG"] / r["se"]["RW_NEG"] > 2  # falling real wages cut trade
    assert 0 <= r["coef"]["RW_POS"] < r["coef"]["RW_NEG"]  # rising ones add little
    p = payload("b1_payload")
    g = p["B1_REAL!A17:G31"][7]
    assert g[0] == "GVA_G" and "MIN(B4_LABOUR!F$74;0)" in g[5]  # trade is no longer a constant
    assert "ВНИМАНИЕ" in p["B1_REAL!H24"][0][0]


def test_peace_by_quarter():
    """Peace effect only after the ceasefire quarter; the year average feeds the annual equations."""
    p = payload("b2_payload")
    rows = {r[0]: r for r in p["B2_DEMAND!A18:G27"] if r and r[0]}
    assert "$H$54:$BK$54)/4" in rows["GDPE_HH"][5] and "SCENARIOS!" not in rows["GDPE_HH"][5]
    assert "$H$55:$BK$55)/4" in rows["GDPE_GFCF"][5] and "COEFS!$E$232*(B1_REAL!F$16-B1_REAL!E$16)" in rows["GDPE_GFCF"][5]
    assert "COEFS!$E$30*F$12/$D$12" in rows["GDPE_EXP"][5]  # port-dependent share follows the ports level against 2025
    q = p["B2_DEMAND!H51:BK55"]
    assert len(q[0]) == 56 and q[0][0] == "=H$31" and q[0][-1] == "=BK$31"
    assert q[2][0] == '=IF($C$52="нет";0;IF(H$31>=$C$52;1;0))'
    assert q[3][45] == "" and "SCENARIOS!$L$123:$N$123" in q[3][46] and "(BB53-AX53)" in q[3][46]
    hh = p["B2_DEMAND!BB32:BK37"][0][0]
    assert "-SUMIF($H$30:$BK$30;BB$30;$H$54:$BK$54)/4+BB54" in hh
    b1 = payload("b1_payload")
    assert any("B2_DEMAND!$H$55:$BK$55" in str(v) for v in b1.values())
    assert not any("SCENARIOS!L124" in str(v) or "SCENARIOS!M124" in str(v) for v in b1.values())


def test_bop_closure():
    """Reserves stay at the floor: extra financing first, then a forced import cut that devalues next year."""
    p = payload("b5_payload")
    sec = p["B5_EXTERNAL!A43:T95"]
    row = {r[0]: r for r in sec if r and r[0]}
    assert row["RESQ"][10] == "=K87+K91+K92" and row["RESQ"][9] == "=ANCHORS!BB24"
    assert row["RES_FLOOR"][10] == "=COEFS!$E$233*SUM(H57:K57)/12"
    assert row["EXTRA_FIN"][10] == "=MIN(K89;K90)" and row["EXTRA_AV"][10] == "=SCENARIOS!E297"
    assert row["IMP_CUT"][18] == "=S89-S91"
    assert "COEFS!$E$234*E$37" in row["FXQ_RULE"][11] and "COEFS!$E$234*F$37" in row["FXQ_RULE"][15]
    assert p["ANCHORS!BB22:BK22"][0][1] == "=B5_EXTERNAL!K57-B5_EXTERNAL!K92"
    sc = p["SCENARIOS!A293:O297"]
    assert sc[4][3] == "=CHOOSE(MATCH($C$3;$A$8:$A$10;0);D294;D295;D296)" and sc[2][3] == 0
    assert [r[4] for r in p["COEFS!A233:L234"]] == [3, 2]
    assert p["CHECKS!A40:Q41"][0][14] == "=B5_EXTERNAL!E37"


def test_idle_pay_layoffs():
    """Idle mills and ports: 2/3 pay lowers the average wage, layoffs after two idle quarters raise unemployment."""
    p = payload("b4_payload")
    rows = p["B4_LABOUR!A1:T105"]
    r = {row[0]: i + 1 for i, row in enumerate(rows) if row and row[0]}
    assert r["LAYOFF_U"] == 105 and r["WAGE_LOSS"] == 104
    assert rows[r["UNEMP"] - 1][12].endswith("+M105-I105")
    assert rows[r["WAGE"] - 1][12].endswith("*(1-M104/100)/(1-I104/100)")
    assert rows[r["IDLE_MET"] - 1][9] == "=MAX(0;1-B1_REAL!BB117/100)"
    assert rows[r["LAYOFF_N"] - 1][11] == "=COEFS!$E$240*MIN(K101;J101)"
    assert not any("§" in str(v) for row in rows for v in row)
    assert [x[4] for x in p["COEFS!A235:L240"]] == [160, 30, 0.667, 1.2, 5500, 0.3]


def test_deficit_2026_by_treasury_months():
    p = payload("b6_payload")
    sec = p["B6_FISCAL!A49:P56"]
    fact = sec[2][3:15]
    assert len([v for v in fact if v != ""]) == 8  # January-August 2026
    assert abs(sum(fact[:6]) - 303.15) < 0.1  # H1 matches the actual quarters in ANCHORS
    assert sec[4][3:15][8] == "=IF(L51<>\"\";L51;$D$52)"  # September: fact or the rest of the year
    q3, q4 = p["ANCHORS!BB27:BC27"][0]
    assert "J$53:$L$53" in q3 and "SUM($AZ27:$BB27)" in q4  # Q4 closes the annual deficit
    assert p["CHECKS!A43:D44"][0][3] == "=B6_FISCAL!D55"
