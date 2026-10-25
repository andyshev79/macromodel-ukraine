"""Block B6: state budget and its financing gap.

Ratios are calibrated on 2025, the last full year of war-time budget: own
revenue and non-defence spending as % of GDP, the grant share of external
financing and net domestic financing as % of GDP. Defence spending comes from
SCENARIOS, so the budget follows the war path.

Debt is split into FX (external, kept in USD and valued at the forecast year-end
rate) and hryvnia parts. MinFin's payment schedule is in hryvnia at the rate of
the day it was made (FX_SCHED), so external repayments are rescaled to the
forecast rate.
"""
import pandas as pd

from macromodel.blocks.real_sector import HIST, quarterly

BASE_YEAR = "2025"
FX_SCHED_Q = "2026Q1"  # MinFin schedule in MacroStat: 2026 plan, monthly from March 2026


def annual() -> pd.DataFrame:
    d = quarterly()
    year = d.index.str[:4]
    s = d[["BUDGET_REV", "BUDGET_EXP", "BUDGET_DEFENCE", "BUDGET_DEF", "GDP_NOM", "GRANTS_USD", "FIN_RECEIVED_USD"]]
    a = s.groupby(year).sum(min_count=4) / 1000  # bn UAH; USD columns become bn USD
    a["FX"] = d["FX_AVG"].groupby(year).mean()
    a["DEBT"] = d["DEBT_UAH"].groupby(year).last() / 1000
    a["EXT_DEBT_UAH"] = d["EXT_DEBT_GG_USD"].groupby(year).last() * d["FX_EOP"].groupby(year).last() / 1000
    sched = pd.read_csv(HIST / "debt_schedule_y.csv", index_col=0)
    sched.index = sched.index.astype(str)
    a["DEBT_PAY_EXT"] = sched["external"]
    a["DEBT_REPAY_EXT"] = sched["external_repayment"]  # principal only: interest is in spending
    a["EXT_DEBT_USD"] = d["EXT_DEBT_GG_USD"].groupby(year).last() / 1000  # bn USD
    a["FX_EOP"] = d["FX_EOP"].groupby(year).last()
    a["GRANTS"] = a["GRANTS_USD"] * a["FX"]
    a["REV_OWN"] = a["BUDGET_REV"] - a["GRANTS"]
    return a


def calibration(year: str = BASE_YEAR) -> dict:
    a = annual().loc[year]
    gdp = a["GDP_NOM"]
    ext_loans = (a["FIN_RECEIVED_USD"] - a["GRANTS_USD"]) * a["FX"]
    dom = a["BUDGET_EXP"] - a["REV_OWN"] + a["DEBT_REPAY_EXT"] - a["GRANTS"] - ext_loans
    return {
        ("REV", "OWN"): round(a["REV_OWN"] / gdp * 100, 1),
        ("EXP", "OTHER"): round((a["BUDGET_EXP"] - a["BUDGET_DEFENCE"]) / gdp * 100, 1),
        ("FIN", "GRANT_SHARE"): round(a["GRANTS_USD"] / a["FIN_RECEIVED_USD"], 2),
        ("FIN", "DOM"): round(dom / gdp * 100, 1),
        ("DEBT", "FX_SCHED"): round(float(quarterly().loc[FX_SCHED_Q, "FX_AVG"]), 2),
    }


NOTES = {
    ("REV", "OWN"): "Собственные доходы (без грантов), % ВВП, уровень 2025: эластичность налогов к ВВП 1",
    ("EXP", "OTHER"): "Расходы кроме обороны (вкл. проценты и соцрасходы), % ВВП, уровень 2025",
    ("FIN", "GRANT_SHARE"): "Доля грантов во внешнем финансировании, 2025",
    ("FIN", "DOM"): "Чистое внутреннее финансирование (ОВГЗ, НБУ), % ВВП: остаток 2025",
    ("DEBT", "FX_SCHED"): "Курс, по которому Минфин посчитал график платежей в гривне (график 2026 года, средний курс 2026Q1). "
                          "Погашения пересчитываются: график × прогнозный курс / этот курс",
}


def coef_table() -> list[dict]:
    return [{"eq": eq, "var": var, "coef": float(v), "note": NOTES[(eq, var)]} for (eq, var), v in calibration().items()]


if __name__ == "__main__":
    print(annual().round(0).to_string())
    print(calibration())
