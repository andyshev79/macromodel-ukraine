"""Gosstat (stat.gov.ua) files: annual output of key industrial products in physical units.

The archive "Виробництво окремих видів промислової продукції" holds one workbook for
2003-2010 and one for 2011-2020 with different layouts; rows are matched by label start.
Steel is published only to 2010 (later years are confidential); pig iron runs through 2020.
Gosstat has not published the table for the years since 2021.
"""
import io
import re
import zipfile
from pathlib import Path

import openpyxl
import pandas as pd
import requests

URL = "https://stat.gov.ua/sites/default/files/2026-07/vyrobnytstvo_okremykh_vydiv_promyslovoyi_produktsiyi.zip"

# key -> (unit, label starts in the 2003-2010 file, label starts in the 2011-2020 file)
PRODUCTS = {
    "COAL_MT": ("млн т", "Вугілля готове", "Вугілля кам’яне"),
    "GAS_BCM": ("млрд м3", "Газ природний", "Газ природний"),
    "PIG_IRON_MT": ("млн т", "Чавун", "Чавун переробний"),
    "STEEL_MT": ("млн т", "Сталь без напівфабрикатів", None),
    "ROLLED_STEEL_MT": ("млн т", "Прокат готовий чорних металів", None),
    "ELEC_BKWH": ("млрд кВт·год", "Електроенергія", "Електроенергія"),
}


def download(cache: Path, refresh: bool = False) -> Path:
    p = cache / "gosstat" / "industrial_products_y.zip"
    if refresh or not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(URL, timeout=300)
        r.raise_for_status()
        p.write_bytes(r.content)
    return p


def _year(v) -> int | None:
    m = re.match(r"(19|20)\d\d", str(v).strip()) if v is not None else None
    return int(m.group(0)) if m else None


def _table(rows: list[tuple]) -> pd.DataFrame:
    """One workbook; the labels to look for depend on whether it starts before 2011."""
    head_i = next((i for i, r in enumerate(rows) if sum(_year(v) is not None for v in r) >= 5), None)
    if head_i is None:  # the 1990-2002 workbook has another layout and is not needed
        return pd.DataFrame()
    years = {j: _year(v) for j, v in enumerate(rows[head_i]) if _year(v)}
    out = {}
    for key, (_, old, new) in PRODUCTS.items():
        lab = old if min(years.values()) < 2011 else new
        if lab is None:
            continue
        r = next((r for r in rows[head_i + 1:] if isinstance(r[0], str) and r[0].strip().startswith(lab)), None)
        if r is None:
            continue
        # the year header and the values are right-aligned: the last len(years) numeric cells
        nums = [v for v in r[1:] if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().startswith(("к", "…")))]
        vals = nums[-len(years):]
        out[key] = {y: float(v) for y, v in zip(years.values(), vals) if isinstance(v, (int, float))}
    return pd.DataFrame(out)


def products_y(path: Path) -> pd.DataFrame:
    """Annual output by product (columns as in PRODUCTS), indexed by year."""
    frames = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith(".xlsx"):
                continue
            wb = openpyxl.load_workbook(io.BytesIO(z.read(name)), read_only=True, data_only=True)
            rows = list(wb.worksheets[0].iter_rows(values_only=True))
            frames.append(_table(rows))
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = "year"
    return df
