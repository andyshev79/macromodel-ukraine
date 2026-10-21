"""Series from Andrey's MacroStat workbook (an .xlsx export of the Google sheet).

MacroStat fills gaps the public APIs leave: Gosstat quarterly wages for 2022-2024,
monthly freight, gross external financing by donor and the MinFin debt payment
schedule. The file is personal and large, so it is not committed: put the export at
data/raw/manual/MacroStat.xlsx. Columns are found by their header text, not position,
so moving columns in the sheet does not break the loader as long as headers stay.
"""
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import openpyxl
import pandas as pd

MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


@lru_cache(maxsize=None)
def _rows(path: Path, sheet: str) -> list[tuple]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    return rows


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _cell(row: tuple, j: int):
    return row[j] if j < len(row) else None


def _col(header: tuple, text: str) -> int:
    for j, v in enumerate(header):
        if isinstance(v, str) and v.strip().startswith(text):
            return j
    raise KeyError(f"no column starting with {text!r}")


def wages_q(path: Path) -> pd.Series:
    """Average nominal wage per quarter, UAH (sheet Salary, column 'Salary Q grn')."""
    rows = _rows(path, "Salary")
    c = _col(rows[0], "Salary Q grn")
    out = {}
    for r in rows[1:]:
        y, q, v = _num(_cell(r, 0)), _num(_cell(r, 1)), _num(_cell(r, c))
        if y and q and v:
            out[f"{int(y)}Q{int(q)}"] = v
    return pd.Series(out, dtype=float).sort_index()


def registered_unemployed_m(path: Path) -> pd.Series:
    """Registered unemployed at month end, thousand persons (State Employment Service)."""
    rows = _rows(path, "Salary")
    c = _col(rows[0], "Кількість зареєстрованих безробітних")
    out = {}
    for r in rows[1:]:
        y, m, v = _num(_cell(r, 0)), _num(_cell(r, 2)), _num(_cell(r, c))
        if y and m and v is not None:
            out[pd.Period(f"{int(y)}-{int(m):02d}", "M")] = v
    return pd.Series(out, dtype=float).sort_index()


def freight_m(path: Path) -> pd.Series:
    """Freight carried per month, million tonnes (sheet SectorIndexes M)."""
    rows = _rows(path, "SectorIndexes M")
    start = _col(rows[1], "Перевозка грузов")
    c = start + [str(v).strip() for v in rows[2][start:start + 4]].index("млн т в міс")
    out = {}
    for r in rows[3:]:
        d, v = _cell(r, 3), _num(_cell(r, c))
        if isinstance(d, datetime) and v is not None:
            out[pd.Period(d, "M")] = v
    return pd.Series(out, dtype=float).sort_index()


def external_financing_q(path: Path) -> pd.Series:
    """Gross external financing received, USD million per quarter (sheet Help, row TOTAL).

    The header row mixes two layouts: annual blocks (year, two empty cells, total in the
    third column) for 2022-2023, then runs of month columns closed by their year
    (January and February share one column). Annual blocks are spread evenly over
    quarters; years with month columns are summed by quarter. Plan columns for future
    years have neither layout and are skipped.
    """
    rows = _rows(path, "Help")
    head = next(r for r in rows if r and r[0] == "US$, m")
    total = next(r for r in rows if r and r[0] == "TOTAL")
    out: dict[str, float] = {}
    pending: list[tuple[int, int]] = []  # (column, month) waiting for their year label
    for j, h in enumerate(head):
        if isinstance(h, str):
            key = h.strip().lower()
            if key == "янв-фев":
                pending.append((j, 2))
            elif key in MONTHS_RU:
                pending.append((j, MONTHS_RU.index(key) + 1))
            continue
        if not (isinstance(h, (int, float)) and 2000 < h < 2100):
            continue
        year = int(h)
        if pending:
            for col, m in pending:
                v = _num(_cell(total, col))
                if v is not None:
                    k = f"{year}Q{(m - 1) // 3 + 1}"
                    out[k] = out.get(k, 0.0) + v
            pending = []
        elif _cell(head, j + 1) is None and _cell(head, j + 2) is None and f"{year}Q1" not in out:
            v = _num(_cell(total, j + 2))
            if v is not None:
                for qn in range(1, 5):
                    out[f"{year}Q{qn}"] = v / 4
    return pd.Series(out, dtype=float).sort_index()


def debt_payments_m(path: Path) -> pd.DataFrame:
    """Monthly state debt payments, UAH billion (sheet Debt): total, domestic, external,
    external interest and external repayment. Months after the publication date are the
    MinFin schedule, not actual payments."""
    rows = _rows(path, "Debt")
    hi = next(i for i, r in enumerate(rows) if any(isinstance(v, datetime) for v in r))
    head = rows[hi]
    labels = [str(r[0]).strip() if r and r[0] else "" for r in rows]
    i_total = labels.index("ВСЬОГО")
    i_dom = labels.index("Внутрішній борг")
    i_ext = labels.index("Зовнішній борг")
    i_ext_int = labels.index("Обслуговування", i_ext)
    i_ext_rep = labels.index("Погашення", i_ext)
    cols = {"total": i_total, "domestic": i_dom, "external": i_ext,
            "external_interest": i_ext_int, "external_repayment": i_ext_rep}
    out = {}
    for j, h in enumerate(head):
        if isinstance(h, datetime):
            out[pd.Period(h, "M")] = {k: _num(_cell(rows[i], j)) for k, i in cols.items()}
    df = pd.DataFrame.from_dict(out, orient="index").sort_index()
    # The sheet has typos in the external split (e.g. 45607 instead of ~45.6), while
    # total and domestic are consistent; derive external from them and drop splits that
    # do not add up.
    df["external"] = df["total"] - df["domestic"]
    bad = (df["external_interest"] + df["external_repayment"] - df["external"]).abs() > 1
    df.loc[bad, ["external_interest", "external_repayment"]] = float("nan")
    return df


def debt_schedule_y(path: Path) -> pd.DataFrame:
    """Annual debt payment schedule, UAH billion, from the far-right block of sheet Debt
    (the block starts where the row label 'ВСЬОГО' repeats last)."""
    rows = _rows(path, "Debt")
    hi = next(i for i, r in enumerate(rows) if any(isinstance(v, datetime) for v in r))
    head = rows[hi]
    labels = {"ВСЬОГО": "total", "Внутрішній борг": "domestic", "Зовнішній борг": "external"}
    out = {}
    for r in rows[hi + 1:]:
        for lab, key in labels.items():
            js = [j for j, v in enumerate(r) if isinstance(v, str) and v.strip() == lab]
            if key in out or not js:
                continue
            start = js[-1]
            out[key] = {int(h): _num(_cell(r, j)) for j, h in enumerate(head)
                        if j > start and isinstance(h, (int, float)) and 2000 < h < 2100}
    df = pd.DataFrame(out)
    df.index.name = "year"
    return df.sort_index()
