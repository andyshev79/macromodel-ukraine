"""Block B5: external sector in USD.

Exports and imports in USD = real growth from B2 x USD price growth. Export
prices follow wheat and steel, import prices follow TTF gas (OLS 2016-2025).
Reserves change by the trade balance, remittances, FDI, other flows and the
external financing received; the exchange rate rule adds depreciation pressure
when reserves fall below five months of imports.
"""
import numpy as np
import pandas as pd

from macromodel.blocks.demand import real_levels_q
from macromodel.blocks.real_sector import EXT, annual_growth, ols, quarterly

EQUATIONS = {"EXP_P": ["PX"], "IMP_P": ["TTF"]}

CALIBRATED = {
    ("EXP_P", "const"): (2.0, "Мировая инфляция в USD; оценка 6,4 завышена ценовым шоком 2021–2022"),
    ("BOP", "OTHER"): (-9000.0, "Прочие потоки, млн USD в год: средний остаток 2022–2025 (инвестиционные доходы, погашения, "
                                "частный отток, покупка валюты населением). С 2026-10-26 переводы — полные (оплата труда + "
                                "трансферты, лист Dollar), поэтому остаток больше прежних −2500"),
    ("FX", "RES"): (3.0, "Доп. девальвация, п.п. на каждый месяц импорта ниже порога"),
    ("FX", "MONTHS"): (5.0, "Порог резервов для курса, месяцев импорта"),
}

COEF_ROWS = [("EXP_P", "const"), ("EXP_P", "PX"), ("IMP_P", "const"), ("IMP_P", "TTF"),
             ("BOP", "OTHER"), ("FX", "RES"), ("FX", "MONTHS")]


def annual() -> pd.DataFrame:
    d = quarterly()
    year = d.index.str[:4]
    g = annual_growth(real_levels_q())
    ext = pd.read_csv(EXT / "drivers_y.csv", index_col=0).drop(columns=["name", "unit", "source"]).T
    ext.index = ext.index.astype(str)
    ext = ext.astype(float)
    usd = d[["EXP_USD", "IMP_USD", "TRADE_BAL", "REMIT_USD", "FDI_L_USD", "FIN_RECEIVED_USD"]].groupby(year).sum(min_count=4)
    a = usd.assign(
        RES=d["RES_USD"].groupby(year).last(),
        EXP_P=((1 + usd["EXP_USD"].pct_change()) / (1 + g["EXP"] / 100) - 1) * 100,
        IMP_P=((1 + usd["IMP_USD"].pct_change()) / (1 + g["IMP"] / 100) - 1) * 100,
        PX=(ext["WHEAT"].pct_change() + ext["STEEL"].pct_change()) / 2 * 100,
        TTF=ext["TTF"].pct_change() * 100,
    )
    a["OTHER"] = a["RES"].diff() - (a["TRADE_BAL"] + a["REMIT_USD"] + a["FDI_L_USD"] + a["FIN_RECEIVED_USD"])
    return a


def estimate(first="2016", last="2025") -> dict:
    a = annual()
    return {y: ols(a.loc[first:last, y], a.loc[first:last, regs]) for y, regs in EQUATIONS.items()}


def coef_table() -> list[dict]:
    est = estimate()
    rows = []
    for eq, var in COEF_ROWS:
        if (eq, var) in CALIBRATED:
            v, note = CALIBRATED[(eq, var)]
            rows.append({"eq": eq, "var": var, "coef": v, "se": None, "r2": None, "method": "калибровка", "note": note})
        else:
            r = est[eq]
            rows.append({"eq": eq, "var": var, "coef": round(float(r["coef"][var]), 2), "se": round(float(r["se"][var]), 2),
                         "r2": round(float(r["r2"]), 2), "method": "оценка МНК 2016–2025, годовые", "note": ""})
    return rows


if __name__ == "__main__":
    print(annual().round(1).to_string())
    for y, r in estimate().items():
        print(y, {k: round(v, 2) for k, v in r["coef"].items()}, {k: round(v, 2) for k, v in r["se"].items()}, round(r["r2"], 2))


# Quarterly B5 (2026-10-26, agreed with Andrey): exchange rate (USD and EUR), trade and remittances by
# quarter, revaluation of reserves and FX debt. Facts for the rate and remittances come from MacroStat
# sheet Dollar (data/external/dollar_m.csv, scripts/build_dollar.py).
WAR_Q = ["2022Q1", "2022Q2", "2022Q3", "2022Q4", "2023Q1"]
SEAS_YEARS = ["2023", "2024", "2025"]  # quarterly shares of exports and imports in the year
Q_CALIBRATED = {
    ("REMQ", "STOCK"): (5000.0, "Украинцы за границей, тыс. человек: база для эффекта миграции на переводы "
                                "(ООН: около 5–6 млн беженцев в Европе). Оценка Claude"),
    ("REMQ", "MIGR"): (0.3, "Переводы: −0,3% на каждый 1% вернувшихся из-за границы (возвращаются в основном семьи получателей; с коэффициентом 1 модель занижала 2026 1 кв. в 2 раза). Оценка Claude"),
    ("RESQ", "EUR_SH"): (0.35, "Доля евро в резервах НБУ: переоценка резервов в USD при изменении EUR/USD. Оценка Claude"),
    ("DEBTQ", "EUR_SH"): (0.5, "Доля евро в валютном госдолге (кредиты ЕС, MFA, Ukraine Facility; евро в SDR МВФ). "
                               "Оценка Claude по структуре Минфина, уточнить"),
}


