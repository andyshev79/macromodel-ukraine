"""Scenario shocks outside the estimated equations: utility tariff hikes and a metallurgy stop.

Tariffs (SCENARIOS row 57, by quarter, all scenarios): CPI y/y rises by the weight of
housing and utilities in CPI times the hike, in the quarter of the hike and the next three.
Metallurgy (SCENARIOS row 63, utilisation in % of 2025, by year and scenario): the change
in utilisation moves manufacturing, mining and real exports by the metallurgy shares below.
CPI_SPEED sets inflation inertia: each quarter CPI closes this share of the gap between the
previous quarter and the annual B3 model.
All values are calibrated assumptions, not estimates.
"""
COEF_FIRST = 90  # after B7 transmission (85-89)
TARIFF_ROW = 57
MET_ROW = 63

SHOCKS = {
    "TARIFF_W": (0.11, "B3", "Вес «Жильё, вода, электроэнергия, газ» в ИПЦ ≈ 11%; уточнить по весам Госстата текущего года. "
                             "Вторичные эффекты не учтены."),
    "MET_C": (0.12, "B1", "Доля металлургии в ВДС перерабатывающей промышленности (после потери Мариуполя); допущение, уточнить по Госстату"),
    "MET_B": (0.2, "B1", "Доля добычи, связанная с металлургией (руда и уголь для своих заводов; часть руды идёт на экспорт); допущение"),
    "MET_X": (0.07, "B2", "Доля чёрных металлов и изделий в экспорте товаров и услуг 2025; допущение"),
    "CPI_SPEED": (0.5, "B3", "Инерция инфляции: доля разрыва между прошлым кварталом и годовой моделью B3, закрываемая за квартал "
                             "(0,5 — половина за квартал; 1 — без инерции). Допущение; тарифы добавляются сразу, без инерции"),
}
SHOCK_ROW = {k: COEF_FIRST + i for i, k in enumerate(SHOCKS)}
