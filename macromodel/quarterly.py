"""Quarterly re-estimation of equations whose drivers exist by quarter (y/y growth rates).

Ten annual points are too few, so the same relations are fitted on 2011Q1-2025Q4
quarterly y/y data from the long history (data/history/long): about 55 points after
dropping the invasion quarters 2022Q1-2023Q1 (the y/y base effect of 2022 lasts into
2023Q1). The 2014-2015 crisis stays in the sample; CPI gets a second exchange-rate term
above FX_THR devaluation, because pass-through in that crisis was far stronger than in
calm years. Overlapping y/y rates are autocorrelated,
so t-statistics use Newey-West errors with 4 lags.

Out-of-sample check, comparable with macromodel.quality: estimate on quarters before year t,
predict the four quarters of t (lagged dependent variables are fed with the model's own
predictions), take the year average (year-end for the NBU rate) and compare with the fact.

USED lists the equations whose COEFS rows now come from here: they beat the annual fit
out of sample with significant drivers. CPI inertia (SHOCK_CPI_SPEED) is also estimated here.
"""
import numpy as np
import pandas as pd

from macromodel.blocks.demand import cpi_index_q, real_levels_q
from macromodel.blocks.real_sector import HIST, quarterly

HIST_LONG = HIST / "long"

FIRST, LAST = "2011Q1", "2025Q4"
FX_THR = 15  # devaluation, % y/y, above which pass-through to CPI rises (2014–2015 crisis)
WAR = ["2022Q1", "2022Q2", "2022Q3", "2022Q4", "2023Q1"]
TEST_YEARS = ["2023", "2024", "2025"]
METHOD = "оценка МНК 2011–2025, квартальные г/г без 2022Q1–2023Q1, ошибки Ньюи–Уэста"

# Equation id as on COEFS/MODEL_QUALITY -> (dependent, drivers); driver names as in the annual block
EQUATIONS = {
    "CPI": ("CPI", ["FX", "FX_BIG", "WAGE"]),
    "PPI": ("PPI", ["CPI"]),
    "DEFL": ("DEFL", ["CPI", "PPI"]),
    "RATE": ("RATE", ["CPI", "RATE_L1"]),
    "LOAN": ("LOAN", ["RATE_AVG"]),
    "DEP": ("DEP", ["RATE_AVG"]),
    "GDPE_HH": ("HH", ["REAL_WAGE"]),
    "GDPE_GOV": ("GOV", ["REAL_DEF"]),
    "GDPE_IMP": ("IMP", ["DOM_DEMAND"]),
    "GVA_C": ("GVA_C", ["MET", "HH"]),  # manufacturing on metallurgy output and household demand
}
INERTIA = ("CPI", ["FX", "FX_BIG", "WAGE", "CPI_L1"])
USED = {"CPI", "LOAN", "GDPE_HH", "GDPE_IMP", "GVA_C"}


def long_quarterly() -> pd.DataFrame:
    """Quarterly history from 2005 (data/history/long), same codes as data/history."""
    s = pd.read_csv(HIST_LONG / "series_q.csv", index_col=0)
    a = pd.read_csv(HIST_LONG / "anchors_q.csv", index_col=0)
    return pd.concat([s, a]).T.apply(pd.to_numeric, errors="coerce")


def data(long: bool = True) -> pd.DataFrame:
    yoy = lambda s: (s / s.shift(4) - 1) * 100
    if long:
        d = long_quarterly()
        cpi = (1 + d["CPI_QOQ"] / 100).cumprod()
        w = {c: d[f"GDPE_{n}_NOM"].shift(4) for c, n in [("HH", "HH"), ("GOV", "GEN_GOV"), ("GFCF", "GFCF")]}
        g = {c: d[f"GDPE_{n}_YOY"] for c, n in [("HH", "HH"), ("GOV", "GEN_GOV"), ("GFCF", "GFCF")]}
        dom = sum(w[c] * g[c] for c in w) / sum(w.values())
        q = pd.DataFrame({
            "CPI": d["CPI_YOY"], "PPI": d["PPI_YOY"], "DEFL": yoy(d["GDP_NOM"] / d["GDP_REAL"]),
            "FX": yoy(d["FX_AVG"]), "WAGE": yoy(d["WAGE_NOM"]),
            "RATE": d["NBU_RATE"], "RATE_AVG": d["NBU_RATE"], "LOAN": d["LOAN_RATE"], "DEP": d["DEP_RATE"],
            "HH": d["GDPE_HH_YOY"], "GOV": d["GDPE_GEN_GOV_YOY"], "IMP": d["GDPE_IGS_YOY"], "DOM_DEMAND": dom,
            "REAL_WAGE": yoy(d["WAGE_NOM"] / cpi),
            "REAL_DEF": yoy(d["BUDGET_DEFENCE"] / (d["GDP_NOM"] / d["GDP_REAL"])),
            "GVA_C": d["GVA_C_YOY"], "MET": d["IND_C8_YOY"],
        })
        q["CPI_L1"] = q["CPI"].shift()
        q["RATE_L1"] = q["RATE"].shift()
        q["FX_BIG"] = (q["FX"] - FX_THR).clip(lower=0)
        return q
    d = quarterly()
    lv = real_levels_q()
    q = pd.DataFrame({
        "CPI": d["CPI_YOY"], "PPI": d["PPI_YOY"], "DEFL": yoy(d["DEFL"]),
        "FX": yoy(d["FX_AVG"]), "WAGE": yoy(d["WAGE_NOM"]),
        "RATE": d["NBU_RATE"], "RATE_AVG": d["NBU_RATE"], "LOAN": d["LOAN_RATE"], "DEP": d["DEP_RATE"],
        "HH": yoy(lv["HH"]), "GOV": yoy(lv["GOV"]), "IMP": yoy(lv["IMP"]),
        "DOM_DEMAND": yoy(lv["HH"] + lv["GOV"] + lv["GFCF"]),
        "REAL_WAGE": yoy(d["WAGE_NOM"] / cpi_index_q()),
        "REAL_DEF": yoy(d["BUDGET_DEFENCE"] / d["DEFL"]),
    })
    q["CPI_L1"] = q["CPI"].shift()
    q["RATE_L1"] = q["RATE"].shift()
    q["FX_BIG"] = (q["FX"] - FX_THR).clip(lower=0)
    return q


