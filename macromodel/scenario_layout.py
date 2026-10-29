"""Row numbers of the SCENARIOS sheet, kept in one place (layout of 2026-10-29).

Andrey asked (29.10) for the forecasts on top: first the annual ones, then the quarterly inputs, and the limits
and logic checks at the bottom. The sheet was rearranged by moving whole blocks (formulas on other sheets followed
the cells), and every payload takes its SCENARIOS rows from here, so a later move changes only this file.

Columns: annual blocks C:K by scenario (C:E Base, F:H Pessimistic, I:K Optimistic), L:N active, O source;
quarterly blocks C:L = 2026Q3..2028Q4 (the main block: C = first half 2026, D:M = 2026Q3..2028Q4).
"""

# ---- top: active scenario C3, last fact quarter C4, scenario names A8:A10 ----
ANNUAL_FIRST, ANNUAL_LAST = 16, 33  # annual table: 16 ceasefire quarter .. 33 share of foreign workers

# ---- annual blocks (formulas over the quarterly inputs below) ----
BRENT = 37  # Brent: 2026 the fourth quarter, later the average of the year (header 36)
WAGES = 39  # title; 42 minimum wage, 43 military pay, 44 civil budget pay, 45 de-shadowing
DESHADOW = 45
SHOCKS_Y = 47  # title "Отраслевые шоки по годам"
MET_Y = 50  # metallurgy, average of the year (after the recovery limits of B8_CAPACITY)
PEACE = 52  # title; 55 peace effect in consumption, 56 in investment
PEACE_C, PEACE_I = 55, 56
RECON_FIRST = 60  # title; 63 money for reconstruction
RECON = 63
AGRO_FIRST = 66  # title; 69 sunflower oil, 70 weather, 71 sown area
SUNOIL, WEATHER, AREA = 69, 70, 71
EDU = 77  # education and health pay fund (title 74)
EURUSD = 82  # EUR/USD (title 79)
DESTROYED = 85  # title; 87 metallurgy, 88 ports, 89 chemistry and refinery, 90 chemistry from quarter

# ---- quarterly inputs ----
Q_MAIN = 92  # title of the main quarterly block; parameters from row 95, four rows each (metallurgy seven)
EXTRA_FIN = 187  # extra financing partners are ready to give: Base row (title 186), Pess, Opt, active 190
Q_FIN = 192  # title "Квартальная разбивка"; quarter header 194
Q_HEAD = 194
FIN_Q = 196  # external financing Base / Pess / Opt 196-198
STRIKES_Q = 199  # strikes on energy Base / Pess / Opt 199-201; active financing 202, strikes 203
NBU_Q = 205  # title; 206 real GDP, 207 CPI, 208 UAH/USD, 209 NBU rate
GDP_Q, CPI_Q, FX_Q, RATE_Q = 206, 207, 208, 209
TARIFF = 213  # utility tariff hikes by quarter (title 211)
FUEL_HEAD = 216
FUEL_QQ = 217  # input: fuel prices q/q
FUEL_LAG = 218  # the same quarter a year ago, q/q
FUEL = 219  # result y/y, read by B3_PRICES row 45
FUEL_QQ_RES = 220  # result q/q (input or the B3 equation)
LABOUR = 223  # title of the quarterly labour block (B4_LABOUR); parameters from row 225

# ---- bottom: limits and logic checks ----
LIMITS = 263  # title; limits table 266-275, logic checks from 279

