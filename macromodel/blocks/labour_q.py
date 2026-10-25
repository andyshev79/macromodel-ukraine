"""Block B4 by quarter: wages, labour force, unemployment and employment with seasonality.

Ukraine's labour market is seasonal: farm work lifts employment in Q2-Q3 and cuts it in Q4-Q1;
wages peak in Q4 (December bonuses, the "13th salary", year-end premiums) and dip in Q1;
summer leave pay lifts Q3. Minimum wage and public pay are raised on set dates, several times
a year in some years. So the equations run on quarterly y/y rates: a quarter is compared with
the same quarter a year before, and its level is that quarter × (1 + growth). The seasonal
pattern of the last fact year carries into the forecast; the factors below show it and set the
quarterly labour force and unemployment from the annual estimates (the survey stopped in 2021).

Wage (OLS 2012Q1-2025Q4 without 2022Q1-2023Q1, Newey-West errors):
  wage y/y = const + a × CPI of the last four quarters + b × minimum wage y/y
             + p × central budget wage bill y/y + u × y/y change in unemployment
Okun by quarter: y/y change in unemployment = const + b × real GDP y/y (2012-2025, with the NBU
annual estimates of unemployment for 2022-2025 in all their quarters).

December premium: Gosstat counts pay accrued in the month, so December carries annual bonuses,
the "13th salary" and aid on top of the usual wage. Its size changes from year to year (11-21%
of the November-January trend), and the y/y forecast would repeat last year's size. The premium
is measured from monthly wages (data/external/wage_m.csv) and set by scenario for 2026-2028; the
Q4 level moves by a third of the change, as December is one month of three.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from macromodel import quarterly as Q
from macromodel.blocks.labour import UNEMP_EST

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
FIRST, LAST = "2012Q1", "2025Q4"
SEAS_FIRST, SEAS_LAST = "2011Q1", "2021Q4"  # labour force survey
WAGE_REGS = ["CPI_L", "MINW", "PUB", "DU"]
COEF_FIRST = 128  # COEFS rows after the CPI blocks (108-126)
METHOD = "оценка МНК 2012–2025, квартальные г/г без 2022Q1–2023Q1, ошибки Ньюи–Уэста"
NOTES = {
    "const": "Тренд: рост производительности и догоняющий рост к соседям",
    "CPI_L": "ИПЦ г/г, среднее за четыре прошлых квартала: индексация по прошлой инфляции",
    "MINW": "Рост минимальной зарплаты г/г квартала (средняя за квартал по датам повышений; удвоение 2017 видно)",
    "PUB": "Рост фонда оплаты труда госбюджета г/г квартала (с 2022 в основном довольствие военных)",
    "DU": "Изменение безработицы г/г, п.п.: дефицит работников поднимает зарплаты. 2022–2025 — оценки НБУ",
}


def yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(4) - 1) * 100


def min_wage_q() -> pd.Series:
    """Average minimum wage by quarter from the dates of each change (data/external/min_wage_m.csv)."""
    m = pd.read_csv(EXT / "min_wage_m.csv")
    s = pd.Series(m["MINW_UAH"].values, index=pd.PeriodIndex(m["from"], freq="M"))
    s = s.reindex(pd.period_range(s.index[0], "2026-12", freq="M")).ffill()
    q = s.groupby(s.index.asfreq("Q")).mean()
    q.index = q.index.astype(str)
    return q


def unemployment() -> pd.Series:
    """Survey unemployment to 2021, NBU annual estimates for 2022-2025 in every quarter."""
    u = Q.long_quarterly()["UNEMP"].copy()
    for y, v in UNEMP_EST.items():
        for q in "1234":
            u[f"{y}Q{q}"] = v
    return u


def wage_m() -> pd.Series:
    """Average monthly wage, UAH (Gosstat via MacroStat, 2010-2013 rows fixed); 2022-2023 missing."""
    m = pd.read_csv(EXT / "wage_m.csv")
    s = pd.Series(m["WAGE_UAH"].values, index=pd.PeriodIndex(m["month"], freq="M"))
    return s.reindex(pd.period_range(s.index[0], s.index[-1], freq="M"))


def dec_premium() -> pd.Series:
    """December wage over the trend through November and January (geometric mean), % by year."""
    s = wage_m()
    p = {y: (s[pd.Period(f"{y}-12", "M")] / np.sqrt(s[pd.Period(f"{y}-11", "M")] * s[pd.Period(f"{y + 1}-01", "M")]) - 1) * 100
         for y in range(s.index[0].year, s.index[-1].year) if pd.Period(f"{y + 1}-01", "M") in s.index}
    return pd.Series(p).dropna()


def dec_drivers() -> dict:
    """Averages by period and the slope on nominal GDP growth (OLS on years with both)."""
    p = dec_premium()
    d = Q.long_quarterly()
    gn = d["GDP_NOM"].groupby(d.index.str[:4]).sum(min_count=4)
    gn.index = gn.index.astype(int)
    g = (gn / gn.shift() - 1) * 100
    df = pd.concat([p.rename("P"), g.rename("G")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    fit = Q.ols_nw(df["P"], df[["G"]])
    span = lambda a, b: float(p.loc[a:b].mean())
    return {"pre": span(2006, 2015), "mid": span(2016, 2021), "war": span(2024, 2030), "last": float(p.iloc[-1]),
            "last_year": int(p.index[-1]), "fit": fit, "n": len(df)}


def data() -> pd.DataFrame:
    d = Q.long_quarterly()
    u = unemployment()
    x = pd.DataFrame({"WAGE": yoy(d["WAGE_NOM"]), "CPI": d["CPI_YOY"], "MINW": yoy(min_wage_q().reindex(d.index)),
                      "PUB": yoy(d["CB_EXP_WAGES"]), "U": u, "DU": u - u.shift(4), "GDP": yoy(d["GDP_REAL"])})
    x["CPI_L"] = x["CPI"].shift().rolling(4).mean()
    return x


def wage_estimate(first=FIRST, last=LAST) -> dict:
    df = data()[["WAGE"] + WAGE_REGS].loc[first:last].drop(index=Q.WAR, errors="ignore").dropna()
    return {**Q.ols_nw(df["WAGE"], df[WAGE_REGS]), "n": len(df)}


def okun_estimate(first=FIRST, last=LAST) -> dict:
    df = data()[["DU", "GDP"]].loc[first:last].drop(index=Q.WAR, errors="ignore").dropna()
    return {**Q.ols_nw(df["DU"], df[["GDP"]]), "n": len(df)}


def ratio_to_trend(s: pd.Series) -> pd.Series:
    """Quarter / centred 2×4 moving average: the seasonal part without growth within the year."""
    ma = s.rolling(4).mean().rolling(2).mean().shift(-2)
    return s / ma


def seasonal() -> dict:
    """Seasonal factors by quarter 1-4: multiplicative for levels, additive (п.п.) for unemployment."""
    d = Q.long_quarterly()
    lf = d["EMPL"] / (1 - d["UNEMP"] / 100)
    span = lambda s, a=SEAS_FIRST, b=SEAS_LAST: s.loc[a:b]
    by_q = lambda r: r.groupby(r.index.str[-1]).mean()
    norm = lambda f: f / f.mean()
    w = ratio_to_trend(d["WAGE_NOM"]).loc["2011Q1":"2025Q4"].drop(index=[f"2022Q{q}" for q in "1234"], errors="ignore")
    u = span(d["UNEMP"])
    return {
        "LF": norm(by_q(span(ratio_to_trend(lf)).dropna())),
        "EMPL": norm(by_q(span(ratio_to_trend(d["EMPL"])).dropna())),
        "U": by_q(u - u.groupby(u.index.str[:4]).transform("mean")),
        "WAGE": norm(by_q(w.dropna())),
    }


def retro(years=("2023", "2024", "2025")) -> pd.DataFrame:
    """Out of sample: fit on quarters before year t, predict its four quarters with actual drivers,
    compare the year-average wage growth with the fact."""
    x, d = data(), Q.long_quarterly()
    rows = []
    for y in years:
        r = wage_estimate(last=f"{int(y) - 1}Q4")
        qs = [f"{y}Q{q}" for q in "1234"]
        g = r["coef"]["const"] + sum(r["coef"][k] * x.loc[qs, k] for k in WAGE_REGS)
        prev = d["WAGE_NOM"].loc[[f"{int(y) - 1}Q{q}" for q in "1234"]].values
        model = (prev * (1 + g.values / 100)).mean() / prev.mean() * 100 - 100
        fact = d["WAGE_NOM"].loc[qs].mean() / prev.mean() * 100 - 100
        rows.append({"year": y, "model": model, "fact": fact, "error": model - fact})
    return pd.DataFrame(rows).set_index("year")


def coef_rows() -> list[dict]:
    w, o, s = wage_estimate(), okun_estimate(), seasonal()
    rows = [{"eq": "WQ", "var": k, "coef": w["coef"][k], "se": w["se"][k], "r2": w["r2"], "n": w["n"],
             "period": "2012–2025", "method": METHOD, "note": NOTES[k]} for k in ["const"] + WAGE_REGS]
    rows += [{"eq": "UQ", "var": k, "coef": o["coef"][k], "se": o["se"][k], "r2": o["r2"], "n": o["n"],
              "period": "2012–2025", "method": METHOD,
              "note": {"const": "Закон Оукена по кварталам: константа (дефицит кадров 2023–2025 тянет вниз)",
                       "GDP": "Изменение безработицы г/г на 1 п.п. роста реального ВВП г/г"}[k]} for k in ["const", "GDP"]]
    seas_note = {
        "LF": "Сезонность рабочей силы (агросектор: летом больше), квартал / скользящее среднее, ОРС 2011–2021",
        "U": "Сезонность безработицы, п.п. к среднему за год (зимой выше), ОРС 2011–2021",
        "WAGE": "Сезонность зарплаты: 4 кв. — премии и «13-я зарплата» в декабре, 3 кв. — отпускные; 2011–2025 без 2022. "
                "Для чтения: прогноз г/г к тому же кварталу сохраняет сезонность сам",
    }
    for k in ["LF", "U", "WAGE"]:
        rows += [{"eq": f"SEAS_{k}", "var": f"Q{q}", "coef": float(s[k][q]), "se": None, "r2": None, "n": 0,
                  "period": "2011–2021" if k != "WAGE" else "2011–2025", "method": "расчёт по данным", "note": seas_note[k]}
                 for q in "1234"]
    dd = dec_drivers()
    f = dd["fit"]
    dec_note = "Декабрьская премия: декабрь к тренду ноябрь–январь, %, помесячная зарплата Госстата"
    rows += [{"eq": "DEC", "var": v, "coef": c, "se": None, "r2": None, "n": 0, "period": per, "method": "расчёт по данным",
              "note": f"{dec_note}; {txt}"} for v, c, per, txt in [
        ("AVG_PRE", dd["pre"], "2006–2015", "до реформы ЕСВ (2016) и войны"),
        ("AVG_MID", dd["mid"], "2016–2021", "после снижения ЕСВ до 22%: премии легализованы"),
        ("AVG_WAR", dd["war"], "2024–2025", "война: премии меньше; 2022–2023 помесячных данных нет")]]
    rows.append({"eq": "DEC", "var": "GDPN", "coef": f["coef"]["G"], "se": f["se"]["G"], "r2": f["r2"], "n": dd["n"],
                 "period": "2011–2025", "method": "МНК, ошибки Ньюи–Уэста",
                 "note": f"{dec_note}; на 1 п.п. роста номинального ВВП (прибыли → премии). Слабая связь, для сценариев"})
    return rows


if __name__ == "__main__":
    for name, r in [("wage", wage_estimate()), ("okun", okun_estimate())]:
        print(name, {k: (round(v, 3), round(v / r["se"][k], 1)) for k, v in r["coef"].items()}, "R2", round(r["r2"], 2), "n", r["n"])
    print({k: v.round(3).to_dict() for k, v in seasonal().items()})
    print(retro().round(1))
    print(dec_premium().round(1).to_dict())
    dd = dec_drivers()
    print({k: v for k, v in dd.items() if k != "fit"}, dd["fit"]["coef"], dd["fit"]["r2"])
