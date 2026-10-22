"""Bank loans and deposits from the NBU depository corporations survey (Огляди ДК, xlsx).

Sheet 'Дод_показники_динаміка' has month-end stocks of loans to and deposits of
residents by sector and currency since 2013M12. The cloud environment cannot always
reach bank.gov.ua, so the file is read from data/raw/manual/nbu_dk.xlsx (Andrey's
upload of the NBU file). Rows are found by label; sub-rows ('у національній валюті')
repeat, so they are taken by their offset under the sector row.
"""
from pathlib import Path

import openpyxl
import pandas as pd

from macromodel.aggregate import to_quarter

SHEET = "Дод_показники_динаміка"

# code -> (label the block starts with, sector row label or None, offset of the row under it)
ROWS = {
    "LOANS": ("Кредити, надані резидентам", None, 0),
    "LOANS_CORP_UAH": ("Кредити, надані резидентам", "корпоративний сектор", 1),
    "LOANS_HH_UAH": ("Кредити, надані резидентам", "домашні господарства", 1),
    "DEPOSITS": ("Депозити, залучені", None, 0),
    "DEP_CORP_UAH": ("Депозити, залучені", "корпоративний сектор", 1),
    "DEP_HH_UAH": ("Депозити, залучені", "домашні господарства", 1),
}


def _month(label) -> pd.Timestamp | None:
    if isinstance(label, str) and "M" in label:
        y, m = label.split("M")
        if y.isdigit() and m.isdigit():
            return pd.Timestamp(int(y), int(m), 1) + pd.offsets.MonthEnd(0)
    return None


def monthly(path: Path) -> pd.DataFrame:
    """Month-end stocks, UAH million."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[SHEET].iter_rows(values_only=True))
    wb.close()
    header = next(r for r in rows if _month(r[1]) is not None)
    dates = [(j, _month(v)) for j, v in enumerate(header) if _month(v) is not None]
    labels = [str(r[0] or "").strip() for r in rows]
    out = {}
    for code, (block, sector, off) in ROWS.items():
        i = next(k for k, t in enumerate(labels) if t.startswith(block))
        if sector:
            i = next(k for k in range(i + 1, len(labels)) if labels[k].startswith(sector))
        row = rows[i + off]
        out[code] = pd.Series({d: row[j] for j, d in dates if isinstance(row[j], (int, float))}, dtype=float)
    m = pd.DataFrame(out)
    m["LOANS_UAH"] = m["LOANS_CORP_UAH"] + m["LOANS_HH_UAH"]
    m["DEP_UAH"] = m["DEP_CORP_UAH"] + m["DEP_HH_UAH"]
    return m


def quarterly(path: Path) -> pd.DataFrame:
    """Quarter-end stocks, UAH million, indexed '2024Q3'."""
    m = monthly(path)
    q = pd.DataFrame({c: to_quarter(m[c], "END") for c in m})
    last = m.index.max()
    if last.month % 3:  # drop a quarter whose last month is not out yet
        q = q.drop(str(last.to_period("Q")))
    return q
