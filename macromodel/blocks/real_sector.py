"""Block B1: real gross value added by sector.

Real levels are built in 2021 prices: the 2021 quarters equal nominal GVA, other
quarters are chained through the official real y/y growth rates. Each sector's
annual real growth is then explained by one or two scenario drivers with OLS.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "data" / "history"
EXT = ROOT / "data" / "external"

SECTORS = {
    "A": "Сельское хозяйство",
    "B": "Добыча",
    "C": "Переработка",
    "D": "Энергетика",
    "F": "Строительство",
    "G": "Торговля",
    "H": "Транспорт",
    "J": "ИКТ",
    "O": "Госуправление и оборона",
}

# Driver codes per sector; growth drivers enter as % change, STRIKES as change in index.
# WAR22 is a 2022 dummy that absorbs the invasion shock.
EQUATIONS = {
    "A": ["HARVEST"],
    "B": ["PORTS", "WAR22"],
    "C": ["EA_GDP", "WAR22"],
    "D": ["WAR22"],
    "F": ["WAR22"],
    "G": ["WAR22"],
    "H": ["PORTS", "WAR22"],
    "J": ["WAR22"],
    "O": ["WAR22"],
    "OTHER": ["WAR22"],
}


def quarterly() -> pd.DataFrame:
    s = pd.read_csv(HIST / "series_q.csv", index_col=0)
    a = pd.read_csv(HIST / "anchors_q.csv", index_col=0)
    return pd.concat([s, a]).T.apply(pd.to_numeric, errors="coerce")


def chain_real(nominal: pd.Series, yoy: pd.Series, base_year: str = "2021") -> pd.Series:
    """Real level in base-year prices from nominal and real y/y growth (%)."""
    idx = list(nominal.index)
    real = pd.Series(np.nan, index=idx)
    for q in idx:
        if q.startswith(base_year):
            real[q] = nominal[q]
    for i, q in enumerate(idx):
        if q[:4] > base_year and i >= 4 and pd.notna(yoy[q]):
            real[q] = real[idx[i - 4]] * (1 + yoy[q] / 100)
    for i in range(len(idx) - 1, 3, -1):
        q, p = idx[i], idx[i - 4]
        if p[:4] < base_year and pd.notna(yoy[q]) and pd.notna(real[q]):
            real[p] = real[q] / (1 + yoy[q] / 100)
    return real


def real_levels_q() -> pd.DataFrame:
    d = quarterly()
    out = {s: chain_real(d[f"GVA_{s}_NOM"], d[f"GVA_{s}_YOY"]) for s in SECTORS}
    out = pd.DataFrame(out)
    out["GDP"] = d["GDP_REAL"]
    out["OTHER"] = out["GDP"] - out[list(SECTORS)].sum(axis=1)
    return out.dropna(how="all")


def annual_growth(levels_q: pd.DataFrame) -> pd.DataFrame:
    year = levels_q.index.str[:4]
    full = levels_q.groupby(year).count().min(axis=1) == 4
    y = levels_q.groupby(year).sum()[full]
    return (y.pct_change() * 100).dropna()


def drivers() -> pd.DataFrame:
    x = pd.read_csv(EXT / "drivers_y.csv", index_col=0).drop(columns=["name", "unit", "source"]).T
    x.index = x.index.astype(str)
    g = pd.DataFrame(index=x.index)
    for c in ["HARVEST", "PORTS", "STEEL"]:
        g[c] = x[c].astype(float).pct_change() * 100
    g["EA_GDP"] = x["EA_GDP"].astype(float)
    g["STRIKES"] = x["STRIKES"].astype(float).diff()
    g["WAR22"] = (g.index == "2022").astype(float)
    d = quarterly()
    year = d.index.str[:4]
    real_def = (d["BUDGET_DEFENCE"] / d["DEFL"]).groupby(year).sum(min_count=4)
    g["DEFENCE"] = (real_def.pct_change() * 100).reindex(g.index)
    return g


def ols(y: pd.Series, X: pd.DataFrame) -> dict:
    X = X.assign(const=1.0)[["const"] + list(X.columns)]
    beta, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    resid = y.values - X.values @ beta
    dof = max(len(y) - X.shape[1], 1)
    sigma2 = resid @ resid / dof
    se = np.sqrt(np.diag(sigma2 * np.linalg.inv(X.values.T @ X.values)))
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    return {"coef": dict(zip(X.columns, beta)), "se": dict(zip(X.columns, se)),
            "r2": r2, "n": len(y), "rmse": float(np.sqrt(resid @ resid / len(y)))}


def estimate(first="2016", last="2025") -> dict:
    g = annual_growth(real_levels_q())
    x = drivers()
    res = {}
    for s, regs in EQUATIONS.items():
        df = pd.concat([g[s], x[regs]], axis=1).loc[first:last].dropna()
        res[s] = ols(df[s], df[regs])
    return res


if __name__ == "__main__":
    g = annual_growth(real_levels_q())
    print(g.round(1).to_string())
    for s, r in estimate().items():
        cs = ", ".join(f"{k}={v:.2f} ({r['se'][k]:.2f})" for k, v in r["coef"].items())
        print(f"{s:6s} n={r['n']} R2={r['r2']:.2f} rmse={r['rmse']:.1f}  {cs}")


# Coefficient table written to the COEFS sheet. "оценка" rows come from estimate();
# "калибровка" rows are set by judgement where ten annual points cannot identify the effect.
CALIBRATED = {
    ("B", "CAP"): (0.3, "Удары по энергетике: 30% от изменения доступной мощности"),
    ("C", "CAP"): (0.3, "Удары по энергетике: 30% от изменения доступной мощности"),
    ("D", "const"): (0.0, "Выпуск энергетики ограничен доступной мощностью"),
    ("D", "CAP"): (1.0, "Эластичность 1: выпуск растёт и падает вместе с мощностью"),
    ("F", "const"): (14.0, "Средний рост 2024–2025 (оборонное строительство и восстановление)"),
    ("J", "const"): (4.9, "Средний рост 2024–2025; оценка 2016–2025 (7,6) завышена довоенным бумом"),
    ("O", "DEF"): (0.3, "Реакция на изменение доли расходов на оборону в ВВП"),
}

COEF_ROWS = [
    ("A", "const"), ("A", "HARVEST"),
    ("B", "const"), ("B", "PORTS"), ("B", "CAP"),
    ("C", "const"), ("C", "EA_GDP"), ("C", "CAP"),
    ("D", "const"), ("D", "CAP"),
    ("F", "const"),
    ("G", "const"),
    ("H", "const"), ("H", "PORTS"),
    ("J", "const"),
    ("O", "const"), ("O", "DEF"),
    ("OTHER", "const"),
]


def coef_table() -> list[dict]:
    est = estimate()
    rows = []
    for s, var in COEF_ROWS:
        if (s, var) in CALIBRATED:
            v, note = CALIBRATED[(s, var)]
            rows.append({"eq": f"GVA_{s}", "var": var, "coef": v, "se": None, "r2": None, "n": None,
                         "method": "калибровка", "note": note})
        else:
            r = est[s]
            rows.append({"eq": f"GVA_{s}", "var": var, "coef": round(r["coef"][var], 2),
                         "se": round(r["se"][var], 2), "r2": round(r["r2"], 2), "n": r["n"],
                         "method": "оценка МНК 2016–2025, годовые, дамми 2022", "note": ""})
    return rows
