"""Block B5: external sector in USD.

Exports and imports in USD = real growth from B2 x USD price growth. Export
prices follow wheat and steel, import prices follow TTF gas (OLS 2016-2025).
Reserves change by the trade balance, remittances, FDI, other flows and the
external financing received; the exchange rate rule adds depreciation pressure
when reserves fall below five months of imports.
"""
import pandas as pd

from macromodel.blocks.demand import real_levels_q
from macromodel.blocks.real_sector import EXT, annual_growth, ols, quarterly

EQUATIONS = {"EXP_P": ["PX"], "IMP_P": ["TTF"]}

CALIBRATED = {
    ("EXP_P", "const"): (2.0, "Мировая инфляция в USD; оценка 6,4 завышена ценовым шоком 2021–2022"),
    ("BOP", "OTHER"): (-2500.0, "Прочие потоки, млн USD в год: средний остаток 2022–2025 (доходы, погашения, частный отток)"),
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
