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
    # external debt split: the first "Обслуговування" / "Погашення" rows after "Зовнішній борг"
    ext = False
    for r in rows[hi + 1:]:
        js = [j for j, v in enumerate(r) if isinstance(v, str) and v.strip()]
        if not js:
            continue
        lab = next((r[j].strip() for j in reversed(js) if isinstance(r[j], str)), "")
        if lab == "Зовнішній борг":
            ext = True
            continue
        key = {"Обслуговування": "external_interest", "Погашення": "external_repayment"}.get(lab)
        if ext and key and key not in out:
            j0 = max(j for j, v in enumerate(r) if isinstance(v, str) and v.strip() == lab)
            out[key] = {int(h): _num(_cell(r, j)) for j, h in enumerate(head)
                        if j > j0 and isinstance(h, (int, float)) and 2000 < h < 2100}
    df = pd.DataFrame(out)
    df.index.name = "year"
    return df.sort_index()


def _monthly_columns(path: Path, sheet: str, header_row: int, first_data_row: int, columns: dict[str, str]) -> pd.DataFrame:
    """Monthly table with year in column A and month in column C; `columns` maps a key to
    the start of its header text in row `header_row`."""
    rows = _rows(path, sheet)
    cols = {k: _col(rows[header_row], text) for k, text in columns.items()}
    out = {}
    for r in rows[first_data_row:]:
        y, mo = _num(_cell(r, 0)), _num(_cell(r, 2))
        if not (y and mo):
            continue
        vals = {k: _num(_cell(r, j)) for k, j in cols.items()}
        if any(v is not None for v in vals.values()):
            out[pd.Period(f"{int(y)}-{int(mo):02d}", "M")] = vals
    return pd.DataFrame.from_dict(out, orient="index").sort_index()


# CPI sheet: monthly indices to the previous month (101.8 = +1.8%), from 2010.
CPI_ITEMS = {
    "UTIL": "Житло, вода, електроенергія, газ",
    "ELEC": "Електроенергія",
    "GAS": "Природний газ",
    "HEAT": "Гаряча вода, опалення",
    "WATER": "Водопостачання",
    "FOOD": "Продукти харчування та безалкогольні",
    "ALC_TOB": "Алкогольні напої, тютюнові",
    "TRANSPORT": "Транспорт",
    "FUEL": "Паливо та мастила",
    "HEALTH": "Охорона здоров",
}


def _drop_copied_years(df: pd.DataFrame) -> pd.DataFrame:
    """Drop a year whose twelve months repeat the previous year cell for cell: the CPI
    sheet has 2012 pasted over with 2011."""
    years = sorted(set(df.index.year))
    bad = []
    for y in years[1:]:
        a, b = df[df.index.year == y - 1], df[df.index.year == y]
        if len(a) == len(b) == 12 and a.notna().any().any() and (a.values == b.values).all():
            bad.append(y)
    return df[~df.index.year.isin(bad)]


def cpi_items_mom(path: Path) -> pd.DataFrame:
    """CPI components, index to the previous month (=100), sheet CPI."""
    return _drop_copied_years(_monthly_columns(path, "CPI", 0, 4, CPI_ITEMS))


def cpi_extra_yoy(path: Path) -> pd.DataFrame:
    """Core CPI and PPI, y/y index (=100), sheet CPI; PPI here starts before the API (2013)."""
    return _monthly_columns(path, "CPI", 0, 4, {"CORE": "Базовий індекс y/y", "PPI": "Ціни виробників y/y"})


def industry_yoy_m(path: Path) -> pd.Series:
    """Industrial production index, % y/y (=100), sheet SectorIndexes M, from 2010."""
    rows = _rows(path, "SectorIndexes M")
    start = _col(rows[1], "Industrial production")
    c = start + [str(v).strip() if v else "" for v in rows[2][start:start + 3]].index("y/y")
    out = {}
    for r in rows[3:]:
        d, v = _cell(r, 3), _num(_cell(r, c))
        if isinstance(d, datetime) and v is not None:
            out[pd.Period(d, "M")] = v
    return pd.Series(out, dtype=float).sort_index()


