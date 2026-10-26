"""Gosstat (stat.gov.ua) open SDMX API: the data behind stat.gov.ua/uk/explorer.

No key is needed. The registry lists ~120 dataflows (agency SSSU); each has a data
structure with an ordered list of dimensions, and a query names one value (or several
joined by "+", or "*" for all) per dimension.

Conventions worth knowing:
- Data comes as SDMX-CSV only with the Accept header below; "?format=csv" sometimes
  returns XML instead.
- Whole large dataflows fail on the server (PHP memory error, a cut stream or a 504), so
  every set here is narrowed by key: national total, the needed indicators, bases and
  frequency. Sets that are still big are fetched year by year with c[TIME_PERIOD].
- TIME_PERIOD is "2026-M09", "2026-Q2" or "2026"; period() turns it into "2026-09",
  "2026Q2", "2026" (pandas Period strings).
- Gosstat revises past values (national accounts, wages, indices). fetch() always takes the
  full history of a set, and revisions() compares two snapshots so that every change to an
  already published value is recorded (scripts/fetch_ukrstat.py keeps the log).
"""
import io
import time
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import requests

REGISTRY = "https://stat.gov.ua/sdmx/workspaces/default:integration/registry/sdmx/3.0"
CSV = {"Accept": "application/vnd.sdmx.data+csv;version=2.0.0"}
UA = "UA00000000000000000"  # REGION code of Ukraine as a whole
# SDMX-CSV columns that are not dimensions
ATTRS = {"STRUCTURE", "STRUCTURE_ID", "ACTION", "DATAFLOW", "TIME_PERIOD", "OBS_VALUE", "UNITS_OF_MEASURE",
         "SCALE", "DECIMALS_DISPLAYED", "OBS_FLAG", "NOTES_DS", "NOTES_TS", "NOTES_OBS", "DSS_CODE",
         "TERRITORIAL_COVERAGE", "FREQUENCIES", "DSS_TYPE", "DYNAMICS", "UPDATED", "NEXT_UPDATE", "MAIN_INDICATORS"}


@dataclass
class Set:
    flow: str
    name: str  # what the model uses it for
    key: dict = field(default_factory=dict)  # dimension -> code or [codes]; missing dimensions are "*"
    by_year: int | None = None  # monthly sets too big for one request: years before this one, then year by year


