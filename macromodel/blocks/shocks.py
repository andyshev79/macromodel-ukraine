"""Scenario shocks outside the estimated equations: utility tariff hikes and a metallurgy stop.

Tariffs (SCENARIOS row 57, by quarter, all scenarios): CPI y/y rises by the weight of
housing and utilities in CPI times the hike, in the quarter of the hike and the next three.
Metallurgy (SCENARIOS row 63, utilisation in % of 2025, by year and scenario): the change
in utilisation, in points of 2025 output, moves manufacturing, mining and real exports by the
metallurgy elasticities below (a restart from 15 to 50 adds 35% of 2025 output, not +233%).
Since 2026-10-24 quarterly CPI is built from NBU blocks (cpi_blocks): tariffs enter administered
prices and fuel is its own block. CPI_SPEED (inertia towards the annual B3 model) and fuel() with
FUEL_W/FUEL_NORM stay on COEFS for reference but are not used in the sheet.
TARIFF_W, MET_C and MET_X now come from the long history (estimated() below); MET_B stays
calibrated (the post-invasion fit is not significant).
"""
COEF_FIRST = 90  # after B7 transmission (85-89)
TARIFF_ROW = 57
MET_ROW = 63

SHOCKS = {
    "TARIFF_W": (0.11, "B3", "Вес «Жильё, вода, электроэнергия, газ» в ИПЦ ≈ 11%; уточнить по весам Госстата текущего года. "
                             "Вторичные эффекты не учтены."),
    "MET_C": (0.12, "B1", "Доля металлургии в ВДС перерабатывающей промышленности (после потери Мариуполя); допущение, уточнить по Госстату"),
    "MET_B": (0.2, "B1", "Доля добычи, связанная с металлургией (руда и уголь для своих заводов; часть руды идёт на экспорт); допущение. "
                       "Оценка 2024–2026 даёт 0,26, но незначима (t 1,3)"),
    "MET_X": (0.07, "B2", "Доля металлов и изделий в экспорте товаров и услуг 2025"),
    "CPI_SPEED": (0.5, "B3", "Инерция инфляции: доля разрыва между прошлым кварталом и годовой моделью B3, закрываемая за квартал "
                             "(0,5 — половина за квартал; 1 — без инерции). Допущение; тарифы добавляются сразу, без инерции"),
}
SHOCK_ROW = {k: COEF_FIRST + i for i, k in enumerate(SHOCKS)}


FUEL_ROW = 74  # SCENARIOS: fuel prices y/y by quarter
FUEL_COEF_ROW, FUEL_NORM_ROW = 105, 106  # COEFS, after the wage equation (98-104)
MET_FIRST = "2024Q1"  # after Mariupol and the 2023 rebound: today's weight of metallurgy


def estimated() -> dict:
    """Shock coefficients measured on data/history/long: name -> (value, se or None, period, method, note)."""
    import pandas as pd

    from macromodel import quarterly as Q
    d = Q.long_quarterly()
    out = {}
    # CPI y/y on its component groups: the coefficient on utilities is their effective weight
    comps = ["CPI_FOOD_YOY", "CPI_ALC_TOB_YOY", "CPI_UTIL_YOY", "CPI_HEALTH_YOY", "CPI_TRANSPORT_YOY"]
    df = d[["CPI_YOY"] + comps].loc[Q.FIRST:Q.LAST].dropna().drop(index=Q.WAR, errors="ignore")
    r = Q.ols_nw(df["CPI_YOY"], df[comps])
    out["TARIFF_W"] = (r["coef"]["CPI_UTIL_YOY"], r["se"]["CPI_UTIL_YOY"], "2011–2025",
                       "оценка МНК 2011–2025, квартальные г/г без 2022Q1–2023Q1, ошибки Ньюи–Уэста",
                       "Эффективный вес ЖКУ в ИПЦ: ИПЦ г/г на группы (продукты, алкоголь и табак, ЖКУ, здоровье, транспорт), "
                       f"R² {r['r2']:.2f}. Вторичные эффекты не учтены.".replace("R² 1.", "R² 1,").replace("R² 0.", "R² 0,"))
    # Manufacturing GVA y/y on metallurgy output y/y (industrial index, sections 24–25)
    df = d[["GVA_C_YOY", "IND_C8_YOY"]].loc[MET_FIRST:].dropna()
    r = Q.ols_nw(df["GVA_C_YOY"], df[["IND_C8_YOY"]], lags=2)
    out["MET_C"] = (r["coef"]["IND_C8_YOY"], r["se"]["IND_C8_YOY"], f"{MET_FIRST[:4]}–{df.index[-1][:4]}",
                    f"оценка МНК {df.index[0]}–{df.index[-1]}, квартальные г/г, ошибки Ньюи–Уэста",
                    "Эластичность ВДС переработки к выпуску металлургии (индекс промпроизводства, разделы 24–25), "
                    "с цепочкой поставок внутри переработки. Короткая выборка: до 2022 эластичность была 0,49 (больше Мариуполь)")
    a = pd.read_csv(Q.HIST_LONG / "annual_y.csv", index_col=0)
    share = float(a.loc["EXPG_METALS_USD", Q.LAST[:4]] / a.loc["EXP_USD", Q.LAST[:4]])
    out["MET_X"] = (share, None, Q.LAST[:4], "расчёт по данным",
                    f"Доля металлов и изделий в экспорте товаров и услуг {Q.LAST[:4]} (торговля по группам товаров)")
    return out


def fuel() -> dict:
    """CPI y/y on FX, wages and fuel prices of the previous quarter (CPI component 'fuel and lubricants')."""
    import pandas as pd

    from macromodel import quarterly as Q
    d, q = Q.long_quarterly(), Q.data()
    fl = d["CPI_FUEL_YOY"].shift(1).rename("FUEL_L1")
    df = pd.concat([q["CPI"], q["FX"], q["WAGE"], fl], axis=1).loc[Q.FIRST:Q.LAST].dropna().drop(index=Q.WAR, errors="ignore")
    r = Q.ols_nw(df["CPI"], df[["FX", "WAGE", "FUEL_L1"]])
    norm = float(d["CPI_FUEL_YOY"].loc[Q.FIRST:Q.LAST].drop(index=Q.WAR, errors="ignore").mean())
    food = pd.concat([d["CPI_FOOD_YOY"], q["FX"], fl], axis=1).loc[Q.FIRST:Q.LAST].dropna().drop(index=Q.WAR, errors="ignore")
    rf = Q.ols_nw(food["CPI_FOOD_YOY"], food[["FX", "FUEL_L1"]])
    return {"coef": float(r["coef"]["FUEL_L1"]), "se": float(r["se"]["FUEL_L1"]), "r2": float(r["r2"]), "n": len(df),
            "norm": norm, "food": float(rf["coef"]["FUEL_L1"]), "food_se": float(rf["se"]["FUEL_L1"]),
            "last": float(d["CPI_FUEL_YOY"]["2026Q2"]), "prev": float(d["CPI_FUEL_YOY"]["2026Q1"]), "q3": float(d["CPI_FUEL_YOY"].get("2026Q3", float("nan")))}
