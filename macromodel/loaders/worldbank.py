"""World Bank Indicators API: annual fallbacks and cross-checks.

Used where the NBU API has no series (population, capital consumption, electricity
use) or stops (labour force survey after 2021). Values are for Ukraine as the World
Bank reports it, which is not always the government-controlled territory.

Reference: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""
import time

import pandas as pd
import requests

URL = "https://api.worldbank.org/v2/country/{country}/indicator/{code}"

INDICATORS = {
    "SP.POP.TOTL": "Population, total",
    "SL.UEM.TOTL.ZS": "Unemployment, % of labour force (ILO modelled)",
    "SL.TLF.TOTL.IN": "Labour force, total",
    "NY.ADJ.DKAP.GN.ZS": "Consumption of fixed capital, % of GNI",
    "NY.GNP.MKTP.CN": "GNI, current UAH",
    "NY.GDP.MKTP.CN": "GDP, current UAH",
    "EG.USE.ELEC.KH.PC": "Electric power consumption, kWh per capita",
    "GC.DOD.TOTL.GD.ZS": "Central government debt, % of GDP",
}


def indicator(code: str, country: str = "UKR", start: int = 2000, tries: int = 4) -> pd.Series:
    """Annual values of `code`, indexed by year (int). The API drops requests now and then."""
    for i in range(tries):
        try:
            r = requests.get(URL.format(country=country, code=code),
                             params={"format": "json", "date": f"{start}:2100", "per_page": 200}, timeout=60)
            r.raise_for_status()
            meta, rows = r.json()
            break
        except (requests.RequestException, ValueError):
            if i == tries - 1:
                raise
            time.sleep(2 ** (i + 1))
    s = pd.Series({int(x["date"]): x["value"] for x in rows or [] if x["value"] is not None}, dtype=float)
    s.name = code
    return s.sort_index()
