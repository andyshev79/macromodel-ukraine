"""Block B4, wages: nominal wage growth from its factors instead of 'real wage + last year's CPI'.

Annual equation, OLS 2016–2025 without 2022 (one-off: wage fund of the army, collapse of GDP):
  wage growth = const + a × CPI last year + b × minimum wage growth + p × growth of the
                central budget wage bill + u × change in unemployment
The budget wage bill is mostly military pay since 2022 (pay of soldiers is booked as
'оплата праці'), so in the forecast it is built from two budget targets:
military pay per soldier (share MIL_CB) and civilian public pay growth (the rest); the number
of soldiers works through the labour force (mobilisation), not through pay.
Unemployment: 2022–2025 are NBU estimates (labour.UNEMP_EST). In the sheet the change in
unemployment is the part known before this year's GDP (supply from migration and
mobilisation, Okun on last year's GDP), so B1–B4 have no circular reference.
De-shadowing adds to recorded wages one for one but is not new income: B3 and B2 take wages
without it. Military pay enters household income with its share MIL_HH (B2).
"""
from pathlib import Path

import pandas as pd

from macromodel import quarterly as Q
from macromodel.blocks.labour import annual as labour_annual
from macromodel.blocks.real_sector import ols

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
FIRST, LAST, SKIP = "2016", "2025", ["2022"]
REGS = ["CPI_L", "MINW", "PUB", "DU"]
COEF_FIRST = 98  # after B3 devaluation threshold (95-96)
METHOD = "оценка МНК 2016–2025, годовые, без 2022"
NOTES = {
    "const": "Тренд: рост производительности и догоняющий рост к соседям",
    "CPI_L": "ИПЦ прошлого года (индексация по прошлой инфляции): связь слабая, спирали зарплата–цены нет",
    "MINW": "Рост минимальной зарплаты (средняя за год; удвоение 2017 видно в данных)",
    "PUB": "Рост фонда оплаты труда госбюджета (с 2022 в основном довольствие военных): бюджетники в средней "
           "зарплате и перетягивание работников",
    "DU": "Изменение безработицы, п.п.: дефицит работников (мобилизация, отъезд) поднимает зарплаты. "
          "Безработица 2022–2025 — оценки НБУ",
}
CALIBRATED = {
    "MIL_CB": (0.7, "Доля довольствия военных в фонде оплаты труда госбюджета 2025: 1,88 трлн, из них военные ≈ 1,3 трлн. "
                    "Оценка Claude по росту фонда с 2021 (0,52 трлн), сверить по функциональной классификации (0200). "
                    "В прогнозе: военные — рост довольствия на одного, гражданские — рост оплаты бюджетников"),
    "MIL_HH": (0.3, "Доля довольствия военных в доходах от труда домохозяйств 2025: ≈ 1,3 трлн из 4,3 трлн оплаты "
                    "труда по СНС. Оценка Claude; идёт в B2 (потребление)"),
}
ORDER = ["const"] + REGS + list(CALIBRATED)
ROW = {k: COEF_FIRST + i for i, k in enumerate(ORDER)}


def min_wage() -> pd.Series:
    m = pd.read_csv(EXT / "min_wage_y.csv", index_col=0)["MINW_UAH"]
    m.index = m.index.astype(str)
    return m


def annual() -> pd.DataFrame:
    d = Q.long_quarterly()
    y = d.index.str[:4]
    a = pd.DataFrame({
        "WAGE": d["WAGE_NOM"].groupby(y).mean().pct_change() * 100,
        "CPI": d["CPI_YOY"].groupby(y).mean(),
        "PUB": d["CB_EXP_WAGES"].groupby(y).sum(min_count=4).pct_change() * 100,
    })
    a["MINW"] = min_wage().pct_change().mul(100).reindex(a.index)
    a["CPI_L"] = a["CPI"].shift()
    a["DU"] = labour_annual()["DU"].reindex(a.index)
    return a


def estimate() -> dict:
    df = annual()[["WAGE"] + REGS].loc[FIRST:LAST].drop(index=SKIP).dropna()
    return ols(df["WAGE"], df[REGS])


def coef_table() -> list[dict]:
    r = estimate()
    rows = [{"var": k, "coef": round(float(r["coef"][k]), 2), "se": round(float(r["se"][k]), 2),
             "r2": round(float(r["r2"]), 2), "n": r["n"], "method": METHOD, "note": NOTES[k]} for k in ["const"] + REGS]
    rows += [{"var": k, "coef": v, "se": None, "r2": None, "n": 0, "method": "калибровка", "note": n}
             for k, (v, n) in CALIBRATED.items()]
    return rows


if __name__ == "__main__":
    a = annual()
    print(a.loc["2012":].round(1).to_string())
    r = estimate()
    print({k: (round(v, 2), round(v / r["se"][k], 1)) for k, v in r["coef"].items()}, "R2", round(r["r2"], 2), "n", r["n"])
