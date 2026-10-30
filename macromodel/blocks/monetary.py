"""Block B7: NBU rate, bank rates, loans, deposits and liquidity (annual, UAH).

The NBU rate follows a Taylor-type rule (since 2026-10-30): half of last year's rate plus
half of (neutral real rate + end-of-year CPI + 0.5 x (end-of-year CPI - 5% target)), so the
long-run response to inflation is 1.5 > 1, plus a calibrated premium when reserves fall below
three months of imports. The OLS rule on average CPI (2016-2025) reacted 0.87 < 1 and gave a
rate below inflation in high-inflation years; it stays in estimate() for MODEL_QUALITY. Loan and deposit rates follow the NBU rate. Hryvnia loans grow with nominal
GDP and fall with the real loan rate. Hryvnia deposits keep their 2025 ratio to
nominal GDP. Liquidity (NBU certificates of deposit) absorbs about half of the
deposit growth that banks do not lend out.

Transmission: last year's real NBU rate above its neutral level slows household
consumption, investment and construction and lowers inflation this year. The one-year
lag follows the usual transmission delay and keeps the sheet free of circular references
(the rate rule reads this year's CPI).
"""
import pandas as pd

from macromodel.blocks.real_sector import HIST, ols, quarterly

EQUATIONS = {"RATE": ["CPI", "RATE_L"], "LOAN": ["RATE_AVG"], "DEP": ["RATE_AVG"], "LOANS_G": ["GDPN_G", "REAL"]}

CALIBRATED = {
    ("RATE", "RHO"): (0.5, "Сглаживание: вес ставки прошлого года. Проверка 2016–2025: ошибка 3,3 п.п. (0,3 — 4,1 п.п.); "
                           "прогноз НБУ 29.10.2026 (IV.27 14,6, IV.28 11,7 при ИПЦ 7,3 и 5) правило даёт на 0,6–0,7 п.п. ниже"),
    ("RATE", "PHI"): (0.5, "Реакция на отклонение ИПЦ на конец года от цели, сверх 1:1 (правило Тейлора). Итоговая реакция 1,5 > 1: "
                           "реальная ставка растёт с инфляцией"),
    ("RATE", "TARGET"): (5.0, "Цель НБУ по инфляции, % (5% ± 1 п.п.)"),
    ("RATE", "RES"): (2.0, "Надбавка к ставке, п.п. на каждый месяц импорта ниже порога резервов (2014–2015, 2022: НБУ поднимал ставку при угрозе резервам)"),
    ("RATE", "RES_MAX"): (10.0, "Предел надбавки за резервы, п.п."),
    ("RATE", "MONTHS"): (3.0, "Порог резервов для ставки, месяцев импорта"),
    ("DEPS", "GDP"): (None, "Депозиты в гривне, % номинального ВВП: уровень 2025 (эластичность к ВВП 1; регрессия на 2016–2025 не находит связи)"),
    ("LIQ", "SHARE"): (0.48, "Доля прироста (депозиты − кредиты), уходящая в депозитные сертификаты НБУ: сумма 2016–2025"),
}

COEF_ROWS = [("RATE", "RHO"), ("RATE", "PHI"), ("RATE", "TARGET"), ("RATE", "RES"), ("RATE", "RES_MAX"),
             ("RATE", "MONTHS"), ("LOAN", "const"), ("LOAN", "RATE_AVG"), ("DEP", "const"), ("DEP", "RATE_AVG"),
             ("LOANS_G", "const"), ("LOANS_G", "GDPN_G"), ("LOANS_G", "REAL"), ("DEPS", "GDP"), ("LIQ", "SHARE")]


TRANSMISSION = {
    "NEUTRAL": (3.0, "Нейтральная реальная учётная ставка, %: допущение (для развивающихся экономик обычно 2–4%); "
                     "её же берёт правило ставки B7 (RATE_M)"),
    "HH": (-0.2, "Потребление домохозяйств, п.п. роста на 1 п.п. жёсткости прошлого года. Оценка 2016–2025 дала +0,17 (неверный знак, война); "
                 "взято по мировому опыту 0,1–0,5"),
    "GFCF": (-0.7, "Инвестиции (ВНОК), п.п. на 1 п.п. жёсткости. Оценка МНК 2016–2025: −0,71 (ст. ошибка 0,66); мировой опыт 0,5–1,5"),
    "CONSTR": (-0.5, "Строительство, п.п. на 1 п.п. жёсткости: слабее инвестиций, часть строек — оборона и восстановление за счёт бюджета"),
    "CPI": (-0.25, "ИПЦ, п.п. на 1 п.п. жёсткости прошлого года (канал спроса). Оценка 2016–2025: +0,02 (ст. ошибка 0,23, связи не видно); "
                   "мировой опыт 0,1–0,4"),
}


def transmission_table() -> list[dict]:
    return [{"eq": "TR", "var": k, "coef": v, "note": n} for k, (v, n) in TRANSMISSION.items()]


def credit_q() -> pd.DataFrame:
    """Quarter-end bank loans and deposits, UAH million (macromodel.loaders.nbu_dk)."""
    return pd.read_csv(HIST / "credit_q.csv", index_col=0).T


def annual() -> pd.DataFrame:
    d = quarterly().join(credit_q())
    y = d.index.str[:4]
    a = pd.DataFrame({
        "RATE": d["NBU_RATE"].groupby(y).last(),
        "RATE_AVG": d["NBU_RATE"].groupby(y).mean(),
        "LOAN": d["LOAN_RATE"].groupby(y).mean(),
        "DEP": d["DEP_RATE"].groupby(y).mean(),
        "CPI": d["CPI_YOY"].groupby(y).mean(),
        "GDPN": d["GDP_NOM"].groupby(y).sum(min_count=4),
        "LOANS": d["LOANS_UAH"].groupby(y).last(),
        "DEPS": d["DEP_UAH"].groupby(y).last(),
        "CD": d["NBU_CD"].groupby(y).last(),
    })
    a["RATE_L"] = a["RATE"].shift()
    a["GDPN_G"] = a["GDPN"].pct_change(fill_method=None) * 100
    a["LOANS_G"] = a["LOANS"].pct_change(fill_method=None) * 100
    a["REAL"] = a["LOAN"] - a["CPI"]
    a["DEPS_GDP"] = a["DEPS"] / a["GDPN"] * 100
    return a


def estimate(first="2016", last="2025") -> dict:
    a = annual()
    return {y: ols(a.loc[first:last, y], a.loc[first:last, regs]) for y, regs in EQUATIONS.items()}


def coef_table() -> list[dict]:
    from macromodel import quarterly

    est = estimate()
    rows = []
    for eq, var in COEF_ROWS:
        if eq in quarterly.USED:
            rows += quarterly.coef_rows(eq, [(eq, var)])
        elif (eq, var) in CALIBRATED:
            v, note = CALIBRATED[(eq, var)]
            if (eq, var) == ("DEPS", "GDP"):
                v = round(float(annual().loc["2025", "DEPS_GDP"]), 1)
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
