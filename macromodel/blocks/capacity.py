"""Block B8: capacity limits on growth (labour, energy, logistics).

Each limit gives the highest real growth the economy can reach this year:
- labour: employment growth plus the fastest productivity growth seen (rounded up);
- energy: growth of available peak capacity net of outages from strikes, plus the
  usual decline in electricity use per unit of GDP;
- logistics: growth of export volumes the ports and land routes can carry.
The model's own GDP and export growth are compared with these limits on CHECKS.
"""
import numpy as np
import pandas as pd

from macromodel.blocks.real_sector import quarterly


def annual() -> pd.DataFrame:
    d = quarterly()
    y = d.index.str[:4]
    a = pd.DataFrame({
        "GDP": d["GDP_REAL"].groupby(y).sum(min_count=4),
        "EMPL": d["EMPL"].groupby(y).mean(),
        "ELEC": d["ELEC_CONS"].groupby(y).sum(min_count=4),
    })
    a["PROD_G"] = (a["GDP"] / a["EMPL"]).pct_change(fill_method=None) * 100
    a["EI"] = a["ELEC"] / a["GDP"] * 1000  # kWh per thousand UAH of 2021 GDP
    return a


def calibration() -> dict:
    a = annual()
    ei = a["EI"].dropna()
    ei_g = ((ei.iloc[-1] / ei.iloc[0]) ** (1 / (len(ei) - 1)) - 1) * 100
    return {
        ("CAP", "PROD_MAX"): (float(np.ceil(a["PROD_G"].max()))),
        ("CAP", "EI"): round(float(-ei_g), 1),
        ("CAP", "STRIKE_LOSS"): 0.05,
        ("CAP", "SEA_SHARE"): 0.6,
        ("CAP", "LAND_G"): 3.0,
    }


NOTES = {
    ("CAP", "PROD_MAX"): "Предельный рост производительности труда, %: максимум 2016–2021 (5,6% в 2021), округлён вверх; тот же порог на CHECKS",
    ("CAP", "EI"): "Снижение электроёмкости ВВП, % в год: среднее 2015–2024",
    ("CAP", "STRIKE_LOSS"): "Доля пиковой мощности, теряемая при интенсивности ударов 1 (отключения сверх учтённых в доступной мощности); допущение",
    ("CAP", "SEA_SHARE"): "Доля экспорта товаров по морю (порты); допущение по 2024–2025",
    ("CAP", "LAND_G"): "Рост пропускной способности суши (железная дорога, авто, Дунай), % в год; допущение",
}


def coef_table() -> list[dict]:
    return [{"eq": eq, "var": var, "coef": v, "note": NOTES[(eq, var)]} for (eq, var), v in calibration().items()]


if __name__ == "__main__":
    print(annual().round(2).to_string())
    print(calibration())
