"""Row layout of B8_CAPACITY section 3 (recovery after downtime and destruction), shared by the payloads.

SCENARIOS reads the effective (after-recovery) paths of metallurgy and ports from here, so this module has no imports.
"""
R0 = 30  # section title
HDR = R0 + 2  # quarter labels: C = first half 2026, D:M = 2026Q3..2028Q4, N:Q = 2025..2028 averages
QN = R0 + 3  # quarter number (year × 4 + quarter)
BLOCK = 15  # rows per scenario
SC_FIRST = QN + 1  # first scenario block
IND = ("MET", "PORTS")  # industries with a downtime path in SCENARIOS
SUB = {"PAR": 1, "IN": 2, "BOUND": 3, "CEIL": 4, "EFF": 5, "BIND": 6}  # rows inside an industry group (after the K row)


def sc_row(s: int) -> int:
    """K row (quarters since the ceasefire) of scenario s: 0 Base, 1 Pess, 2 Opt."""
    return SC_FIRST + BLOCK * s


def ind_row(s: int, ind: str, part: str) -> int:
    return sc_row(s) + 6 * IND.index(ind) + SUB[part]


def chem_row(s: int) -> int:
    return sc_row(s) + 13


ACT0 = SC_FIRST + 3 * BLOCK  # active-scenario block title
ACT = {k: ACT0 + 1 + i for i, k in enumerate(["K", "MET", "PORTS", "CHEM", "ORE", "ORE_D", "ORE_DY", "ORE_XTRA"])}
LAST = ACT["ORE_XTRA"] + 1  # note row
EFF_ROWS = {ind: [ind_row(s, ind, "EFF") for s in range(3)] for ind in IND}  # SCENARIOS annual rows read these
