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
    ("O", "ADM_G"): (0.0, "Штат гражданского госуправления на прогнозе постоянен: 2021–2025 сокращался "
                          "(398 → 308 тыс.), в 2026 держится около 317 тыс."),
}

# Quarterly GVA_C (macromodel.quarterly): metallurgy enters the model through SHOCK_MET_C, not this fit
QUARTERLY_NOTES = {
    ("C", "const"): "Регрессия с выпуском металлургии (0,41) и потреблением; в модели металлургия идёт через "
                    "SHOCK_MET_C (оценка по текущей структуре)",
    ("C", "HH"): "Заменила ВВП еврозоны (в годовой оценке незначим, t 0,9): ретропрогноз 4,3 против 6,4",
}

COEF_ROWS = [
    ("A", "const"), ("A", "HARVEST"),
    ("B", "const"), ("B", "PORTS"), ("B", "CAP"),
    ("C", "const"), ("C", "HH"), ("C", "CAP"),
    ("D", "const"), ("D", "CAP"),
    ("F", "const"),
    ("G", "const"),
    ("H", "const"), ("H", "PORTS"),
    ("J", "const"),
    ("O", "DEF_SH"), ("O", "ADM_G"),
    ("OTHER", "const"),
]


ESV = 0.22  # единый социальный взнос сверх фонда довольствия


def defence_share(year="2025") -> float:
    """Share of defence in nominal GVA of section O: military pay fund with ESV / GVA_O.

    Non-market output is valued at cost (compensation + consumption of fixed capital); capital is left out.
    The military part of the budget wage bill is wages MIL_CB (COEFS row 103)."""
    from macromodel import quarterly as Q
    from macromodel.blocks.wages import CALIBRATED as W
    q = Q.long_quarterly()
    fund = q.loc[f"{year}Q1":f"{year}Q4", "CB_EXP_WAGES"].sum() * W["MIL_CB"][0] * (1 + ESV)
    return float(fund / quarterly().loc[f"{year}Q1":f"{year}Q4", "GVA_O_NOM"].sum())


def coef_table() -> list[dict]:
    from macromodel import quarterly
    from macromodel.blocks.demand import link_other_to_consumption

    est = estimate()
    est["OTHER"] = link_other_to_consumption()  # COEFS row 35 holds its HH slope
    rows = []
    for s, var in COEF_ROWS:
        if f"GVA_{s}" in quarterly.USED and (s, var) not in CALIBRATED:
            rows += [dict(r, note=QUARTERLY_NOTES.get((s, var), "")) for r in quarterly.coef_rows(f"GVA_{s}", [(f"GVA_{s}", var)])]
        elif (s, var) == ("O", "DEF_SH"):
            rows.append({"eq": "GVA_O", "var": var, "coef": round(defence_share(), 2), "se": None, "r2": None,
                         "n": None, "method": "расчёт 2025",
                         "note": f"Доля обороны в номинальной ВДС раздела O: фонд довольствия военных "
                                 f"× (1 + ЕСВ {ESV:.0%}) / ВДС O (Госстат)"})
        elif (s, var) in CALIBRATED:
            v, note = CALIBRATED[(s, var)]
            rows.append({"eq": f"GVA_{s}", "var": var, "coef": v, "se": None, "r2": None, "n": None,
                         "method": "калибровка", "note": note})
        else:
            r = est[s]
            rows.append({"eq": f"GVA_{s}", "var": var, "coef": round(r["coef"][var], 2),
                         "se": round(r["se"][var], 2), "r2": round(r["r2"], 2), "n": r["n"],
                         "method": "оценка МНК 2016–2025, годовые, дамми 2022", "note": ""})
    return rows


# Manufacturing by blocks (2026-10-25): metallurgy, food, machinery with defence industry, other.
# Weights come from the Ukrstat production indices (IND_C ~ sum of branch indices, 2023-2025 structure);
# each block has its own driver; GVA_C follows the bottom-up index, the old C equation stays as a top-down check.
C_BLOCKS = {"MET": "IND_C8", "FOOD": "IND_C1", "MACH": "IND_C9", "OTH": ("IND_C4", "IND_C5", "IND_C7")}
OPK_SH = 0.3  # defence industry in the machinery block: Claude estimate, Ukrstat indices do not show it
C_W_FIRST = "2023Q1"
# Cross-check against the sales structure (searched 2026-10-25): weights are value-added weights, not sales shares
C_W_CHECK = {
    "MET": ". Сверка: в реализации переработки 2024 металлургия (24) ≈ 12,5%, с металлоизделиями (25) ≈ 16%, но доля ДС "
           "в выпуске металлургии 2023 всего 7,8% (ДУ ИЭП НАНУ) против ~20% в среднем по переработке (оценка Claude) — по ДС вес ≈ 0,06–0,07, индекс это подтверждает",
    "FOOD": ". Сверка: в реализации переработки 2023 – I пол. 2024 пищепром 40% (Минагрополитики, табл. 3.4)",
    "MACH": ". Сверка: в реализации переработки I пол. 2024 машиностроение 12% (Минагрополитики); оружие и боеприпасы (25.4) "
            "входят в металлоизделия — 42% кода 25 в 2024",
}