def dollar_q() -> pd.DataFrame:
    """Quarterly facts from sheet Dollar: average and end-of-quarter UAH/USD (the average from month-end
    rates, (previous + current) / 2 per month), EUR/USD and remittances (USD million; a quarter needs
    three months, a partly reported quarter is in REM_TOT_PART with the months it has)."""
    m = pd.read_csv(EXT / "dollar_m.csv", index_col="month").drop(columns="source")
    q = pd.PeriodIndex(m.index, freq="M").asfreq("Q").strftime("%YQ%q")
    eurusd = m["EUR_EOP"] / m["USD_EOP"]
    out = pd.DataFrame({
        "USD_AVG": ((m["USD_EOP"] + m["USD_EOP"].shift()) / 2).groupby(q).mean(),
        "USD_EOP": m["USD_EOP"].groupby(q).last(),
        "EURUSD": eurusd.groupby(q).mean(),
        "EURUSD_EOP": eurusd.groupby(q).last(),
    })
    for c in ("REM_TOT", "REM_OFF", "REM_INF"):
        out[c] = m[c].groupby(q).sum(min_count=3)
    out["REM_TOT_PART"] = m["REM_TOT"].groupby(q).sum(min_count=1)
    out["REM_MONTHS"] = m["REM_TOT"].groupby(q).count()
    return out


def remit_fit() -> dict:
    """Remittances y/y by quarter: persistence plus EUR/USD (much of the money comes from the euro area).
    A constant is left out: it is not significant and would turn the war-time fall into a permanent trend."""
    d = dollar_q()
    x = pd.DataFrame({"REM": d["REM_TOT"] / d["REM_TOT"].shift(4) * 100 - 100,
                      "EUR": d["EURUSD"] / d["EURUSD"].shift(4) * 100 - 100})
    x["REM_L"] = x["REM"].shift()
    s = x.loc["2019Q2":"2025Q4"].drop(WAR_Q, errors="ignore").dropna()
    X, y = s[["REM_L", "EUR"]].values, s["REM"].values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X) * (e @ e) / (len(y) - 2)))
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return {"coef": dict(zip(["REM_L", "EUR"], b)), "se": dict(zip(["REM_L", "EUR"], se)), "r2": float(r2), "n": len(y),
            "period": f"{s.index[0][:4]}–{s.index[-1][:4]}"}


def fx_volume_fit() -> dict:
    """Does the real exchange rate move export and import volumes? Real depreciation y/y (UAH/USD minus the
    inflation gap) against real exports and imports y/y (imports also on GDP), quarterly 2016-2025."""
    from macromodel import quarterly as Q
    from macromodel.blocks.demand import real_levels_q as demand_levels
    d, lv = quarterly(), demand_levels()
    x = pd.DataFrame(index=d.index)
    for k in ("EXP", "IMP"):
        x[k] = lv[k] / lv[k].shift(4) * 100 - 100
    x["RDEP"] = (d["FX_AVG"] / d["FX_AVG"].shift(4) * 100 - 100 - (d["CPI_YOY"] - 2)).shift(2)
    x["GDP"] = d["GDP_REAL"] / d["GDP_REAL"].shift(4) * 100 - 100
    out = {}
    for k, regs in (("EXP", ["RDEP"]), ("IMP", ["RDEP", "GDP"])):
        s = Q.sample(x, k, regs).loc["2016Q1":]
        out[k] = Q.ols_nw(s[k], s[regs]) | {"n": len(s)}
    return out


def seasonal_shares() -> pd.DataFrame:
    """Average share of each quarter in the year's exports and imports (USD), 2023-2025."""
    d = quarterly()[["EXP_USD", "IMP_USD"]]
    d = d.loc[[q for q in d.index if q[:4] in SEAS_YEARS]]
    sh = d / d.groupby(d.index.str[:4]).transform("sum")
    return sh.groupby(sh.index.str[-1]).mean()


def other_flows_remit_total() -> float:
    """Average 2022-2025 of the balance-of-payments residual when remittances are the total from sheet Dollar
    (net compensation of employees + private transfers) instead of private transfers only."""
    a = annual()
    rem = dollar_q()["REM_TOT"]
    a["REM_TOT"] = rem.groupby(rem.index.str[:4]).sum(min_count=4)
    other = a["RES"].diff() - (a["TRADE_BAL"] + a["REM_TOT"] + a["FDI_L_USD"] + a["FIN_RECEIVED_USD"])
    return float(other.loc["2022":"2025"].mean())