def ols_nw(y: pd.Series, X: pd.DataFrame, lags: int = 4) -> dict:
    X = X.assign(const=1.0)[["const"] + list(X.columns)]
    Xv = X.values
    beta, *_ = np.linalg.lstsq(Xv, y.values, rcond=None)
    e = y.values - Xv @ beta
    inv = np.linalg.inv(Xv.T @ Xv)
    u = Xv * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        G = u[L:].T @ u[:-L]
        S += (1 - L / (lags + 1)) * (G + G.T)
    se = np.sqrt(np.diag(inv @ S @ inv))
    r2 = 1 - e @ e / ((y - y.mean()) @ (y - y.mean()))
    return {"coef": dict(zip(X.columns, beta)), "se": dict(zip(X.columns, se)), "r2": float(r2), "n": len(y)}


def sample(q: pd.DataFrame, y: str, regs: list, before: str | None = None) -> pd.DataFrame:
    df = q[[y] + regs].loc[FIRST:LAST].dropna().drop(index=WAR, errors="ignore")
    return df[df.index < before] if before else df


def oos(q: pd.DataFrame, y: str, regs: list) -> dict:
    lag = f"{y}_L1"
    out = {}
    for yr in TEST_YEARS:
        tr = sample(q, y, regs, before=f"{yr}Q1")
        c = ols_nw(tr[y], tr[regs])["coef"]
        te = q[[y] + regs].loc[f"{yr}Q1":f"{yr}Q4"].copy()
        prev, pred = q[y].loc[:f"{int(yr) - 1}Q4"].iloc[-1], []
        for i in te.index:
            if lag in regs:
                te.loc[i, lag] = prev
            prev = c["const"] + sum(c[k] * te.loc[i, k] for k in regs)
            pred.append(prev)
        pred = pd.Series(pred, index=te.index)
        fact, model = (te[y].iloc[-1], pred.iloc[-1]) if y == "RATE" else (te[y].mean(), pred.mean())
        out[yr] = float(fact - model)
    return out


def estimate() -> dict:
    q = data()
    res = {}
    for eq, (y, regs) in EQUATIONS.items():
        df = sample(q, y, regs)
        r = ols_nw(df[y], df[regs])
        r["oos"] = oos(q, y, regs)
        r["mae"] = float(np.mean(np.abs(list(r["oos"].values()))))
        r["min_t"] = min(abs(r["coef"][k] / r["se"][k]) for k in regs)
        res[eq] = r
    return res


def cpi_speed() -> tuple[float, float]:
    """Share of the gap to the long-run CPI closed in a quarter: 1 − coefficient on last quarter's CPI."""
    y, regs = INERTIA
    df = sample(data(), y, regs)
    r = ols_nw(df[y], df[regs])
    return 1 - r["coef"]["CPI_L1"], r["se"]["CPI_L1"]


def coef_rows(eq: str, rows: list) -> list[dict]:
    """COEFS rows for an equation in USED: rows are (eq_id_on_sheet, var) pairs."""
    r = estimate()[eq]
    y, regs = EQUATIONS[eq]
    first = sample(data(), y, regs).index[0][:4]  # later than FIRST when a driver starts later
    method = METHOD.replace(FIRST[:4], first)
    return [{"eq": e, "var": v, "coef": round(float(r["coef"][v]), 2), "se": round(float(r["se"][v]), 2),
             "r2": round(r["r2"], 2), "n": r["n"], "method": method, "period": f"{first}–{LAST[:4]}", "note": ""}
            for e, v in rows]


if __name__ == "__main__":
    for eq, r in estimate().items():
        cs = ", ".join(f"{k}={v:.2f} (t {v / r['se'][k]:.1f})" for k, v in r["coef"].items())
        oo = " ".join(f"{v:+.1f}" for v in r["oos"].values())
        print(f"{eq:9s} n={r['n']} R2={r['r2']:.2f} oos[{oo}] mae={r['mae']:.1f}  {cs}")
    print("CPI speed %.2f (se %.2f)" % cpi_speed())
