"""Quality of the estimated equations: fit, out-of-sample errors and a naive benchmark.

For each equation estimated by OLS in the blocks, the same data is refitted here:
- in sample on 2016-2025 (what COEFS holds): fitted values, R², RMSE, smallest |t| of a driver;
- recursively out of sample for 2023-2025: estimate on 2016..t-1, predict year t;
- against the better of two simple rules on the same years: last year's value and the
  2016..t-1 average without 2022.
R² is also shown without 2022: the 2022 dummy fits that year exactly and inflates R².
"занижает"/"завышает": all three out-of-sample errors have one sign and the mean error
exceeds 3/4 of the mean absolute error.
Only estimated equations are checked; calibrated coefficients have no sample to test.
"""
import numpy as np
import pandas as pd

from macromodel.blocks import demand, external, labour, monetary, prices, real_sector, wages
from macromodel.blocks.real_sector import annual_growth, ols

FIRST, LAST = "2016", "2025"
TEST_YEARS = ["2023", "2024", "2025"]
DUMMIES = {"WAR22"}

# Equation id as on COEFS, block, description, dependent variable unit
META = {
    "GVA_A": ("B1", "Сельское хозяйство: рост ВДС от урожая", "% г/г"),
    "GVA_B": ("B1", "Добыча: рост ВДС от портов", "% г/г"),
    "GVA_C": ("B1", "Переработка: рост ВДС от ВВП еврозоны", "% г/г"),
    "GVA_G": ("B1", "Торговля: средний рост", "% г/г"),
    "GVA_H": ("B1", "Транспорт: рост ВДС от портов", "% г/г"),
    "GVA_O": ("B1", "Госуправление и оборона: средний рост", "% г/г"),
    "GVA_OTHER": ("B1", "Прочие отрасли и налоги: от потребления домохозяйств", "% г/г"),
    "GDPE_HH": ("B2", "Потребление домохозяйств: от реальной зарплаты", "% г/г"),
    "GDPE_GOV": ("B2", "Госпотребление: от реальных оборонных расходов", "% г/г"),
    "GDPE_EXP": ("B2", "Реальный экспорт: от портов", "% г/г"),
    "GDPE_IMP": ("B2", "Реальный импорт: от внутреннего спроса", "% г/г"),
    "CPI": ("B3", "ИПЦ (среднегодовой): от курса и зарплат", "% г/г"),
    "PPI": ("B3", "ИЦП: от ИПЦ и цены газа", "% г/г"),
    "DEFL": ("B3", "Дефлятор ВВП: от ИПЦ и ИЦП", "% г/г"),
    "U": ("B4", "Изменение безработицы: закон Оукена", "п.п."),
    "W": ("B4", "Номинальная зарплата: ИПЦ, минимальная, бюджет, безработица", "% г/г"),
    "EXP_P": ("B5", "Цены экспорта в USD: от пшеницы и стали", "% г/г"),
    "IMP_P": ("B5", "Цены импорта в USD: от газа", "% г/г"),
    "RATE": ("B7", "Учётная ставка НБУ на конец года: от ИПЦ", "%"),
    "LOAN": ("B7", "Ставка по кредитам: от учётной ставки", "%"),
    "DEP": ("B7", "Ставка по депозитам: от учётной ставки", "%"),
    "LOANS_G": ("B7", "Рост кредитов в гривне: от номинального ВВП и реальной ставки", "% г/г"),
}

# Notes on how the model uses the equation, where it differs from the plain fit
NOTES = {
    "EXP_P": "В модели константа откалибрована (2 вместо оценки): проверяется оценённая версия",
    "U": "Безработица 2022–2025 — оценки НБУ",
    "W": "Без 2022; безработица 2022–2025 — оценки НБУ. Короткая выборка (9 лет): ретропрогноз 2023 на 6 годах",
    "GVA_OTHER": "В модели наклон к потреблению из этой оценки, константа тоже",
}


