"""Block B2: real GDP by expenditure.

Components are chained in 2021 prices like the sectors in B1. Change in
inventories with the statistical discrepancy is the residual. Annual growth of
each component is explained by OLS on 2016-2025 with a 2022 dummy.
"""
import numpy as np
import pandas as pd

from macromodel.blocks.real_sector import annual_growth, chain_real, drivers, ols, quarterly

COMPONENTS = {
    "HH": ("GDPE_HH", "Потребление домохозяйств"),
    "GOV": ("GDPE_GEN_GOV", "Потребление госуправления"),
    "GFCF": ("GDPE_GFCF", "Валовое накопление основного капитала"),
    "EXP": ("GDPE_EGS", "Экспорт товаров и услуг"),
    "IMP": ("GDPE_IGS", "Импорт товаров и услуг"),
}

EQUATIONS = {
    "HH": ["REAL_WAGE", "WAR22"],
    "GOV": ["REAL_DEF", "WAR22"],
    "EXP": ["PORTS", "WAR22"],
    "IMP": ["DOM_DEMAND", "WAR22"],
}


def real_levels_q() -> pd.DataFrame:
    d = quarterly()
    out = pd.DataFrame({k: chain_real(d[f"{v}_NOM"].abs(), d[f"{v}_YOY"]) for k, (v, _) in COMPONENTS.items()})
    out["GDP"] = d["GDP_REAL"]
    out["INV"] = out["GDP"] - (out.HH + out.GOV + out.GFCF + out.EXP - out.IMP)
    return out.dropna(how="all")


def cpi_index_q() -> pd.Series:
    d = quarterly()
    return (1 + d["CPI_QOQ"] / 100).cumprod()


def regressors() -> pd.DataFrame:
    d = quarterly()
    year = d.index.str[:4]
    x = drivers()
    wage = d["WAGE_NOM"].groupby(year).mean()
    cpi = cpi_index_q().groupby(year).mean()
    x["REAL_WAGE"] = ((wage / cpi).pct_change() * 100).reindex(x.index)
    real_def = (d["BUDGET_DEFENCE"] / d["DEFL"]).groupby(year).sum(min_count=4)
    x["REAL_DEF"] = (real_def.pct_change() * 100).reindex(x.index)
    gp = annual_growth(real_levels_q_b1())
    x["GDP_P"] = gp["GDP"].reindex(x.index)
    lv = real_levels_q()
    yr = lv.groupby(lv.index.str[:4]).sum(min_count=4)
    dom = yr.HH + yr.GOV + yr.GFCF
    x["DOM_DEMAND"] = (dom.pct_change() * 100).reindex(x.index)
    return x


def real_levels_q_b1() -> pd.DataFrame:
    from macromodel.blocks import real_sector
    return real_sector.real_levels_q()


def estimate(first="2016", last="2025") -> dict:
    g = annual_growth(real_levels_q())
    x = regressors()
    res = {}
    for c, regs in EQUATIONS.items():
        df = pd.concat([g[c], x[regs]], axis=1).loc[first:last].dropna()
        res[c] = ols(df[c], df[regs])
    return res


# GFCF and the placeholders for blocks not yet built are calibrated: 2016-2025
# cannot separate the investment accelerator from the 2022-2023 swing.
CALIBRATED = {
    ("GFCF", "const"): (1.5, "Акселератор: подобран под средний рост 2024–2025 (6,5%)"),
    ("GFCF", "GDP_P"): (2.0, "Эластичность инвестиций к ВВП 2 (мировой опыт 1,5–3)"),
    ("RW", "GAP"): (4.0, "Не используется: с версии B4 реальная зарплата берётся из B4_LABOUR"),
    ("INV", "GDP_P"): (1.0, "Запасы и расхождение растут вместе с ВВП по производству"),
}

COEF_ROWS = [
    ("HH", "const"), ("HH", "REAL_WAGE"),
    ("GOV", "const"), ("GOV", "REAL_DEF"),
    ("GFCF", "const"), ("GFCF", "GDP_P"),
    ("EXP", "const"), ("EXP", "PORTS"),
    ("IMP", "const"), ("IMP", "DOM_DEMAND"),
    ("RW", "GAP"), ("INV", "GDP_P"),
]


def coef_table() -> list[dict]:
    from macromodel import quarterly

    est = estimate()
    rows = []
    for c, var in COEF_ROWS:
        if f"GDPE_{c}" in quarterly.USED:
            rows += quarterly.coef_rows(f"GDPE_{c}", [(f"GDPE_{c}", var)])
        elif (c, var) in CALIBRATED:
            v, note = CALIBRATED[(c, var)]
            rows.append({"eq": f"GDPE_{c}", "var": var, "coef": v, "se": None, "r2": None, "n": None,
                         "method": "калибровка", "note": note})
        else:
            r = est[c]
            rows.append({"eq": f"GDPE_{c}", "var": var, "coef": round(float(r["coef"][var]), 2),
                         "se": round(float(r["se"][var]), 2), "r2": round(float(r["r2"]), 2), "n": r["n"],
                         "method": "оценка МНК 2016–2025, годовые, дамми 2022", "note": ""})
    return rows


if __name__ == "__main__":
    lv = real_levels_q()
    print(annual_growth(lv).round(1).to_string())
    print(regressors().round(1).to_string())
    for c, r in estimate().items():
        cs = ", ".join(f"{k}={v:.2f} ({r['se'][k]:.2f})" for k, v in r["coef"].items())
        print(f"{c:5s} n={r['n']} R2={r['r2']:.2f} rmse={r['rmse']:.1f}  {cs}")


def link_other_to_consumption(first="2016", last="2025") -> dict:
    """GVA of other sectors and net taxes (B1) on household consumption (B2).

    Trade (G) and public administration (O) were tried against household and
    government consumption too; their slopes came out negative, so they keep
    their own equations in B1.
    """
    from macromodel.blocks import real_sector

    y = annual_growth(real_sector.real_levels_q())["OTHER"]
    x = pd.concat([annual_growth(real_levels_q())["HH"], regressors()["WAR22"]], axis=1)
    df = pd.concat([y.rename("OTHER"), x], axis=1).loc[first:last].dropna()
    return ols(df["OTHER"], df[["HH", "WAR22"]])