SETS = {
    "gdp_q": Set("DF_QUARTERLY_NATIONAL_ACCOUNTS", "ВВП и ВДС по КВЭД, ВВП по расходам: текущие, постоянные цены 2021, индексы объёма, дефлятор",
                 {"REGION": UA}),
    "cpi_m": Set("DF_PRICE_CHANGE_CONSUMER_GOODS_SERVICE", "ИПЦ по группам и базовая инфляция: к предыдущему месяцу и г/г",
                 {"INDICATOR": ["INDEX_CONSUMPRICE", "CORE_INFL"], "BASE_PERIOD": ["PREV_MONTH", "CORMONTH_PREV_YEAR"],
                  "REGION": UA, "FREQ": "M"}, by_year=2000),
    "ppi_m": Set("DF_PRICE_CHANGE_MANUFACTURER_INDUSTRIAL_PRODUCT", "ИЦП промышленности по КВЭД и группам: к предыдущему месяцу и г/г",
                 {"INDICATOR": "INDEX_PRODPRICE", "REGION": UA, "BASE_PERIOD": ["PREV_MONTH", "CORMONTH_PREV_YEAR"],
                  "DISTRIBUTION": "DIST_0", "FREQ": "M"}),
    "industry_m": Set("DF_IND_SHORT_STAT_INDUSTR_PROD", "Индекс промышленной продукции по КВЭД: м/м, г/г, сезонно скорректированный",
                      {"INDICATOR": "INDX_IND_PROD", "BASE": ["UNADJ_PREV_MONTH", "UNADJ_CORR_MON_PREV_Y", "ADJ_AVG_M_VAL_SEAS_CALEN"],
                       "REGION": UA, "FREQ": "M"}, by_year=2013),
    "construction_m": Set("DF_ECONOM_INDC_SHORT-TERM_CONSTRUCTION_STAT", "Строительная продукция: объём, индексы, по видам и характеру строительства",
                          {"REGION": UA}),
    "construction_prices": Set("DF_PRICE_CHANGE_CONSTRUCTION", "Индексы цен в строительстве по видам",
                               {"REGION": UA, "BASE_PERIOD": ["PREV_MONTH", "CORMONTH_PREV_YEAR", "PREV_QUART",
                                                              "CORQUART_PREV_YEAR", "PREV_YEAR"]}),
    "retail_m": Set("DF_SALE_AND_STOCKS_OF_GOODS_RETAIL_M", "Оборот розничной торговли: объём и индексы в сопоставимых ценах",
                    {"REGION": UA}),
    "agro": Set("DF_AGRICULTURAL_PRODUCTS_AT_CONSTANT_PRICES", "Индекс сельхозпродукции: растениеводство, животноводство, предприятия и хозяйства",
                {"REGION": UA}),
    "wages_m": Set("DF_ENTERPRISE_LABOR_STATISTICS", "Средняя зарплата, фонд оплаты труда, штатные работники по КВЭД (месяц)",
                   {"INDICATOR": ["AVG_SALARY_UAH", "AVG_MTH_SALARY_UAH", "WAGE_FUND_ALL_EMPL", "WAGE_FUND_EMPL", "REG_WKRS_AVG_NUM"],
                    "REGION": UA, "BREAKDOWN": "_T", "FREQ": "M"}),
    "wages_q": Set("DF_ENTERPRISE_LABOR_STATISTICS", "Средняя зарплата, фонд оплаты труда, штатные и внештатные работники по КВЭД (квартал)",
                   {"INDICATOR": ["AVG_MTH_SALARY_UAH", "WAGE_FUND_EMPL", "REG_WKRS_AVG_NUM", "NREG_WKRS_CIV_LEG_AVG_NUM",
                                  "NREG_WKRS_EXT_SEC_AVG_NUM", "EMP_NUM_UNP_LVE", "EMP_NUM_PRT_TME_ECN_REAS"],
                    "REGION": UA, "BREAKDOWN": "_T", "FREQ": "Q"}),
    "capinv_q": Set("DF_CAPITAL_INVESTMENTS_Q", "Капитальные инвестиции: сумма и индекс, по КВЭД",
                    {"INDICATOR": ["CAP_INV_UAH", "IDX_CAP_INV_PERC"], "REGION": UA, "BREAKDOWN_CATEGORY": "_T",
                     "COST_DIRECTION": "_T", "FREQ": "Q"}),
    "freight_m": Set("DF_GROUND_TRANSPORT_M", "Грузы ж/д и автотранспорта: тонны и тонно-км по видам грузов",
                     {"INDICATOR": ["VOL_FRGT_TRF_TONS", "CARG_TRNVR_TON_KM"], "REGION": UA}),
    "housing_prices_q": Set("DF_PRICE_CHANGE_HOUSING_MARKET", "Индексы цен на жильё", {"REGION": UA}),
    "service_prices_q": Set("DF_PRICE_CHANGES_OF_SERVICE_PRODUCERS", "Индексы цен производителей услуг, тарифы на грузоперевозки",
                            {"REGION": UA}),
    "trade_m": Set("DF_EXTERNAL_TRADE_OF_GOODS_IMF", "Экспорт и импорт товаров (стандарт СДДС МВФ)", {}),
}


def _get(url: str, headers: dict | None = None, tries: int = 4) -> requests.Response:
    for i in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=600)
            if r.status_code < 500:
                r.raise_for_status()
                return r
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.Timeout):
            if i == tries - 1:
                raise
        time.sleep(2 ** (i + 1))
    r.raise_for_status()
    return r


def versions() -> dict[str, str]:
    """Dataflow id -> current version; Gosstat bumps versions when it changes a structure."""
    flows = _get(f"{REGISTRY}/structure/dataflow").json()["data"]["dataflows"]
    return {f["id"]: f["version"] for f in flows if f["agencyID"] == "SSSU"}


def dimensions(flow: str, version: str) -> list[str]:
    s = _get(f"{REGISTRY}/structure/dataflow/SSSU/{flow}/{version}?references=datastructure").json()
    return [d["id"] for d in s["data"]["dataStructures"][0]["dataStructureComponents"]["dimensionList"]["dimensions"]]


def key(dims: list[str], spec: dict) -> str:
    unknown = set(spec) - set(dims)
    if unknown:
        raise KeyError(f"no such dimensions: {sorted(unknown)} (structure has {dims})")
    part = lambda v: "+".join(v) if isinstance(v, list) else v
    return ".".join(part(spec[d]) if d in spec else "*" for d in dims)


def period(tp: str) -> str:
    return tp.replace("-M", "-").replace("-Q", "Q")


def tidy(raw: pd.DataFrame, dims: list[str]) -> pd.DataFrame:
    """SDMX-CSV -> series (dimension codes joined by "."), period, value, flag, updated."""
    raw = raw[raw["TIME_PERIOD"].notna()] if "TIME_PERIOD" in raw else raw.iloc[0:0]
    if raw.empty:
        return pd.DataFrame(columns=["series", "period", "value", "flag", "updated"])
    df = pd.DataFrame({
        "series": raw[dims].fillna("").astype(str).agg(".".join, axis=1),
        "period": raw["TIME_PERIOD"].astype(str).map(period),
        "value": pd.to_numeric(raw["OBS_VALUE"], errors="coerce"),
        "flag": raw.get("OBS_FLAG", pd.Series("", index=raw.index)).fillna("").astype(str),
        "updated": raw.get("UPDATED", pd.Series("", index=raw.index)).fillna("").astype(str).str.strip(),
    })
    return df.drop_duplicates(["series", "period"], keep="last").sort_values(["series", "period"]).reset_index(drop=True)


