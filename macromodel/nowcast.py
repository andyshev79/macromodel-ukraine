"""Nowcast of the current quarter from Gosstat monthly indices (04.11.2026).

Bridge equations: sector real GVA y/y (quarter) = a + b x quarterly average of the monthly y/y index.
A partial quarter takes the months that are out and fills the rest with the last month's y/y.
The gap between the nowcast and the model equation growth fades: gap x rho^h (rho per sector from
the persistence of the sector's y/y growth). Backtest: 2016-2025 without 2022, with 1, 2 and 3 months.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UK = ROOT / "data" / "ukrstat"
HIST = ROOT / "data" / "history" / "series_q.csv"

# indicator -> (file, series key or list of keys for tonnes, kind)
IND = {
    "AGRO": ("agro", ["INDC_AGRCLT.C_2016.CORMONTH_PREV_YEAR.AGRICUTURE_GROUP.ALL_AGRICULTURAL_HOLDINGS.M",
                      "INDC_AGRCLT.C_2021.CORMONTH_PREV_YEAR.AGRICUTURE_GROUP.ALL_AGRICULTURAL_HOLDINGS.M"], "yoy"),
    "IND_B": ("industry_m", ["INDX_IND_PROD.UNADJ_CORR_MON_PREV_Y.EAT_MIG.B.M"], "yoy"),
    "IND_C": ("industry_m", ["INDX_IND_PROD.UNADJ_CORR_MON_PREV_Y.EAT_MIG.C.M"], "yoy"),
    "IND_D": ("industry_m", ["INDX_IND_PROD.UNADJ_CORR_MON_PREV_Y.EAT_MIG.D.M"], "yoy"),
    "IND_BCD": ("industry_m", ["INDX_IND_PROD.UNADJ_CORR_MON_PREV_Y.EAT_MIG.BCD.M"], "yoy"),
    "CONSTR": ("construction_m", ["INDX_CONSTRUCTION_PRODUCTS.UNADJ_CORR_MON_PREV_Y.TYPES_CONSTRUCTION.0.M"], "yoy"),
    "RETAIL": ("retail_m", ["IDX_TRNVR_RTL_TRADE_VOL.UNADJ_CORR_MON_PREV_Y.M"], "yoy"),
    # ton-km, rail + road: tracks GVA_H in 2025-2026 better than tonnes (road tonnes +20% while transport GVA fell)
    "FREIGHT": ("freight_m", ["CARG_TRNVR_TON_KM.RAIL._Z._Z._Z._Z._Z._Z._Z._Z._Z.M",
                              "CARG_TRNVR_TON_KM.ROAD._Z._Z._Z._Z._Z._Z._Z._Z._Z.M"], "sum_level"),
    "PPI": ("ppi_m", ["INDEX_PRODPRICE.NACE_GROUP.BCD.CORMONTH_PREV_YEAR.DIST_0.M"], "yoy"),
}
NAMES = {"AGRO": "Индекс сельхозпродукции, % г/г", "IND_B": "Промышленность: добыча (B), % г/г",
         "IND_C": "Промышленность: переработка (C), % г/г", "IND_D": "Промышленность: энергетика (D), % г/г",
         "IND_BCD": "Промышленность всего (B+C+D), % г/г", "CONSTR": "Строительная продукция, % г/г",
         "RETAIL": "Розничный товарооборот (сопоставимые цены), % г/г",
         "FREIGHT": "Грузооборот ж/д + авто, т·км, % г/г", "PPI": "Цены производителей промышленности, % г/г"}
# sector -> indicator; quarterly history of the indicator: series_q code (longer) or the monthly cache
BRIDGE = {"A": "AGRO", "B": "IND_B", "C": "IND_C", "D": "IND_D", "F": "CONSTR", "G": "RETAIL", "H": "FREIGHT"}
HIST_Q = {"IND_B": "IND_B_YOY", "IND_C": "IND_C_YOY", "IND_D": "IND_D_YOY", "CONSTR": "CONSTR_YOY", "RETAIL": "RETAIL_YOY"}
SAMPLE = ("2016Q1", "2025Q4")
EXCL = ("2022Q1", "2022Q4")
RHO_EXCL = EXCL   # pairs that touch 2022 are dropped
RHO_CLIP = (0.3, 0.9)


def monthly_yoy(name: str) -> pd.Series:
    """Monthly y/y, % (index 100 = no change -> 0)."""
    f, keys, kind = IND[name]
    d = pd.read_csv(UK / f"{f}.csv.gz")
    d = d[d.series.isin(keys)].dropna(subset=["value"])
    if kind == "yoy":
        s = d.groupby("period").value.last() - 100     # C_2021 base overrides C_2016 where both exist
    else:
        lv = d.groupby("period").value.sum()
        lv.index = pd.PeriodIndex(lv.index, freq="M")
        s = (lv / lv.shift(12, freq="M") * 100 - 100).dropna()
        s.index = s.index.astype(str)
    s.index = pd.PeriodIndex(s.index, freq="M")
    return s.sort_index()


def quarterly(m: pd.Series, months: int | None = None) -> pd.Series:
    """Quarterly mean of monthly y/y. months = 1/2/3 keeps only the first months of every quarter and fills the
    rest with the last kept month (the rule of the partial quarter). None = the actual data, incl. a partial last quarter."""
    out = {}
    for q, g in m.groupby(m.index.asfreq("Q")):
        g = g.sort_index()
        pos = (g.index.month - 1) % 3
        if months is not None:
            g = g[pos < months]
        if g.empty:
            continue
        vals = list(g.values) + [g.values[-1]] * (3 - len(g))
        out[str(q)] = float(np.mean(vals[:3]))
    return pd.Series(out)


def hist_q() -> pd.DataFrame:
    return pd.read_csv(HIST, index_col=0)


def indicator_q(name: str, months: int | None = None) -> pd.Series:
    """Quarterly indicator; history before the monthly cache from series_q (full quarters only)."""
    q = quarterly(monthly_yoy(name), months)
    if name in HIST_Q and months is None:
        h = hist_q().loc[HIST_Q[name]].dropna()
        q = pd.concat([h[~h.index.isin(q.index)], q]).sort_index()
    return q


def _sample(idx, lo=SAMPLE[0], hi=SAMPLE[1], excl=EXCL):
    return [q for q in idx if lo <= q <= hi and not (excl[0] <= q <= excl[1])]


def bridges() -> dict:
    """Sector -> dict(a, b, r2, n, rmse, rho, sample)."""
    h = hist_q()
    res = {}
    for s, ind in BRIDGE.items():
        y = h.loc[f"GVA_{s}_YOY"].dropna()
        x = indicator_q(ind)
        idx = _sample(sorted(set(y.index) & set(x.index)))
        X, Y = x[idx].values, y[idx].values
        b, a = np.polyfit(X, Y, 1)
        e = Y - (a + b * X)
        r2 = 1 - e.var() / Y.var()
        # rho: AR(1) of the demeaned y/y growth of the sector
        g = y[_sample(y.index, excl=RHO_EXCL)]
        g = g - g.mean()
        lag = g.shift(1)
        ok = lag.notna() & pd.Series([QUARTERS_NEXT(p, c) for p, c in zip([None] + list(g.index[:-1]), g.index)], index=g.index)
        rho = float(np.clip((g[ok] * lag[ok]).sum() / (lag[ok] ** 2).sum(), *RHO_CLIP))
        res[s] = dict(ind=ind, a=float(a), b=float(b), r2=float(r2), n=len(idx), rmse=float(np.sqrt((e ** 2).mean())),
                      rho=rho, sample=f"{idx[0]}–{idx[-1]}, без 2022")
    return res


def QUARTERS_NEXT(p, c) -> bool:
    """True when quarter c directly follows p (no gap from the excluded years)."""
    if p is None:
        return False
    return pd.Period(p, freq="Q") + 1 == pd.Period(c, freq="Q")


def backtest() -> pd.DataFrame:
    """RMSE of the nowcast with 1, 2, 3 months vs the naive forecast (last quarter's y/y), pp."""
    h = hist_q()
    br = bridges()
    rows = []
    for s, ind in BRIDGE.items():
        y = h.loc[f"GVA_{s}_YOY"].dropna()
        m = monthly_yoy(ind)
        rec = {"sector": s}
        for k in (1, 2, 3):
            x = quarterly(m, k)
            idx = _sample(sorted(set(y.index) & set(x.index)))
            e = y[idx] - (br[s]["a"] + br[s]["b"] * x[idx])
            rec[f"m{k}"] = float(np.sqrt((e ** 2).mean()))
            rec["n"] = len(idx)
        naive = y.shift(1)
        idx = [q for q in _sample(y.index) if not pd.isna(naive.get(q)) and QUARTERS_NEXT(prev(q), q)
               and prev(q) in y.index and q in set(quarterly(m, 3).index)]
        rec["naive"] = float(np.sqrt(((y[idx] - naive[idx]) ** 2).mean()))
        rows.append(rec)
    return pd.DataFrame(rows).set_index("sector")


def prev(q: str) -> str:
    return str(pd.Period(q, freq="Q") - 1)


def ppi_rho() -> float:
    """Persistence of the PPI y/y deviation from its mean (end of quarter, 2016-2025 without 2022)."""
    a = pd.read_csv(ROOT / "data" / "history" / "anchors_q.csv", index_col=0).loc["PPI_YOY"].dropna()
    g = a[_sample(a.index)]
    g = g - g.mean()
    pairs = [(g[p], g[c]) for p, c in zip(g.index[:-1], g.index[1:]) if QUARTERS_NEXT(p, c)]
    x, y = np.array(pairs).T
    return float(np.clip((x * y).sum() / (x ** 2).sum(), *RHO_CLIP))


def monthly_table(first="2025-01", last="2028-12") -> pd.DataFrame:
    """Monthly y/y (%, rounded) for the NOWCAST sheet: indicators x months; NaN = not out yet."""
    months = pd.period_range(first, last, freq="M")
    return pd.DataFrame({n: monthly_yoy(n).reindex(months) for n in IND}).T.round(1)


if __name__ == "__main__":
    for s, r in bridges().items():
        print(s, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    print(backtest().round(2))
    print("rho PPI", round(ppi_rho(), 2))
    for n in IND:
        print(n, indicator_q(n).tail(3).round(1).to_dict())