def datasets() -> dict:
    """Equation id -> (y, X) on all available years, rows with gaps dropped."""
    out = {}

    def add(eq, df, y, regs):
        d = df[[y] + regs].apply(pd.to_numeric, errors="coerce").dropna()
        out[eq] = (d[y], d[regs])

    g1, x1 = annual_growth(real_sector.real_levels_q()), real_sector.drivers()
    for s in ["A", "B", "C", "G", "H", "O"]:
        add(f"GVA_{s}", pd.concat([g1[s], x1], axis=1), s, real_sector.EQUATIONS[s])
    hh = annual_growth(demand.real_levels_q())["HH"].rename("HH")
    add("GVA_OTHER", pd.concat([g1["OTHER"], hh, x1["WAR22"]], axis=1), "OTHER", ["HH", "WAR22"])
    g2, x2 = annual_growth(demand.real_levels_q()), demand.regressors()
    for c, regs in demand.EQUATIONS.items():
        add(f"GDPE_{c}", pd.concat([g2[c], x2[regs]], axis=1), c, regs)
    a3 = prices.annual()
    for y, regs in prices.EQUATIONS.items():
        add(y, a3, y, regs)
    add("U", labour.annual(), "DU", ["GDP"])
    add("W", wages.annual().drop(index=wages.SKIP), "WAGE", wages.REGS)
    a5 = external.annual()
    for y, regs in external.EQUATIONS.items():
        add(y, a5, y, regs)
    a7 = monetary.annual()
    for y, regs in monetary.EQUATIONS.items():
        add(y, a7, y, regs)
    return out


def predict(fit: dict, X: pd.DataFrame) -> pd.Series:
    c = fit["coef"]
    return c["const"] + sum(c[k] * X[k] for k in X.columns)


def check(y: pd.Series, X: pd.DataFrame) -> dict:
    ins = (y.index >= FIRST) & (y.index <= LAST)
    fit = ols(y[ins], X[ins])
    drivers = [k for k in X.columns if k not in DUMMIES]
    t = {k: fit["coef"][k] / fit["se"][k] for k in drivers if fit["se"][k] > 0}
    oos, naive, mean = {}, {}, {}
    for yr in TEST_YEARS:
        if yr not in y.index:
            continue
        tr = (y.index >= FIRST) & (y.index < yr)
        f = ols(y[tr], X[tr])
        oos[yr] = float(y[yr] - predict(f, X.loc[[yr]]).iloc[0])
        prev = y[y.index < yr]
        naive[yr] = float(y[yr] - prev.iloc[-1])
        mean[yr] = float(y[yr] - prev[(prev.index >= FIRST) & (prev.index != "2022")].mean())
    mae = lambda e: float(np.mean(np.abs(list(e.values())))) if e else np.nan
    bench = min(mae(naive), mae(mean))
    ratio = mae(oos) / bench if bench > 0 else np.nan
    min_t = min((abs(v) for v in t.values()), default=np.nan)
    fitted = predict(fit, X[ins])
    keep = y[ins].index != "2022"
    ya, ra = y[ins][keep], (y[ins] - fitted)[keep]
    r2_ex22 = float(1 - (ra @ ra) / ((ya - ya.mean()) @ (ya - ya.mean())))
    e = list(oos.values())
    bias = float(np.mean(e)) if e else np.nan
    if e and abs(bias) > 0.75 * mae(oos) and len({np.sign(v) for v in e}) == 1:
        bias_note = "занижает" if bias > 0 else "завышает"
    else:
        bias_note = ""
    if not drivers:
        verdict = "только среднее"
    elif ratio < 0.8 and (np.isnan(min_t) or min_t >= 2):
        verdict = "надёжно"
    elif ratio < 1:
        verdict = "приемлемо"
    else:
        verdict = "слабо"
    return {
        "n": fit["n"], "r2": fit["r2"], "rmse": fit["rmse"], "min_t": min_t, "t": t,
        "oos": oos, "mae": mae(oos), "bench": bench, "bench_rule": "прошлый год" if mae(naive) <= mae(mean) else "среднее",
        "ratio": ratio, "bias": bias, "bias_note": bias_note, "verdict": verdict, "r2_ex22": r2_ex22,
        "actual": y[ins], "fitted": fitted,
    }


def report() -> dict:
    return {eq: check(y, X) for eq, (y, X) in datasets().items()}


if __name__ == "__main__":
    for eq, r in report().items():
        oos = " ".join(f"{v:+.1f}" for v in r["oos"].values())
        print(f"{eq:10s} n={r['n']:2d} R2={r['r2']:.2f}/{r['r2_ex22']:.2f} {r['bias_note']} min|t|={r['min_t']:.1f} oos[{oos}] "
              f"mae={r['mae']:.1f} bench={r['bench']:.1f} ({r['bench_rule']}) ratio={r['ratio']:.2f} {r['verdict']}")
