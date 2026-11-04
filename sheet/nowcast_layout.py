"""Row and column layout of the NOWCAST sheet (shared by nowcast_payload and b1_payload)."""
from macromodel.nowcast import BRIDGE, IND


def col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


MONTHS = [f"{y}-{m:02d}" for y in range(2025, 2029) for m in range(1, 13)]
QUARTERS = [f"{y}Q{q}" for y in range(2025, 2029) for q in range(1, 5)]
MCOL = {m: col(3 + i) for i, m in enumerate(MONTHS)}        # D = 2025-01 .. AY = 2028-12
QCOL = {q: col(3 + i) for i, q in enumerate(QUARTERS)}      # D = 2025Q1 .. S = 2028Q4
FIRST_FC = "2026Q3"                                          # first quarter without Gosstat GDP
FC = [q for q in QUARTERS if q >= FIRST_FC]
INDS = list(IND)
SECTORS = list(BRIDGE)
B1_ROW = {"A": 35, "B": 36, "C": 37, "D": 38, "F": 39, "G": 40, "H": 41}  # B1_REAL section 3 levels
B1_ANNUAL = {s: r - 16 for s, r in B1_ROW.items()}                         # B1_REAL section 2 growth (rows 19..)
B1_CORR = {"B": 126, "C": 127, "D": 128, "H": 129}                         # B1_REAL section 8 quarter corrections

# section 1: monthly, section 1 header row 5, rows 6..
M_HDR = 5
M_ROW = {n: M_HDR + 1 + i for i, n in enumerate(INDS)}
# section 2: quarterly indicator
Q_HDR = M_HDR + len(INDS) + 3
Q_ROW = {n: Q_HDR + 1 + i for i, n in enumerate(INDS)}
# section 3: bridges and backtest
B_HDR = Q_HDR + len(INDS) + 3
B_ROW = {s: B_HDR + 1 + i for i, s in enumerate(SECTORS)}
# section 4: nowcast and fade, 6 rows per sector (5 + blank)
N_HDR = B_HDR + len(SECTORS) + 4
N_FIRST = N_HDR + 1
N_KEYS = ["NC", "EQ", "DEV", "AF", "RES"]
N_ROW = {s: {k: N_FIRST + 6 * i + j for j, k in enumerate(N_KEYS)} for i, s in enumerate(SECTORS)}
AF_ROW = {s: N_ROW[s]["AF"] for s in SECTORS}
# section 5: flash GDP check; section 6: PPI by quarter
F_HDR = N_FIRST + 6 * len(SECTORS) + 1
F_ROW = {"MODEL": F_HDR + 1, "FLASH": F_HDR + 2, "DIFF": F_HDR + 3, "FLAG": F_HDR + 4}
P_HDR = F_HDR + 7
P_ROW = {"FACT": P_HDR + 1, "B3": P_HDR + 2, "USED": P_HDR + 3}
LAST_ROW = P_HDR + 5

COEF_FIRST = 259
COEF_ROW = {}
for i, s in enumerate(SECTORS):
    for j, v in enumerate(("a", "b", "rho")):
        COEF_ROW[(s, v)] = COEF_FIRST + 3 * i + j
COEF_ROW[("PPI", "rho")] = COEF_FIRST + 3 * len(SECTORS)
PLATEAU = ("B",)   # sectors on the war plateau: level of the last nowcast quarter, moved only by seasonality
for i, k in enumerate(range(1, 5)):
    COEF_ROW[("B", f"s{k}")] = COEF_ROW[("PPI", "rho")] + 1 + i
