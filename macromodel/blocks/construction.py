"""Block B9: construction by kind of work, with financing and capacity checks (2026-10-25).

Construction grows from three blocks: civil (housing and commercial, from household consumption),
infrastructure and reconstruction (scenario points of reconstruction, SCENARIOS row 124) and
fortifications (real defence spending). The construction output index (Ukrstat, quarterly from 2011)
gives the civil equation and the link to GVA_F. Block weights are Claude's estimates until Andrey adds
the Ukrstat split of construction output by kind of work.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from macromodel import quarterly as Q

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
COEF_FIRST = 185  # after B1 manufacturing rows 172-184
YEAR = "2025"

CALIBRATED = {
    ("W", "CIVIL"): (0.5, "Вес жилья и коммерческой недвижимости в строительстве. Оценка Claude до данных Госстата по видам работ"),
    ("W", "INFRA"): (0.3, "Вес инфраструктуры и восстановления (дороги, энергетика, социальные объекты). Оценка Claude"),
    ("W", "FORT"): (0.2, "Вес фортификаций и оборонного строительства. Оценка Claude"),
    ("LAB", "BASE"): (400.0, "Занятые в строительстве 2025, тыс. (включая неформальных). Оценка Claude: ОРС после 2021 не публикуется"),
    ("LAB", "PROD"): (2.0, "Рост производительности в строительстве, % в год. Оценка Claude"),
    ("LAB", "DEMOB"): (0.15, "Доля демобилизованных, идущих в строительство. Оценка Claude: до войны строительство — около 5% занятых, "
                             "но среди мужчин призывного возраста доля выше"),
    ("LAB", "NAT"): (1.0, "Естественный приток рабочих (миграция, переобучение), % занятых в год. Оценка Claude"),
}


def data():
    d = Q.long_quarterly()
    q = Q.data()
    q["CONSTR"] = d["CONSTR_YOY"]
    q["GVA_F"] = d["GVA_F_YOY"]
    return q, d


def estimate() -> dict:
    q, _ = data()
    out = {}
    for name, y, regs in [("CIVIL", "CONSTR", ["HH"]), ("LINK", "GVA_F", ["CONSTR"])]:
        s = Q.sample(q, y, regs)
        out[name] = Q.ols_nw(s[y], s[regs]) | {"first": s.index[0], "regs": regs}
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


def coef_rows() -> list[dict]:
    e = estimate()
    notes = {"CIVIL": "Индекс строительной продукции от потребления домохозяйств: жильё и коммерческая недвижимость",
             "LINK": "ВДС строительства от индекса строительной продукции"}
    rows = []
    for name, r in e.items():
        for v in ["const"] + r["regs"]:
            rows.append({"code": f"F_{name}_{v}", "eq": f"F_{name}", "var": v, "coef": round(float(r["coef"][v]), 2),
                         "se": round(float(r["se"][v]), 2), "period": f"{r['first'][:4]}–{Q.LAST[:4]}",
                         "method": "МНК квартальные, Newey–West, без 2022Q1–2023Q1", "r2": round(r["r2"], 2),
                         "note": notes[name] if v == "const" else ""})
    for (g, v), (c, note) in CALIBRATED.items():
        rows.append({"code": f"F_{g}_{v}", "eq": f"F_{g}", "var": v, "coef": c, "se": None, "period": "",
                     "method": "калибровка", "r2": None, "note": note})
    return rows


ROW = {r["code"]: COEF_FIRST + i for i, r in enumerate(coef_rows())}
