"""State and guaranteed debt, month-end, from index.minfin.com.ua.

The site republishes the Ministry of Finance debt statistics (mof.gov.ua itself blocks
cloud addresses). One page per year, table of month-end totals in million UAH.
"""
import io
import re
import time

import pandas as pd
import requests

URL = "https://index.minfin.com.ua/ua/finance/debtgov/{year}/"


def _num(x) -> float:
    return float(str(x).replace("\xa0", "").replace(" ", "").replace(",", "."))


def debt_month_end(start_year: int, end_year: int) -> pd.DataFrame:
    """Columns total / external / domestic (million UAH), monthly PeriodIndex."""
    out = {}
    for y in range(start_year, end_year + 1):
        r = requests.get(URL.format(year=y), headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        if r.status_code == 404:
            continue
        r.raise_for_status()
        table = pd.read_html(io.StringIO(r.text))[0]
        for _, row in table.iterrows():
            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(row.iloc[0]))
            if not m:
                continue
            p = pd.Period(f"{m[3]}-{m[2]}", "M")
            out[p] = {"total": _num(row.iloc[1]), "external": _num(row.iloc[5]), "domestic": _num(row.iloc[8])}
        time.sleep(0.5)
    return pd.DataFrame.from_dict(out, orient="index").sort_index()
