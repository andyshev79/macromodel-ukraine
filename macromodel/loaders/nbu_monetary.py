"""NBU monetary survey, operational data (ms_oper.xlsx): monetary base, NBU certificates
of deposit, net international reserves. These are the liquidity series the statistical
API does not carry. The file is replaced every month at the same address.
"""
import re
from pathlib import Path

import openpyxl
import pandas as pd
import requests

URL = "https://bank.gov.ua/files/ms_oper.xlsx"
SHEETS = ["Огляд_ДК_динаміка_2013-2022", "Огляд_ДК_динаміка з 2022"]

# code -> row label prefix in the NBU survey block (first match is the NBU's own row)
ROWS = {
    "MONETARY_BASE": "Грошова база",
    "NBU_CD": "Депозитні сертифікати НБУ",
    "NIR_USD": "Чисті міжнародні резерви",
    "BANK_RESERVES": "Резервні кошти банків",
}


def download(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=120)
    r.raise_for_status()
    path = dest / "nbu_ms_oper.xlsx"
    path.write_bytes(r.content)
    return path


def month_end(path: Path) -> pd.DataFrame:
    """End-of-month stocks (UAH million; NIR in USD million), monthly PeriodIndex."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    frames = []
    for name in SHEETS:
        rows = list(wb[name].iter_rows(values_only=True))
        hi = next(i for i, r in enumerate(rows) if any(isinstance(v, str) and re.fullmatch(r"\d{4}[MМ]\d{1,2}", v.strip()) for v in r))
        cols = {j: pd.Period(re.sub("М", "M", v.strip()).replace("M", "-"), "M") for j, v in enumerate(rows[hi])
                if isinstance(v, str) and re.fullmatch(r"\d{4}[MМ]\d{1,2}", v.strip())}
        data = {}
        for code, label in ROWS.items():
            r = next(r for r in rows[hi + 1:] if isinstance(r[0], str) and r[0].strip().startswith(label))
            data[code] = {p: r[j] for j, p in cols.items() if isinstance(r[j], (int, float))}
        frames.append(pd.DataFrame(data))
    wb.close()
    df = pd.concat(frames)
    return df[~df.index.duplicated(keep="last")].sort_index()
