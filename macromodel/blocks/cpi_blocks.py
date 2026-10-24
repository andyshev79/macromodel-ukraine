"""CPI by the NBU's blocks: core, raw food, administered prices, fuel (quarterly, % y/y, end of quarter).

Weights: CPI y/y on the four NBU components 2019Q1–2026Q2 (they sum to ≈ 1, so they are the
effective basket weights). Block equations, OLS with Newey–West errors:
- core: FX, wages and last quarter's core (2011–2025 without 2022Q1–2023Q1);
- raw food: last quarter's raw food, fuel prices of the previous quarter, harvest growth (2017–2025);
- fuel: Brent in USD and FX, y/y (2019–2026, war quarters kept: they hold the FX variation);
- administered: inertia (2017–2025), plus utility tariff hikes from SCENARIOS row 57 over four quarters.
The NBU split starts in 2017 (raw food, administered) and 2019 (fuel), so these samples are short.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from macromodel import quarterly as Q

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
COEF_FIRST = 108  # COEFS rows after fuel (105-106)
BLOCKS = ["CORE", "RAW", "ADM", "FUEL"]
NAMES = {"CORE": "Базовая инфляция", "RAW": "Сырые продукты", "ADM": "Административные цены", "FUEL": "Топливо"}
EQ = {
    "W": ("CPI", BLOCKS, "2019Q1", "2026Q2", False),
    "CORE": ("CORE", ["FX", "WAGE", "CORE_L1"], "2011Q1", "2025Q4", True),
    "RAW": ("RAW", ["RAW_L1", "FUEL_L1", "HARV"], "2017Q1", "2025Q4", True),
    "FUEL": ("FUEL", ["BRENT", "FX"], "2019Q1", "2026Q2", False),
    "ADM": ("ADM", ["ADM_L1"], "2017Q1", "2025Q4", True),
}


def harvest_growth() -> pd.Series:
    h = pd.read_csv(EXT / "drivers_y.csv", index_col=0).loc["HARVEST"].drop(["name", "unit", "source"]).astype(float)
    h.index = h.index.astype(str)
    return h.pct_change() * 100


def data() -> pd.DataFrame:
    d, q = Q.long_quarterly(), Q.data()
    x = pd.DataFrame({"CPI": d["CPI_YOY"], "CORE": d["CORE_CPI_YOY"], "RAW": d["CPI_RAW_FOOD_YOY"],
                      "ADM": d["CPI_ADMIN_YOY"], "FUEL": d["CPI_FUEL_NBU_YOY"],
                      "BRENT": d["PX_BRENT_USD"].pct_change(4, fill_method=None) * 100, "FX": q["FX"], "WAGE": q["WAGE"]})
    for c in ["CORE", "RAW", "ADM", "FUEL"]:
        x[f"{c}_L1"] = x[c].shift()
    hg = harvest_growth()
    # a harvest shows in prices from Q3 of its year to Q2 of the next
    x["HARV"] = [hg.get(i[:4] if i[-1] in "34" else str(int(i[:4]) - 1), np.nan) for i in x.index]
    return x


def estimate() -> dict:
    x, out = data(), {}
    for k, (y, regs, first, last, drop_war) in EQ.items():
        df = x[[y] + regs].loc[first:last].dropna()
        if drop_war:
            df = df.drop(index=Q.WAR, errors="ignore")
        out[k] = {**Q.ols_nw(df[y], df[regs]), "n": len(df), "period": f"{df.index[0][:4]}–{df.index[-1][:4]}"}
    return out


def coef_rows() -> list[dict]:
    """COEFS rows: name -> value, se, period, method, note."""
    est, rows = estimate(), []
    notes = {
        ("W", "const"): "Взвешивание блоков: ИПЦ = константа + Σ вес × блок (веса оценены, сумма ≈ 1)",
        ("CORE", "FX"): "Девальвация, % г/г квартала", ("CORE", "WAGE"): "Рост номинальной зарплаты, % г/г квартала",
        ("CORE", "CORE_L1"): "Инерция базовой инфляции", ("RAW", "RAW_L1"): "Инерция цен сырых продуктов",
        ("RAW", "FUEL_L1"): "Топливо прошлого квартала: затраты аграриев и перевозки",
        ("RAW", "HARV"): "Рост урожая зерновых и масличных (с 3 кв. года урожая по 2 кв. следующего); слабая связь",
        ("FUEL", "BRENT"): "Нефть Brent в USD, % г/г", ("FUEL", "FX"): "Девальвация: топливо импортное, перенос ≈ 1",
        ("ADM", "ADM_L1"): "Инерция админцен (акцизы, проезд, связь); тарифы ЖКУ добавляются из SCENARIOS строка 57",
    }
    method = lambda k: f"оценка МНК {est[k]['period']}, квартальные г/г, ошибки Ньюи–Уэста" + (
        " без 2022Q1–2023Q1" if EQ[k][4] else "")
    for k, r in est.items():
        for v in ["const"] + EQ[k][1]:
            rows.append({"eq": f"CPIB_{k}", "var": v, "coef": float(r["coef"][v]), "se": float(r["se"][v]),
                         "r2": float(r["r2"]), "period": est[k]["period"], "method": method(k),
                         "note": notes.get((k, v), "Вес блока в ИПЦ" if k == "W" else "Константа")})
    rows.append({"eq": "CPIB_ADM", "var": "TARIFF", "coef": None, "se": None, "r2": None, "period": "",
                 "method": "расчёт", "note": "Доля ЖКУ в админценах: вес ЖКУ в ИПЦ (SHOCK_TARIFF_W) / вес админцен"})
    return rows


if __name__ == "__main__":
    for k, r in estimate().items():
        print(k, r["n"], r["period"], round(r["r2"], 2), {v: (round(c, 3), round(c / r["se"][v], 1)) for v, c in r["coef"].items()})
