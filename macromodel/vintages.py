"""Forecast vintages: every model run saved with its inputs, outputs, checks and conclusions.

A vintage is a long table, one row per (kind, code, year):
  kind = input (SCENARIOS), output (ANNUAL), check (CHECKS), conclusion (text).
All vintages live in data/vintages/vintages.csv and on the VINTAGES sheet. The same
rows let a later run compare an old forecast with the actuals that arrived since
(`errors`), which is what re-estimation starts from.

The Python side cannot read the Google Sheet, so a snapshot is taken from sheet values
exported as JSON (see sheet/vintage_payload.py).
"""
from pathlib import Path

import pandas as pd

from macromodel.aggregate import to_year
from macromodel.blocks.real_sector import HIST

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "vintages" / "vintages.csv"
COLUMNS = ["vintage", "date", "scenario", "last_actual", "kind", "code", "name", "units", "agg",
           "year", "value", "status", "note"]

# SCENARIOS rows 16-33, in sheet order
INPUT_CODES = ["CEASEFIRE_Q", "ENERGY_STRIKES", "ENERGY_CAP", "PORTS_CAP", "FIN_PROMISED", "DEFENCE_GDP",
               "MIGR_UA", "MOB", "HARVEST", "WHEAT", "STEEL", "TTF", "EA_GDP", "HICP", "FED_RATE",
               "GUEST", "MIGR_UA_SHARE", "GUEST_SHARE"]


def num(s):
    """Sheet display value ('4 878 980,5', '8,9%', '') -> float or None; other text stays text."""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).replace(" ", "").replace(" ", "").replace(",", ".").rstrip("%")
    try:
        return float(t)
    except ValueError:
        return str(s)


def build(meta: dict, annual: list, scenarios: list, checks: list, conclusions: list[str],
          years: list[int]) -> pd.DataFrame:
    """Rows of one vintage.

    annual: [code, name, units, agg, base_year_value, y1, y2, y3]
    scenarios: [name, units, y1, y2, y3] for SCENARIOS rows 16-33 (active columns)
    checks: [code, name, units, y1, y2, y3, status1, status2, status3]
    """
    n = len(years)
    base = years[0] - 1
    rows = []
    add = lambda **kw: rows.append({**meta, **kw})
    for code, (name, units, *vals) in zip(INPUT_CODES, scenarios):
        for y, v in zip(years, vals):
            add(kind="input", code=code, name=name, units=units, year=y, value=num(v))
    for code, name, units, agg, *vals in annual:
        for y, v in zip([base] + years, vals):
            add(kind="output", code=code, name=name, units=units, agg=agg, year=y, value=num(v))
    for code, name, units, *rest in checks:
        for y, v, st in zip(years, rest[:n], rest[n:]):
            add(kind="check", code=code, name=name, units=units, year=y, value=num(v), status=st)
    for i, text in enumerate(conclusions, 1):
        add(kind="conclusion", code=f"C{i}", note=text)
    return pd.DataFrame(rows).reindex(columns=COLUMNS)


def load(path: Path = STORE) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=COLUMNS)


def save(v: pd.DataFrame, path: Path = STORE) -> pd.DataFrame:
    """Add a vintage to the store, replacing an older copy with the same id."""
    old = load(path)
    old = old[~old["vintage"].isin(v["vintage"].unique())]
    out = pd.concat([old, v], ignore_index=True) if len(old) else v
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out


def actual_q() -> pd.DataFrame:
    """Actual quarterly ANCHORS history, one column per code."""
    return pd.read_csv(HIST / "anchors_q.csv", index_col=0).T.apply(pd.to_numeric, errors="coerce")


def errors(store: pd.DataFrame | None = None) -> pd.DataFrame:
    """Forecast minus actual for every output of every vintage whose year is now complete."""
    store = load() if store is None else store
    q = actual_q()
    out = store[store["kind"] == "output"].copy()
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    act = {}
    for code, agg in out[["code", "agg"]].drop_duplicates().itertuples(index=False):
        if code in q:
            act[code] = to_year(q[code], agg)  # same aggregation as the ANNUAL sheet
    out["actual"] = [act.get(c, pd.Series(dtype=float)).get(str(int(y))) for c, y in zip(out["code"], out["year"])]
    done = to_year(q["GDP_REAL"], "SUM").index.astype(int)  # years with all four GDP quarters
    out = out[out["year"].isin(done)].dropna(subset=["actual", "value"])
    out["error"] = out["value"] - out["actual"]
    out["error_pct"] = out["error"] / out["actual"].abs() * 100
    return out[["vintage", "code", "name", "year", "value", "actual", "error", "error_pct"]]
