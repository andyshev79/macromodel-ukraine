"""NBU loaders: official exchange rate via the open API and raw statistical files.

API reference: https://bank.gov.ua/ua/open-data/api-dev
"""
from datetime import date
from pathlib import Path

import pandas as pd
import requests

EXCHANGE_URL = "https://bank.gov.ua/NBU_Exchange/exchange_site"

# Files Andrey keeps in MacroStat ("Ссылки"). Parsers come after the first download,
# once the layout of each file is checked.
RAW_FILES = {
    "interventions": "https://bank.gov.ua/files/Finmarket/InterventionsResults.xlsx",
    "liquidity_ops": "https://bank.gov.ua/files/PInterestRates_Facts.xls",
    "corr_accounts": "https://bank.gov.ua/files/Vzal.xlsx",
    "financial_markets": "https://bank.gov.ua/files/4-Financial_markets.xlsx",
    "term_deposit_rates": "https://bank.gov.ua/files/Inter_r_term_dep.xlsx",
    "ovdp_outstanding": "https://bank.gov.ua/files/Depositary/T-bills_debt.xlsx",
    "monetary_aggregates": "https://bank.gov.ua/files/SDDS/AA_BS.xlsx",
    "fx_market": "https://bank.gov.ua/files/rates_final.xlsx",
    "fx_client_ops": "https://bank.gov.ua/files/Volue.xls",
}


def exchange_rate(start: date, end: date, valcode: str = "usd") -> pd.Series:
    """Daily official UAH rate per one unit of `valcode`, one request per year."""
    parts = []
    for y in range(start.year, end.year + 1):
        a = max(start, date(y, 1, 1))
        b = min(end, date(y, 12, 31))
        r = requests.get(EXCHANGE_URL, params={
            "start": a.strftime("%Y%m%d"), "end": b.strftime("%Y%m%d"),
            "valcode": valcode, "sort": "exchangedate", "order": "asc", "json": "",
        }, timeout=60)
        r.raise_for_status()
        parts.extend(r.json())
    df = pd.DataFrame(parts)
    s = pd.Series(df["rate_per_unit"].astype(float).values,
                  index=pd.to_datetime(df["exchangedate"], dayfirst=True), name=f"{valcode.upper()}UAH")
    return s.sort_index()


def download_raw(dest: Path) -> dict[str, Path]:
    """Download every file in RAW_FILES into `dest`; returns name -> saved path."""
    dest.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, url in RAW_FILES.items():
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path = dest / f"nbu_{name}{Path(url).suffix}"
        path.write_bytes(r.content)
        saved[name] = path
    return saved
