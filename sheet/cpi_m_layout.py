"""Row layout of the CPI_M sheet (shared by cpi_m_payload and cpi_blocks_payload)."""
SHEET = "CPI_M"
ORIGIN = "2026-10"          # last month with Gosstat CPI; move with each monthly run
HIST_FIRST = "2016-01"      # first month shown (2017 needs 12 months back for y/y)

# section 1: summary of the six forecast months
S1_HDR = 5
S1_FIRST = 6
# section 2: quarter anchors for B3_PRICES (columns C = last fact quarter, D, E = the two nowcast quarters)
S2_HDR = 14
S2_ROW = {"CPI": 15, "CORE": 16, "RAW": 17, "ADM": 18, "FUEL": 19}
S2_COL = {"2026Q4": "D", "2027Q1": "E"}       # anchored quarters -> column on CPI_M
B3_COL = {"2026Q4": "G", "2027Q1": "H"}       # same quarters on B3_PRICES
B3_FACT_COL = "F"                             # last quarter with facts on B3_PRICES (2026Q3)
SCQ = {"2026Q4": "D", "2027Q1": "E"}          # SCENARIOS quarter columns
# section 3: block equations and weights
S3_HDR = 22
EQ_ROW = {"CORE": 23, "RAW": 24, "ADMX": 25}
SEAS_MIN, SEAS_MAX = 26, 27                   # headline m/m in history by calendar month
UTIL_ROW = 28                                  # utilities drift (B28)
W_HDR, W_ROW = 29, 30                          # weights of the headline equation
# section 4: benchmark
S4_HDR = 33
BM_ROW = {k: 34 + k - 1 for k in range(1, 7)}  # 34..39
BM_EXP = 40                                    # expectations value used at the origin
# section 5: checks
S5_HDR = 43
CHK_FIRST = 44
# section 6: accuracy (backtest) and the forecast log
S6_HDR = 62
ACC_ALL = 64       # 64..69
ACC_RECENT = 72    # 72..77
LOG_HDR = 80
LOG_FIRST = 81
LOG_ROWS = 60      # 81..140
# section 7: monthly table
S7_HDR = 143
T_FIRST = 145      # first data row (HIST_FIRST)
COLS = {"M": "A", "KIND": "B", "CPI_MM": "C", "CPI_YY": "D", "CORE_MM": "E", "CORE_YY": "F", "RAW_MM": "G",
        "RAW_YY": "H", "ADMX_MM": "I", "UTIL_MM": "J", "ADM_MM": "K", "ADM_YY": "L", "FUEL_MM": "M", "FUEL_YY": "N",
        "FX": "O", "FX_MM": "P", "FX_YY": "Q", "REB_MM": "R", "NBU_RAW_YY": "S", "NBU_ADM_YY": "T", "NBU_FUEL_YY": "U",
        "EXP_HH": "V", "EXP_ANALYSTS": "W", "EXP_BANKS": "X", "EXP_BUSINESS": "Y", "FLAG": "Z"}


def month_row(month: str) -> int:
    y, m = map(int, month.split("-"))
    y0, m0 = map(int, HIST_FIRST.split("-"))
    return T_FIRST + (y - y0) * 12 + (m - m0)
