"""Block B9: construction by kind of work, with financing and capacity checks (2026-10-25).

Construction grows from three blocks: civil (housing and commercial, from household consumption),
infrastructure and reconstruction (scenario points of reconstruction, SCENARIOS row 124) and
fortifications (real defence spending). The construction output index (Ukrstat, quarterly from 2011)
gives the link to GVA_F. Since 2026-10-26 the Ukrstat index by kind of construction (buildings: residential
and non-residential; civil engineering works), monthly from 2015, gives the civil equation (buildings index)
and the block weights; only the split of engineering works into infrastructure and fortifications is
Claude's estimate.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from macromodel import quarterly as Q

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
COEF_FIRST = 185  # after B1 manufacturing rows 172-184
YEAR = "2025"

W_YEARS = ("2023", "2025")  # weights of kinds from the post-invasion structure
CIVIL_SAMPLE = ("2015Q1", "2021Q4")  # buildings equation on pre-war years: the 2023-25 rebound is a base effect
FORT_W = 0.15  # fortifications, share of all construction

CALIBRATED = {
    ("W", "FORT"): (FORT_W, "Вес фортификаций в строительстве. Оценка Claude: решения Кабмина о фортификациях — "
                            "порядка 30–40 млрд грн в год при объёме строительства 258 млрд грн в 2025"),
    ("LAB", "BASE"): (400.0, "Занятые в строительстве 2025, тыс. (включая неформальных). Оценка Claude: ОРС после 2021 не публикуется"),
    ("LAB", "PROD"): (2.0, "Рост производительности в строительстве, % в год. Оценка Claude"),
    ("LAB", "DEMOB"): (0.15, "Доля демобилизованных, идущих в строительство. Оценка Claude: до войны строительство — около 5% занятых, "
                             "но среди мужчин призывного возраста доля выше"),
    ("LAB", "NAT"): (1.0, "Естественный приток рабочих (миграция, переобучение), % занятых в год. Оценка Claude"),
}


KINDS = {"TOT": "Всё строительство", "BLD": "Здания", "RES": "Жилые здания", "NRES": "Нежилые здания",
         "ENG": "Инженерные сооружения"}


def kinds() -> pd.DataFrame:
    """Construction output index by kind (Ukrstat), monthly from 2015: <KIND>_yoy, _ytd, _mom, %."""
    k = pd.read_csv(EXT / "construction_kind_m.csv", index_col="month").drop(columns="source")
    k.index = pd.PeriodIndex(k.index, freq="M")
    return k


def area() -> pd.DataFrame:
    """Floor area put into service (_DONE) and at the start of construction (_START), m², cumulative from January."""
    return pd.read_csv(EXT / "housing_area_q.csv", index_col="quarter").drop(columns="source")


def weights() -> dict:
    """Shares of residential, non-residential and engineering works in the total index: least squares of the
    monthly total y/y on the three kinds with weights summing to one, pooled over W_YEARS."""
    k = kinds()
    k = k[(k.index.year >= int(W_YEARS[0])) & (k.index.year <= int(W_YEARS[1]))]
    y = k["TOT_yoy"] - k["ENG_yoy"]
    X = np.c_[k["RES_yoy"] - k["ENG_yoy"], k["NRES_yoy"] - k["ENG_yoy"]]
    w = np.linalg.lstsq(X, y.values, rcond=None)[0]
    return {"RES": float(w[0]), "NRES": float(w[1]), "ENG": float(1 - w.sum())}


def data():
    d = Q.long_quarterly()
    q = Q.data()
    q["CONSTR"] = d["CONSTR_YOY"]
    q["GVA_F"] = d["GVA_F_YOY"]
    k = kinds()
    b = k["BLD_yoy"].groupby(k.index.asfreq("Q")).mean() - 100
    q["BLD"] = b.set_axis(b.index.astype(str))
    return q, d


def estimate() -> dict:
    q, _ = data()
    out = {}
    for name, y, regs, per in [("CIVIL", "BLD", ["HH"], CIVIL_SAMPLE), ("LINK", "GVA_F", ["CONSTR"], None)]:
        s = Q.sample(q, y, regs)
        s = s.loc[per[0]:per[1]] if per else s
        out[name] = Q.ols_nw(s[y], s[regs]) | {"first": s.index[0], "last": s.index[-1], "regs": regs}
    return out


def history() -> dict:
    """Annual construction growth 2013-2025 without war years; base-year GFCF in USD for the financing check."""
    q, d = data()
    c = q["CONSTR"].loc["2013Q1":Q.LAST].drop(index=Q.WAR, errors="ignore")
    c = c.groupby(c.index.str[:4]).mean()
    y = d.loc[f"{YEAR}Q1":f"{YEAR}Q4"]
    return {"lo": float(np.percentile(c, 10)), "hi": float(np.percentile(c, 90)), "years": f"{c.index[0]}–{c.index[-1]}",
            "gfcf_usd": float(y["GDPE_GFCF_NOM"].sum() / y["FX_AVG"].mean() / 1000),  # bn USD
            "constr_25": float(q["CONSTR"].loc[f"{YEAR}Q1":f"{YEAR}Q4"].mean()),
            "gva_f_25": float(q["GVA_F"].loc[f"{YEAR}Q1":f"{YEAR}Q4"].mean())}


MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]


def monthly() -> pd.DataFrame:
    """Construction output by month (MacroStat SectorIndexes M): index % y/y and volume of work, UAH mn."""
    m = pd.read_csv(EXT / "construction_m.csv", index_col="month")
    m.index = pd.PeriodIndex(m.index, freq="M")
    return m


def fact_ytd() -> dict:
    """Growth from January to the last month with data (Ukrstat cumulative index)."""
    m = monthly().dropna(subset=["ytd"])
    last = m.index[-1]
    return {"year": last.year, "months": last.month, "last": MONTHS[last.month - 1], "yoy": float(m["ytd"].iloc[-1] - 100)}


def kind_facts() -> dict:
    """Growth by kind, % y/y: full years 2023-2025 (December, from January) and the current year to the last month."""
    k = kinds()
    last = k.dropna(subset=["TOT_ytd"]).index[-1]
    out = {}
    for kind in KINDS:
        s = k[f"{kind}_ytd"]
        out[kind] = {str(y): float(s[pd.Period(f"{y}-12", "M")] - 100) for y in range(2023, last.year)}
        out[kind][str(last.year)] = float(s[last] - 100)
    return {"facts": out, "year": last.year, "months": last.month, "last": MONTHS[last.month - 1]}


def area_growth() -> dict:
    """Floor area growth, % y/y: full years 2023-2025 (Q4, from January) and the current year to the last quarter."""
    a = area()
    last = a.dropna(subset=["RES_START"]).index[-1]
    yr, qn = int(last[:4]), int(last[-1])
    g = lambda col, y, n: float(a.loc[f"{y}Q{n}", col] / a.loc[f"{y - 1}Q{n}", col] * 100 - 100)
    out = {}
    for col in a.columns:
        out[col] = {str(y): g(col, y, 4) for y in range(2023, yr)} | {str(yr): g(col, yr, qn)}
    st = lambda y, n: a.loc[f"{y}Q{n}", ["RES_START", "NRES_START"]].sum()
    out["START"] = {str(y): float(st(y, 4) / st(y - 1, 4) * 100 - 100) for y in range(2023, yr)} | \
                   {str(yr): float(st(yr, qn) / st(yr - 1, qn) * 100 - 100)}
    return {"growth": out, "year": yr, "quarters": qn, "res_done": float(a.loc[f"{yr - 1}Q4", "RES_DONE"] / 1e6)}


def coef_rows() -> list[dict]:
    e = estimate()
    notes = {"CIVIL": "Индекс строительства зданий (жилые и нежилые, Госстат) от потребления домохозяйств, "
                      "довоенные годы: рост 2023–2025 — отскок после 2022",
             "LINK": "ВДС строительства от индекса строительной продукции"}
    rows = []
    for name, r in e.items():
        for v in ["const"] + r["regs"]:
            rows.append({"code": f"F_{name}_{v}", "eq": f"F_{name}", "var": v, "coef": round(float(r["coef"][v]), 2),
                         "se": round(float(r["se"][v]), 2), "period": f"{r['first'][:4]}–{r['last'][:4]}",
                         "method": "МНК квартальные, Newey–West, без 2022Q1–2023Q1", "r2": round(r["r2"], 2),
                         "note": notes[name] if v == "const" else ""})
    w = weights()
    for v, c, note in [("CIVIL", w["RES"] + w["NRES"], f"Вес зданий: жилые {w['RES']:.2f} + нежилые {w['NRES']:.2f}".replace(".", ",")),
                       ("INFRA", w["ENG"] - FORT_W, f"Вес инженерных сооружений {w['ENG']:.2f} без фортификаций: ".replace(".", ",") +
                                                    "дороги, энергетика, сети, восстановление")]:
        rows.append({"code": f"F_W_{v}", "eq": "F_W", "var": v, "coef": round(c, 2), "se": None,
                     "period": f"{W_YEARS[0]}–{W_YEARS[1]}", "method": "МНК по видам строительства, месячные г/г, сумма весов 1",
                     "r2": None, "note": note})
    for (g, v), (c, note) in CALIBRATED.items():
        rows.append({"code": f"F_{g}_{v}", "eq": f"F_{g}", "var": v, "coef": c, "se": None, "period": "",
                     "method": "калибровка", "r2": None, "note": note})
    return rows


ROW = {r["code"]: COEF_FIRST + i for i, r in enumerate(coef_rows())}
