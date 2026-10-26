"""Gosstat snapshots (data/ukrstat/) turned into quarterly series the model uses, and the
cross-check of those series against the model history (data/history/), which is built
from the NBU API and other republished copies of Gosstat data.

A mismatch means one of two things: Gosstat revised the series and the copy has not caught
up yet, or the two use different definitions. The cross-check shows where to look.
"""
from pathlib import Path

import pandas as pd

from macromodel.history import m_to_q, q_label

# code in data/history -> (set, series id in the snapshot, monthly-to-quarter rule or None for
# quarterly data, shift so the unit matches: index (same period last year = 100) minus 100 -> % y/y)
CHECKS = {
    "GDP_NOM": ("gdp_q", "GROSS_DOM_PRODUCT.CURR_PRICES._T.Q", None, 0),
    "GDP_REAL_YOY": ("gdp_q", "GROSS_DOM_PRODUCT.IDX_VOLUME_CONST_2021._T.Q", None, -100),
    "CPI_YOY": ("cpi_m", "INDEX_CONSUMPRICE.CORMONTH_PREV_YEAR.0.M", "END", -100),
    "CORE_CPI_YOY": ("cpi_m", "CORE_INFL.CORMONTH_PREV_YEAR._Z.M", "END", -100),
    "PPI_YOY": ("ppi_m", "INDEX_PRODPRICE.NACE_GROUP.BCD.CORMONTH_PREV_YEAR.DIST_0.M", "END", -100),
    "WAGE_NOM": ("wages_m", "AVG_SALARY_UAH._Z._T.SEX._T.M", "AVG", 0),
    "IND_PROD_YOY": ("industry_m", "INDX_IND_PROD.UNADJ_CORR_MON_PREV_Y.EAT_MIG.BCD.M", "AVG", -100),
    "RETAIL_YOY": ("retail_m", "IDX_TRNVR_RTL_ENTRP_VOL.UNADJ_CORR_MON_PREV_Y.M", "AVG", -100),
    "CONSTR_YOY": ("construction_m", "INDX_CONSTRUCTION_PRODUCTS.UNADJ_CORR_MON_PREV_Y.TYPES_CONSTRUCTION.0.M", "AVG", -100),
}
# a gap below this is rounding: % points for growth rates, % of the level for levels
TOL = {"GDP_NOM": 0.1, "WAGE_NOM": 0.5}
TOL_PP = 0.15


def snapshot(folder: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(folder / f"{name}.csv.gz", dtype={"series": str, "period": str, "flag": str, "updated": str})


def quarterly(folder: Path, code: str) -> pd.Series:
    """The quarterly series behind one CHECKS entry, labelled like data/history ("2026Q2")."""
    name, sid, how, shift = CHECKS[code]
    df = snapshot(folder, name)
    s = df[df["series"] == sid].set_index("period")["value"].dropna()
    if s.empty:
        raise KeyError(f"{code}: no series {sid} in {name}")
    if how is None:
        s = s[s.index.str.contains("Q")]
        return s + shift
    s.index = pd.PeriodIndex(s.index, freq="M")
    return q_label(m_to_q(s + shift, how))


def crosscheck(folder: Path, history: Path, last: int = 12) -> pd.DataFrame:
    """Gosstat vs model history over the last `last` quarters with data in both."""
    hist = pd.concat([pd.read_csv(history / f, index_col=0) for f in ("anchors_q.csv", "series_q.csv")])
    rows = []
    for code in CHECKS:
        try:
            g = quarterly(folder, code)
        except (FileNotFoundError, KeyError):
            continue
        if code not in hist.index:
            continue
        h = hist.loc[code].dropna()
        h.index = h.index.astype(str)
        both = g.index.intersection(h.index)[-last:]
        for q in both:
            gap = g[q] - h[q]
            rel = code in TOL
            size = abs(gap / h[q] * 100) if rel and h[q] else abs(gap)
            rows.append({"code": code, "quarter": q, "ukrstat": round(g[q], 2), "model": round(h[q], 2),
                         "gap": round(gap, 2), "gap_unit": "%" if rel else "п.п.",
                         "gap_size": round(size, 2), "ok": size <= (TOL[code] if rel else TOL_PP)})
        newer = g.index.difference(h.index)
        for q in newer[newer > (h.index.max() if len(h) else "")]:
            rows.append({"code": code, "quarter": q, "ukrstat": round(g[q], 2), "model": None, "gap": None,
                         "gap_unit": "", "gap_size": None, "ok": None})
    return pd.DataFrame(rows)
