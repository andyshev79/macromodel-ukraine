"""World commodity prices.

Brent crude, USD per barrel, monthly average (EIA series RBRTE), from the
datasets/oil-prices mirror on GitHub: EIA, FRED and the World Bank Pink Sheet are not
reachable from the cloud environment.
"""
from pathlib import Path

import pandas as pd
import requests

BRENT_URL = "https://raw.githubusercontent.com/datasets/oil-prices/main/data/brent-monthly.csv"


def brent_m(cache: Path, refresh: bool) -> pd.Series:
    p = cache / "brent-monthly.csv"
    if refresh or not p.exists():
        r = requests.get(BRENT_URL, timeout=120)
        r.raise_for_status()
        p.write_bytes(r.content)
    d = pd.read_csv(p)
    s = pd.Series(d.iloc[:, 1].astype(float).values, index=pd.PeriodIndex(d.iloc[:, 0].str[:7], freq="M"))
    return s.sort_index()
