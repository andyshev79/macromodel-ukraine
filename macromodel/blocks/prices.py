"""Block B3: prices.

Annual average CPI, PPI and GDP deflator growth, explained by OLS on 2016-2025
with a 2022 dummy. CPI follows nominal wages and the hryvnia exchange rate,
PPI follows CPI and the TTF gas price, the deflator is a mix of CPI and PPI.
Nominal wages and the exchange rate stay simple rules until blocks B4 and B5.
"""
import pandas as pd

from macromodel.blocks.real_sector import EXT, drivers, ols, quarterly

EQUATIONS = {
    "CPI": ["FX", "WAGE", "WAR22"],
    "PPI": ["CPI", "TTF"],
    "DEFL": ["CPI", "PPI"],
}

COEF_ROWS = [
    ("CPI", "const"), ("CPI", "FX"), ("CPI", "WAGE"),
    ("PPI", "const"), ("PPI", "CPI"), ("PPI", "TTF"),
    ("DEFL", "const"), ("DEFL", "CPI"), ("DEFL", "PPI"),
]


def annual() -> pd.DataFrame:
    d = quarterly()
    year = d.index.str[:4]
    full = d["GDP_NOM"].groupby(year).count() == 4
    a = pd.DataFrame({
        "CPI": d["CPI_YOY"].groupby(year).mean(),
        "PPI": d["PPI_YOY"].groupby(year).mean(),
        "FX": d["FX_AVG"].groupby(year).mean().pct_change() * 100,
        "WAGE": d["WAGE_NOM"].groupby(year).mean().pct_change() * 100,
        "DEFL": (d["GDP_NOM"].groupby(year).sum() / d["GDP_REAL"].groupby(year).sum())[full].pct_change() * 100,
    })
    ext = pd.read_csv(EXT / "drivers_y.csv", index_col=0).drop(columns=["name", "unit", "source"]).T
    ext.index = ext.index.astype(str)
    a["TTF"] = ext["TTF"].astype(float).pct_change() * 100
    a["HICP"] = ext["HICP"].astype(float)
    a["WAR22"] = drivers()["WAR22"]
    return a


def estimate(first="2016", last="2025") -> dict:
    a = annual()
    res = {}
    for y, regs in EQUATIONS.items():
        df = a[[y] + regs].loc[first:last].dropna()
        res[y] = ols(df[y], df[regs])
    return res


def coef_table() -> list[dict]:
    est = estimate()
    return [{"eq": y, "var": v, "coef": round(float(est[y]["coef"][v]), 2), "se": round(float(est[y]["se"][v]), 2),
             "r2": round(float(est[y]["r2"]), 2), "n": est[y]["n"],
             "method": "оценка МНК 2016–2025, годовые" + (", дамми 2022" if "WAR22" in EQUATIONS[y] else ""),
             "note": ""} for y, v in COEF_ROWS]


if __name__ == "__main__":
    print(annual().round(1).to_string())
    for y, r in estimate().items():
        cs = ", ".join(f"{k}={v:.2f} ({r['se'][k]:.2f})" for k, v in r["coef"].items())
        print(f"{y:5s} n={r['n']} R2={r['r2']:.2f} rmse={r['rmse']:.1f}  {cs}")
