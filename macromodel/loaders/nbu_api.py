"""NBU statistical API (NBUStatService): the main source of model history.

Besides its own data (rates, money, balance of payments, reserves, external debt) the
NBU republishes Gosstat and Treasury series through the same API: GDP by production
and expenditure, CPI/PPI, wages, labour force survey, industry, retail, construction,
state budget execution. stat.gov.ua and mof.gov.ua block cloud addresses, so this API
is how the model reads Gosstat and MinFin data.

Reference: https://bank.gov.ua/ua/open-data/api-dev

Conventions worth knowing:
- `dt` is the reporting date, the first day after the period. For monthly, quarterly
  and annual rows the period is the one that ends the day before `dt`
  (dt=20150401, freq=Q means 2015Q1). Daily rows (`key`) carry the actual day.
- Every row has `id_api` (indicator), `tzep` (measure) and dataset-specific dimension
  columns; `select()` filters on any of them.
- Large datasets refuse long ranges, so requests go one calendar year at a time.
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE = "https://bank.gov.ua/NBUStatService/v1/statdirectory"

# name -> (endpoint, fixed query params). Filters cut the interest-rate tables, which
# otherwise run to ~50k rows a month.
DATASETS = {
    "gdp_q": ("economicactivity", {"period": "q"}),
    "activity_m": ("economicactivity", {"period": "m"}),
    "prices_m": ("inflation", {"period": "m"}),
    "labour_m": ("labormarket", {"period": "m"}),
    "labour_q": ("labormarket", {"period": "q"}),
    "budget_m": ("budget", {"period": "m"}),
    "bop_m": ("balanceofpayments", {}),
    "reserves_m": ("res", {}),
    "ext_debt_q": ("grossextdebt", {}),
    "money_m": ("monetary", {}),
    "key_rates_d": ("key", {}),
    "fx_market_m": ("kursf", {"period": "m"}),
    "loan_rates_m": ("mir", {"id_api": "New_Loans_Res,New_Loans_NFinCorp,New_Loans_Households",
                             "odkodter": "total", "ods180": "total", "odk111": "total",
                             "odf074": "total"}),
    "dep_rates_m": ("mir", {"id_api": "New_Deposits_Res,New_Deposits_NFinCorp,New_Deposits_Households",
                            "odkodter": "total", "ods180": "total", "odk111": "total",
                            "odf074": "total"}),
}

_SKIP = {"dt", "txt", "value", "leveli", "level", "parent"}


def _get(endpoint: str, params: dict) -> list:
    r = requests.get(f"{BASE}/{endpoint}", params={**params, "json": ""}, timeout=600)
    data = r.json()
    if isinstance(data, dict):  # API errors come back as {"message": ...}
        if "не знайдено" in data.get("message", ""):
            return []
        raise RuntimeError(f"{endpoint} {params}: {data.get('message')}")
    return data


def _get_filtered(endpoint: str, params: dict) -> list:
    # The API takes one value per filter, so comma lists become separate calls.
    multi = {k: v for k, v in params.items() if isinstance(v, str) and "," in v}
    if not multi:
        return _get(endpoint, params)
    (k, v), = multi.items()
    rows = []
    for one in v.split(","):
        rows += _get(endpoint, {**params, k: one})
    return rows


def fetch(name: str, start_year: int, end_year: int, cache: Path, refresh_from: int | None = None) -> pd.DataFrame:
    """Rows of dataset `name` for reporting dates in [start_year, end_year].

    Each year is cached as JSON in `cache`; years >= `refresh_from` are downloaded again
    because recent figures get revised.
    """
    endpoint, fixed = DATASETS[name]
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(start_year, end_year + 1):
        path = cache / f"{name}_{y}.json"
        if path.exists() and (refresh_from is None or y < refresh_from):
            part = json.loads(path.read_text(encoding="utf-8"))
        else:
            params = {**fixed, "start": f"{y}0101", "end": f"{y}1231"}
            part = _get_filtered(endpoint, params)
            path.write_text(json.dumps(part, ensure_ascii=False), encoding="utf-8")
        rows += part
    return to_frame(rows)


def to_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["period"] = [period_of(dt, f) for dt, f in zip(df["dt"], df["freq"])]
    return df


def period_of(dt: str, freq: str) -> pd.Period:
    """Map a reporting date to the period it describes (see module docstring)."""
    d = pd.Timestamp(dt)
    if freq == "D":
        return d.to_period("D")
    return (d - pd.Timedelta(days=1)).to_period({"M": "M", "Q": "Q", "Y": "Y"}[freq])


def select(df: pd.DataFrame, id_api: str, tzep: str, freq: str | None = None, **dims) -> pd.Series:
    """One series from a dataset frame, indexed by period.

    `freq` is needed where a dataset mixes frequencies (balance of payments carries
    monthly, quarterly and annual rows). Dimension values are compared as strings; an
    unknown dimension column raises instead of silently returning everything.
    """
    m = (df["id_api"] == id_api) & (df["tzep"] == tzep)
    if freq:
        m &= df["freq"] == freq
    for k, v in dims.items():
        col = df[k].where(df[k].notna(), "None").astype(str)
        m &= col == str(v)
    s = df[m]
    if s.empty:
        raise KeyError(f"no rows for {id_api}/{tzep} {dims}")
    s = s.drop_duplicates("period", keep="last").set_index("period")["value"]
    s.index = pd.PeriodIndex(s.index)  # mixed-frequency datasets leave a plain object index
    s = s.sort_index()
    s.name = id_api
    return s


def dims(df: pd.DataFrame) -> list[str]:
    """Dimension columns of a dataset frame, for exploring what `select` can filter."""
    return [c for c in df.columns if c not in _SKIP | {"period", "freq", "txten", "id_api", "tzep"}]
