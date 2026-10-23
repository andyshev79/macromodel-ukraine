"""Steel, pig iron and rolled products output, hand-entered from public releases.

Gosstat keeps steel output confidential after 2010, so these come from the producers'
association Ukrmetallurgprom as republished by GMK Center and the press:
- data/external/metals_m.csv: monthly, thousand t, from 2024 (2024-2025 from the GMK
  infographic, 2026 from monthly releases; a few months derived from cumulative totals,
  marked in the source column)
- data/external/metals_y.csv: annual, million t, 2016-2025
Add each new month to metals_m.csv by hand.
"""
from pathlib import Path

import pandas as pd

EXT = Path(__file__).resolve().parents[2] / "data" / "external"


def monthly(path: Path = EXT / "metals_m.csv") -> pd.DataFrame:
    """Columns STEEL_KT, PIG_IRON_KT, ROLLED_KT; monthly PeriodIndex."""
    d = pd.read_csv(path, dtype={"month": str})
    out = d.pivot(index="month", columns="code", values="value")
    out.index = pd.PeriodIndex(out.index, freq="M")
    return out.sort_index()


def annual(path: Path = EXT / "metals_y.csv") -> pd.DataFrame:
    """Columns STEEL_MT, PIG_IRON_MT, ROLLED_STEEL_MT (Gosstat PRODUCTS codes); index years."""
    d = pd.read_csv(path)
    return d.pivot(index="year", columns="code", values="value").sort_index()