def _data(flow: str, version: str, k: str, since: str | None = None, until: str | None = None) -> pd.DataFrame:
    url = f"{REGISTRY}/data/dataflow/SSSU/{flow}/{version}/{k}"
    flt = [f"c[TIME_PERIOD]=ge:{since}" if since else "", f"c[TIME_PERIOD]=le:{until}" if until else ""]
    flt = "&".join(f for f in flt if f)
    r = _get(url + (f"?{flt}" if flt else ""), CSV)
    if not r.text.startswith("STRUCTURE"):
        raise RuntimeError(f"{flow}: not SDMX-CSV: {r.text[:200]!r}")
    return pd.read_csv(io.StringIO(r.text), dtype=str, low_memory=False)


def fetch(name: str, vers: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Full history of one set, tidy; plus metadata (version, key, last release, next release)."""
    s = SETS[name]
    v = (vers or versions())[s.flow]
    dims = dimensions(s.flow, v)
    k = key(dims, s.key)
    if s.by_year:
        parts = [_data(s.flow, v, k, until=f"{s.by_year - 1}-M12")]
        for y in range(s.by_year, date.today().year + 1):
            parts.append(_data(s.flow, v, k, since=f"{y}-M01", until=f"{y}-M12"))
        raw = pd.concat(parts, ignore_index=True)
    else:
        raw = _data(s.flow, v, k)
    # REGION and FREQ fixed by the key are dropped from the series id, FREQ is kept when mixed
    keep = [d for d in dims if not (d == "REGION" and isinstance(s.key.get(d), str))]
    df = tidy(raw, keep)
    upd = pd.to_datetime(raw.get("UPDATED", pd.Series(dtype=str)).str.strip(), format="%d.%m.%Y", errors="coerce")
    nxt = pd.to_datetime(raw.get("NEXT_UPDATE", pd.Series(dtype=str)).str.strip(), format="%d.%m.%Y", errors="coerce")
    meta = {"set": name, "flow": s.flow, "version": v, "key": k, "dims": ".".join(keep),
            "rows": len(df), "series": df["series"].nunique(),
            "first": df["period"].min() if len(df) else "", "last": df["period"].max() if len(df) else "",
            "released": upd.max().date().isoformat() if upd.notna().any() else "",
            "next_release": nxt.max().date().isoformat() if nxt.notna().any() else ""}
    return df, meta


def revisions(old: pd.DataFrame, new: pd.DataFrame, rel_tol: float = 1e-6) -> pd.DataFrame:
    """Values that changed between two snapshots of a set: revised, removed, and the count of new.

    Returns rows (series, period, kind, old, new, diff, pct) with kind "revised" or "removed";
    new periods are not listed one by one (attrs["new"] holds their count)."""
    a = pd.to_numeric(old.set_index(["series", "period"])["value"], errors="coerce")
    b = pd.to_numeric(new.set_index(["series", "period"])["value"], errors="coerce")
    both = a.index.intersection(b.index)
    va, vb = a.loc[both], b.loc[both]
    changed = ~((va - vb).abs() <= rel_tol * va.abs().clip(lower=1)) & ~(va.isna() & vb.isna())
    rev = pd.DataFrame({"kind": "revised", "old": va[changed], "new": vb[changed]})
    gone = a.index.difference(b.index)
    rem = pd.DataFrame({"kind": "removed", "old": a.loc[gone], "new": float("nan")})
    out = pd.concat([rev, rem]).reset_index()
    out["diff"] = (out["new"] - out["old"]).round(6)
    out["pct"] = ((out["new"] / out["old"] - 1) * 100).round(4)
    out = out[["series", "period", "kind", "old", "new", "diff", "pct"]].sort_values(["series", "period"]).reset_index(drop=True)
    out.attrs["new"] = len(b.index.difference(a.index))
    return out


def series(df: pd.DataFrame, pattern: dict, dims: str) -> pd.Series:
    """One series from a tidy set: pattern {dimension: code}, dims = meta["dims"] of the set."""
    names = dims.split(".")
    parts = df["series"].str.split(".", expand=True)
    parts.columns = names
    m = pd.Series(True, index=df.index)
    for d, v in pattern.items():
        m &= parts[d] == v
    sel = df[m]
    if sel["series"].nunique() != 1:
        raise KeyError(f"{pattern}: {sel['series'].nunique()} series match")
    return sel.set_index("period")["value"]
