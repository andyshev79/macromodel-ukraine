"""Block B10: agriculture, harvest by crop and agro exports (2026-10-25).

Harvest of six main crops (Ukrstat, Ministry of Agrarian Policy for the current year). Forecast years:
average harvest 2023-2026 (territory after 2022) x sown area x weather, plus the 2027 shift from winter
wheat to spring crops announced by the ministry. Agro exports: grain surplus over domestic use plus
oilseeds (marketing year = half of this year's and half of last year's harvest) limited by port and land
capacity; what cannot be shipped stays in stocks for the next year. Value = volume x Black Sea FOB prices.
"""
from pathlib import Path

import numpy as np
import pandas as pd

EXT = Path(__file__).resolve().parents[2] / "data" / "external"
LONG = Path(__file__).resolve().parents[2] / "data" / "history" / "long"
COEF_FIRST = 196  # after B9 construction rows 185-195
CROPS = {"WHEAT": "Пшеница", "CORN": "Кукуруза", "BARLEY": "Ячмень",
         "SUNFLOWER": "Подсолнечник", "SOY": "Соя", "RAPESEED": "Рапс"}
GRAINS = ["WHEAT", "CORN", "BARLEY"]
SPRING = ["CORN", "SUNFLOWER", "SOY"]
BASE_YEARS = ["2023", "2024", "2025", "2026"]
FACT = "2025"   # last full year of agro exports
NOW = "2026"    # current year: harvest is the ministry estimate, exports anchored to H1 facts

CALIBRATED = {
    ("DOM", "GRAIN"): (20.0, "Внутреннее потребление зерна (корм, продовольствие, семена), млн т в год. Оценка Claude по балансам УЗА/USDA: 18–22"),
    ("OIL", "K"): (0.45, "Выход масла из маслосемян (подсолнечник почти весь перерабатывается внутри, экспорт — масло). Оценка Claude"),
    ("CAP", "SH"): (0.6, "Доля агро в пропускной способности морских портов. Оценка Claude: 2025 — около 50 из 82 млн т"),
    ("CAP", "LAND"): (10.0, "Экспорт агро по Дунаю, железной дороге и автотранспортом, млн т в год. Оценка Claude"),
    ("SHIFT", "WHEAT"): (-16.0, "Площадь пшеницы под урожай 2027, %: Минагрополитики 23.10.2026 — минус 15–17%"),
    ("SHIFT", "SPRING"): (5.0, "Рост яровых (кукуруза, подсолнечник, соя) на освободившихся площадях, %. Оценка Claude"),
}


def crops() -> pd.DataFrame:
    """Harvest by crop, million tonnes, years as columns."""
    return pd.read_csv(EXT / "crops_y.csv", index_col=0).drop(columns=["name", "unit", "source"]).astype(float)


def sources() -> dict:
    return pd.read_csv(EXT / "crops_y.csv", index_col=0)["source"].to_dict()


def prices() -> pd.DataFrame:
    """Annual average Black Sea FOB prices, USD/t (months with data)."""
    m = pd.read_csv(EXT / "agro_prices_m.csv")
    m["year"] = m["month"].str[:4]
    return m.groupby("year")[["WHEAT", "SUNOIL"]].mean()


def annual(code: str) -> pd.Series:
    y = pd.read_csv(LONG / "annual_y.csv", index_col=0)
    return y.loc[code].astype(float)


def quarterly(code: str) -> pd.Series:
    q = pd.read_csv(LONG / "series_q.csv", index_col=0)
    return q.loc[code].astype(float)


def marketing(s: pd.Series, year: str) -> float:
    """Marketing-year volume shipped in a calendar year: half of this year's and half of last year's harvest."""
    return 0.5 * s[year] + 0.5 * s[str(int(year) - 1)]


def history() -> dict:
    c = crops()
    h = c.sum()
    dom = CALIBRATED[("DOM", "GRAIN")][0]
    grain = c.loc[GRAINS].sum() - dom
    oil = c.drop(index=GRAINS).sum()
    px = prices()
    mix = lambda y: (marketing(grain, y) * marketing(px["WHEAT"], y) + marketing(oil, y) * CALIBRATED[("OIL", "K")][0]
                     * marketing(px["SUNOIL"], y)) / (marketing(grain, y) + marketing(oil, y))
    # weather: deviation of the harvest from its 3-year centred mean, 2016-2021 (before the war)
    lh = np.log(h)
    dev = (lh - lh.rolling(3, center=True).mean()).loc["2016":"2021"] * 100
    exp = annual("EXPG_AGRO_USD")
    g = (np.log(exp).diff() * 100).loc["2016":FACT].drop(index=["2022", "2023", "2024"], errors="ignore")
    q = quarterly("EXPG_AGRO_USD")
    return {
        "harvest": h, "base": c[BASE_YEARS].mean(axis=1), "sigma": float(dev.std()),
        "grain_my": marketing(grain, FACT), "oil_my": marketing(oil, FACT), "mix": float(mix(FACT)),
        "exp": float(exp[FACT]), "exp_lo": float(np.percentile(g, 10)), "exp_hi": float(np.percentile(g, 90)),
        "h1_now": float(q[f"{NOW}Q1"] + q[f"{NOW}Q2"]), "h1_prev": float(q[f"{FACT}Q1"] + q[f"{FACT}Q2"]),
        "agro_sh": float(exp[FACT] / annual("EXP_USD")[FACT]),
        "px": px,
    }


def coef_rows() -> list[dict]:
    h = history()
    rows = [{"code": "A_AGRO_SH", "eq": "A_EXP", "var": "AGRO_SH", "coef": round(h["agro_sh"], 2), "method": f"расчёт {FACT}",
             "note": "Доля агроэкспорта в экспорте товаров и услуг: эта часть реального экспорта B2 идёт за объёмом агроэкспорта B10"},
            {"code": "A_SIGMA", "eq": "A_HARV", "var": "SIGMA", "coef": round(h["sigma"], 1), "method": "ст. откл. 2016–2021",
             "note": "Погодный разброс урожая: отклонение от скользящего среднего за 3 года, % (до войны)"}]
    for (g, v), (c, note) in CALIBRATED.items():
        rows.append({"code": f"A_{g}_{v}", "eq": f"A_{g}", "var": v, "coef": c, "method": "калибровка", "note": note})
    return rows


ROW = {r["code"]: COEF_FIRST + i for i, r in enumerate(coef_rows())}
