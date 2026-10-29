"""Row numbers of the SCENARIOS sheet, kept in one place (layout of 2026-10-29).

Andrey asked (29.10) for the forecasts on top: first the annual ones, then the quarterly inputs, and the limits
and logic checks at the bottom. The sheet was rearranged by moving whole blocks (formulas on other sheets followed
the cells), and every payload takes its SCENARIOS rows from here, so a later move changes only this file.

Columns: annual blocks C:K by scenario (C:E Base, F:H Pessimistic, I:K Optimistic), L:N active, O source;
quarterly blocks C:L = 2026Q3..2028Q4 (the main block: C = first half 2026, D:M = 2026Q3..2028Q4).

The strike intensity on energy (old row 17 and its quarterly rows) was removed on 2026-10-29 at Andrey's request:
hard to interpret and to estimate; the energy war is in the available capacity (row 17, GW). The same day the unused
annual rows of minimum wage, military and civil budget pay went too (the quarterly labour block holds them).
The annual Brent block (old rows 35-36) was removed the same day: B3_PRICES reads the quarterly Brent rows directly;
two blank rows were added above the quarterly block, so rows from 88 down did not move.
Later that day (Andrey: no duplicates) the remaining annual blocks were folded into the annual table (rows 33-42):
annual-only parameters are typed there, their quarterly rows were removed, and every row below moved up.
Then (Andrey, 29.10: "убираем лишнее") the metallurgy level rows, the fuel helper rows (year-ago q/q, y/y and q/q results,
now in B3_PRICES section 6) and the scenario copies of the minimum wage and the December bonus (one row for all
scenarios) were deleted; rows below moved up by 3, 6, 9 and 12.
"""

# ---- top: active scenario C3, last fact quarter C4, scenario names A8:A10 ----
# annual table (rows 16-42): base C:E, pessimistic F:H, optimistic I:K, active L:N, source O.
# Rows 16-32 as before; 33-39 annual-only inputs (one value a year, typed here: Andrey, 2026-10-29),
# 40-42 annual summaries of quarterly inputs (formulas).
Y = {"CEASEFIRE": 16, "CAP": 17, "PORTS": 18, "FIN": 19, "DEF": 20, "MIGR": 21, "MOB": 22, "HARVEST": 23, "WHEAT": 24,
     "STEEL": 25, "TTF": 26, "EA_GDP": 27, "HICP": 28, "FED": 29, "GUEST": 30, "SH_MIGR": 31, "SH_GUEST": 32,
     "DESHADOW": 33, "PEACE_C": 34, "PEACE_I": 35, "RECON": 36, "WEATHER": 37, "AREA": 38, "EDU": 39,
     "MET": 40, "SUNOIL": 41, "EURUSD": 42}
ANNUAL_FIRST, ANNUAL_LAST = 16, 42
ANNUAL_INPUTS = ("SH_MIGR", "SH_GUEST", "DESHADOW", "PEACE_C", "PEACE_I", "RECON", "WEATHER", "AREA", "EDU")

# aliases kept for the block payloads (the separate annual blocks were folded into the table on 2026-10-29)
DESHADOW, MET_Y, PEACE_C, PEACE_I, RECON = Y["DESHADOW"], Y["MET"], Y["PEACE_C"], Y["PEACE_I"], Y["RECON"]
SUNOIL, WEATHER, AREA, EDU, EURUSD = Y["SUNOIL"], Y["WEATHER"], Y["AREA"], Y["EDU"], Y["EURUSD"]

DESTROYED = 45  # title; 47 metallurgy, 48 ports, 49 chemistry and refinery, 50 chemistry from quarter

# ---- quarterly inputs ----
Q_MAIN = 54  # title of the main quarterly block; parameters from row 57, four rows each (Base, Pess, Opt, active)
EXTRA_FIN = 110  # extra financing partners are ready to give: Base row (title 109), Pess, Opt, active 113
Q_FIN = 115  # title "Квартальная разбивка"; quarter header 117
Q_HEAD = 117
FIN_Q = 119  # external financing Base / Pess / Opt 119-121, active 122
FIN_ACT = 122
NBU_Q = 124  # title; 125 real GDP, 126 CPI, 127 UAH/USD, 128 NBU rate
GDP_Q, CPI_Q, FX_Q, RATE_Q = 125, 126, 127, 128
TARIFF = 132  # utility tariff hikes by quarter (title 130)
FUEL_HEAD = 135
FUEL_QQ = 136  # the only fuel row: fuel prices q/q (input); y/y and the seasonality are computed in B3_PRICES section 6
LABOUR = 139  # title of the quarterly labour block (B4_LABOUR); parameters from row 141

# labour parameters: one row for all scenarios (Andrey, 29.10: minimum wage and December bonus) or Base/Pess/Opt/active
LAB_PARAMS = ("MINW", "MIL", "CIV", "MIGR", "MOB", "GUEST", "DEC", "MILN", "MILINT")
LAB_SINGLE = ("MINW", "DEC")
LAB, LAB_ACT = {}, {}  # first row and the row the model reads
_r = LABOUR + 2
for _p in LAB_PARAMS:
    LAB[_p] = _r
    LAB_ACT[_p] = _r if _p in LAB_SINGLE else _r + 3
    _r += 1 if _p in LAB_SINGLE else 4
LAB_NOTE = _r  # note row under the labour block

# ---- bottom: limits and logic checks ----
LIMITS = 173  # title; limits table 176-185, logic checks from 189
