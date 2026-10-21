"""Turn daily or monthly series into model quarters and quarters into years."""
import pandas as pd


def to_quarter(s: pd.Series, how: str) -> pd.Series:
    """Roll a dated series up to quarters, indexed by labels like '2024Q3'.

    how: 'AVG' (mean of the quarter), 'END' (last observation), 'SUM'.
    """
    s = s.dropna().sort_index()
    q = s.groupby(s.index.to_period("Q"))
    out = {"AVG": q.mean, "END": q.last, "SUM": q.sum}[how]()
    out.index = out.index.astype(str)
    return out


def to_year(q: pd.Series, how: str) -> pd.Series:
    """Roll quarterly labels ('2024Q3') up to years; a year needs all four quarters."""
    q = q.dropna()
    years = q.index.str[:4]
    full = q.groupby(years).count() == 4
    g = q.groupby(years)
    out = {"AVG": g.mean, "END": g.last, "SUM": g.sum}[how]()
    return out[full]
