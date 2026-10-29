"""Row numbers of the SCENARIOS sheet, kept in one place (layout of 2026-10-29).

Andrey asked (29.10) for the forecasts on top: first the annual ones, then the quarterly inputs, and the limits
and logic checks at the bottom. The sheet was rearranged by moving whole blocks (formulas on other sheets followed
the cells), and every payload takes its SCENARIOS rows from here, so a later move changes only this file.

Columns: annual blocks C:K by scenario (C:E Base, F:H Pessimistic, I:K Optimistic), L:N active, O source;
quarterly blocks C:L = 2026Q3..2028Q4 (the main block: C = first half 2026, D:M = 2026Q3..2028Q4).

The strike intensity on energy (old row 17 and its quarterly rows) was removed on 2026-10-29 at Andrey's request:
hard to interpret and to estimate; the energy war is in the available capacity (row 17, GW).
"""

# ---- top: active scenario C3, last fact quarter C4, scenario names A8:A10 ----
# annual table (rows 16-32): base C:E, pessimistic F:H, optimistic I:K, active L:N
Y = {"CEASEFIRE": 16, "CAP": 17, "PORTS": 18, "FIN": 19, "DEF": 20, "MIGR": 21, "MOB": 22, "HARVEST": 23, "WHEAT": 24,
     "STEEL": 25, "TTF": 26, "EA_GDP": 27, "HICP": 28, "FED": 29, "GUEST": 30, "SH_MIGR": 31, "SH_GUEST": 32}
ANNUAL_FIRST, ANNUAL_LAST = 16, 32

# ---- annual blocks (formulas over the quarterly inputs below) ----
BRENT = 36  # Brent: 2026 the fourth quarter, later the average of the year (header 35)
WAGES = 38  # title; 41 minimum wage, 42 military pay, 43 civil budget pay, 44 de-shadowing
DESHADOW = 44
SHOCKS_Y = 46  # title "Отраслевые шоки по годам"
MET_Y = 49  # metallurgy, average of the year (after the recovery limits of B8_CAPACITY)
PEACE = 51  # title; 54 peace effect in consumption, 55 in investment
PEACE_C, PEACE_I = 54, 55
RECON_FIRST = 59  # title; 62 money for reconstruction
RECON = 62
AGRO_FIRST = 65  # title; 68 sunflower oil, 69 weather, 70 sown area
SUNOIL, WEATHER, AREA = 68, 69, 70
EDU = 76  # education and health pay fund (title 73)
EURUSD = 81  # EUR/USD (title 78)
DESTROYED = 84  # title; 86 metallurgy, 87 ports, 88 chemistry and refinery, 89 chemistry from quarter

# ---- quarterly inputs ----
Q_MAIN = 91  # title of the main quarterly block; parameters from row 94, four rows each (metallurgy seven)
EXTRA_FIN = 186  # extra financing partners are ready to give: Base row (title 185), Pess, Opt, active 189
Q_FIN = 191  # title "Квартальная разбивка"; quarter header 193
Q_HEAD = 193
FIN_Q = 195  # external financing Base / Pess / Opt 195-197, active 198
FIN_ACT = 198
NBU_Q = 200  # title; 201 real GDP, 202 CPI, 203 UAH/USD, 204 NBU rate
GDP_Q, CPI_Q, FX_Q, RATE_Q = 201, 202, 203, 204
TARIFF = 208  # utility tariff hikes by quarter (title 206)
FUEL_HEAD = 211
FUEL_QQ = 212  # input: fuel prices q/q
FUEL_LAG = 213  # the same quarter a year ago, q/q
FUEL = 214  # result y/y, read by B3_PRICES row 45
FUEL_QQ_RES = 215  # result q/q (input or the B3 equation)
LABOUR = 218  # title of the quarterly labour block (B4_LABOUR); parameters from row 220

# ---- bottom: limits and logic checks ----
LIMITS = 258  # title; limits table 261-270, logic checks from 274