def manuf_data() -> pd.DataFrame:
    from macromodel import quarterly as Q
    d = Q.long_quarterly()
    q = Q.data()
    for b, src in C_BLOCKS.items():
        q[b] = d[[f"{s}_YOY" for s in src]].mean(axis=1) if isinstance(src, tuple) else d[f"{src}_YOY"]
    q["IND_C"] = d["IND_C_YOY"]
    q["GFCF"] = d["GDPE_GFCF_YOY"]
    return q


def manuf_blocks() -> dict:
    from macromodel import quarterly as Q
    q = manuf_data()
    x = q[["IND_C", "FOOD", "MET", "MACH", "OTH"]].loc[C_W_FIRST:Q.LAST].dropna()
    rel = ["FOOD", "MET", "MACH"]
    b, *_ = np.linalg.lstsq((x[rel].values - x[["OTH"]].values), x["IND_C"].values - x["OTH"].values, rcond=None)
    w = dict(zip(rel, b)) | {"OTH": 1 - b.sum()}
    eqs = {"FOOD": ["HH"], "MACH": ["GFCF"], "OTH": ["HH"]}
    fits = {k: Q.ols_nw(s[k], s[r]) | {"first": s.index[0]} for k, r in eqs.items() for s in [Q.sample(q, k, r)]}
    s = Q.sample(q, "GVA_C", ["IND_C"])
    fits["LINK"] = Q.ols_nw(s["GVA_C"], s[["IND_C"]]) | {"first": s.index[0]}
    return {"w": w, "n_w": len(x), "fits": fits, "eqs": eqs | {"LINK": ["IND_C"]}}


def manuf_coef_rows() -> list[dict]:
    from macromodel import quarterly as Q
    m = manuf_blocks()
    names = {"MET": "металлургия", "FOOD": "пищепром", "MACH": "машиностроение", "OTH": "другое (химия, кокс, пластмассы)"}
    rows = [{"eq": "GVA_C_W", "var": k, "coef": round(float(v), 2), "se": None, "period": f"{C_W_FIRST[:4]}–{Q.LAST[:4]}",
             "method": "МНК квартальные, сумма весов 1", "r2": None,
             "note": f"Вес блока «{names[k]}» в индексе переработки Госстата (структура военных лет, {m['n_w']} кв.)"
                     + C_W_CHECK.get(k, "")}
            for k, v in m["w"].items()]
    notes = {"FOOD": "Пищепром от потребления домохозяйств (B2); урожай незначим",
             "MACH": "Гражданское машиностроение от ВНОК без акселератора (константа + ставка + восстановление): "
                     "иначе циклическая ссылка через ВВП",
             "OTH": "Химия, кокс, пластмассы от потребления домохозяйств (B2)",
             "LINK": "ВДС переработки от индекса производства (снизу вверх)"}
    for k, regs in m["eqs"].items():
        r = m["fits"][k]
        for v in ["const"] + regs:
            rows.append({"eq": f"GVA_C_{k}", "var": v, "coef": round(float(r["coef"][v]), 2), "se": round(float(r["se"][v]), 2),
                         "period": f"{r['first'][:4]}–{Q.LAST[:4]}", "method": "МНК квартальные, Newey–West, без 2022Q1–2023Q1",
                         "r2": round(r["r2"], 2), "note": notes[k] if v == "const" else ""})
    rows.append({"eq": "GVA_C_MACH", "var": "OPK_SH", "coef": OPK_SH, "se": None, "period": "", "method": "калибровка", "r2": None,
                 "note": "Доля ОПК в блоке машиностроения, растёт с реальными расходами на оборону. Оценка Claude: в индексе "
                         "Госстата ОПК не виден (связь машиностроения с расходами на оборону отрицательная)"})
    return rows