# Budget sheet: consolidated budget, cumulative from January, UAH million, from 2011.
# key -> (block title prefix in column A, row label prefix in column B or budget code)
BUDGET_ROWS = {
    "REV_TOTAL": ("Доходи Зведеного", "Разом доходів"),
    "REV_PIT": ("Доходи Зведеного", 11010000),
    "REV_CIT": ("Доходи Зведеного", 11020000),
    "REV_VAT_DOM": ("Доходи Зведеного", 14060000),
    "REV_VAT_IMP": ("Доходи Зведеного", 14070000),
    "REV_EXC_DOM": ("Доходи Зведеного", 14020000),
    "REV_EXC_IMP": ("Доходи Зведеного", 14030000),
    "REV_GRANTS": ("Доходи Зведеного", 42000000),
    "EXP_TOTAL": ("Видатки Зведеного", "Усього видатків"),
    "EXP_DEFENCE": ("Видатки Зведеного", 200),
    "EXP_ORDER": ("Видатки Зведеного", 300),
    "EXP_ECON": ("Видатки Зведеного", 400),
    "EXP_HEALTH": ("Видатки Зведеного", 700),
    "EXP_EDU": ("Видатки Зведеного", 900),
    "EXP_SOCIAL": ("Видатки Зведеного", 1000),
    "EXP_WAGES": ("Видатки Зведеного", 2100),
    "EXP_INTEREST": ("Видатки Зведеного", 2400),
    "EXP_CAPITAL": ("Видатки Зведеного", 3000),
    "FIN_TOTAL": ("Фінансування Зведеного", "Фінансування (дефіцит"),
    "FIN_DOMESTIC": ("Фінансування Зведеного", 200000),
    "FIN_EXTERNAL": ("Фінансування Зведеного", 300000),
}


def budget_consolidated_ytd(path: Path) -> pd.DataFrame:
    """Consolidated budget items, cumulative from January, UAH million, monthly (sheet Budget).

    Rows are found inside their block (revenue, expenditure, financing) by budget code in
    column C or by label start in column B, so inserted rows do not shift them."""
    rows = _rows(path, "Budget")
    head = rows[0]
    months = {j: pd.Period(h, "M") for j, h in enumerate(head) if isinstance(h, datetime)}
    blocks = [i for i, r in enumerate(rows) if r and isinstance(r[0], str) and "кумулятивно" in r[0]]
    out = {}
    for key, (block, ident) in BUDGET_ROWS.items():
        b = next(i for i in blocks if rows[i][0].startswith(block))
        end = next((i for i in blocks if i > b), len(rows))
        i = next(i for i in range(b + 1, end)
                 if (isinstance(ident, int) and _num(_cell(rows[i], 2)) == ident)
                 or (isinstance(ident, str) and isinstance(_cell(rows[i], 1), str) and rows[i][1].strip().startswith(ident)))
        out[key] = {p: _num(_cell(rows[i], j)) for j, p in months.items()}
    return pd.DataFrame(out).sort_index()


AGRO_PRICES = {
    "WHEAT": "Ukraine Wheat 11.5% FOB",
    "BARLEY": "Ukraine Barley FOB",
    "SUNOIL": "Ukraine Crude Sunoil FOB",
    "SOY": "Ukraine Soybeans FOB",
}


def agro_export_prices_m(path: Path) -> pd.DataFrame:
    """Black Sea FOB export prices, USD per tonne, monthly (sheet AGROTrends, last price)."""
    rows = _rows(path, "AGROTrends")
    cols = {k: _col(rows[0], text) for k, text in AGRO_PRICES.items()}
    out = {}
    for r in rows[3:]:
        d = _cell(r, 0)
        if isinstance(d, str):
            try:
                d = datetime.strptime(d.strip(), "%d.%m.%Y")
            except ValueError:
                continue
        if not isinstance(d, datetime):
            continue
        out[pd.Period(d, "M")] = {k: _num(_cell(r, j)) for k, j in cols.items()}
    return pd.DataFrame.from_dict(out, orient="index").sort_index()
