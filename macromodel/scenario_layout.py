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
"""

# ---- top: active scenario C3, last fact quarter C4, scenario names A8:A10 ----
# annual table (rows 16-32): base C:E, pessimistic F:H, optimistic I:K, active L:N
Y = {"CEASEFIRE": 16, "CAP": 17, "PORTS": 18, "FIN": 19, "DEF": 20, "MIGR": 21, "MOB": 22, "HARVEST": 23, "WHEAT": 24,
     "STEEL": 25, "TTF": 26, "EA_GDP": 27, "HICP": 28, "FED": 29, "GUEST": 30, "SH_MIGR": 31, "SH_GUEST": 32}
ANNUAL_FIRST, ANNUAL_LAST = 16, 32

# ---- annual blocks (formulas over the quarterly inputs below) ----
WAGES = 36  # title; 39 de-shadowing (annual minimum wage and budget pay rows removed 2026-10-29: inputs are quarterly)
DESHADOW = 39
SHOCKS_Y = 41  # title "Отраслевые шоки по годам"
MET_Y = 44  # metallurgy, average of the year (after the recovery limits of B8_CAPACITY)
PEACE = 46  # title; 49 peace effect in consumption, 50 in investment
PEACE_C, PEACE_I = 49, 50
RECON_FIRST = 54  # title; 57 money for reconstruction
RECON = 57
AGRO_FIRST = 60  # title; 63 sunflower oil, 64 weather, 65 sown area
SUNOIL, WEATHER, AREA = 63, 64, 65
EDU = 71  # education and health pay fund (title 68)
EURUSD = 76  # EUR/USD (title 73)
DESTROYED = 79  # title; 81 metallurgy, 82 ports, 83 chemistry and refinery, 84 chemistry from quarter

# ---- quarterly inputs ----
Q_MAIN = 88  # title of the main quarterly block; parameters from row 91, four rows each (metallurgy seven)
EXTRA_FIN = 183  # extra financing partners are ready to give: Base row (title 182), Pess, Opt, active 186
Q_FIN = 188  # title "Квартальная разбивка"; quarter header 190
Q_HEAD = 190
FIN_Q = 192  # external financing Base / Pess / Opt 192-194, active 195
FIN_ACT = 195
NBU_Q = 197  # title; 198 real GDP, 199 CPI, 200 UAH/USD, 201 NBU rate
GDP_Q, CPI_Q, FX_Q, RATE_Q = 198, 199, 200, 201
TARIFF = 205  # utility tariff hikes by quarter (title 203)
FUEL_HEAD = 208
FUEL_QQ = 209  # input: fuel prices q/q
FUEL_LAG = 210  # the same quarter a year ago, q/q
FUEL = 211  # result y/y, read by B3_PRICES row 45
FUEL_QQ_RES = 212  # result q/q (input or the B3 equation)
LABOUR = 215  # title of the quarterly labour block (B4_LABOUR); parameters from row 217

# ---- bottom: limits and logic checks ----
LIMITS = 255  # title; limits table 258-267, logic checks from 271
