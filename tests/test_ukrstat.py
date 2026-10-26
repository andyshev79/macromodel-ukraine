import pandas as pd
import pytest

from macromodel import ukrstat
from macromodel.loaders import ukrstat_sdmx as u


def snap(rows):
    return pd.DataFrame(rows, columns=["series", "period", "value"]).assign(flag="", updated="")


def test_key_orders_dimensions_and_joins_codes():
    dims = ["INDICATOR", "BASE_PERIOD", "REGION", "GOODS", "FREQ"]
    assert u.key(dims, {"INDICATOR": ["A", "B"], "REGION": u.UA, "FREQ": "M"}) == f"A+B.*.{u.UA}.*.M"
    with pytest.raises(KeyError):
        u.key(dims, {"BASE": "X"})


def test_period_labels_match_pandas():
    assert [u.period(p) for p in ("2026-M09", "2026-Q2", "2025")] == ["2026-09", "2026Q2", "2025"]


def test_tidy_joins_dimensions_and_skips_empty_rows():
    raw = pd.DataFrame({"INDICATOR": ["CPI", "CPI", None], "FREQ": ["M", "M", None],
                        "TIME_PERIOD": ["2026-M02", "2026-M01", None], "OBS_VALUE": ["101.2", "", None],
                        "UPDATED": ["14.10.2026", "14.10.2026", None]})
    df = u.tidy(raw, ["INDICATOR", "FREQ"])
    assert df["series"].tolist() == ["CPI.M", "CPI.M"]
    assert df["period"].tolist() == ["2026-01", "2026-02"]
    assert df["value"].isna().tolist() == [True, False]


def test_revisions_lists_changed_and_removed_values_and_counts_new():
    old = snap([("A", "2026-01", 100.0), ("A", "2026-02", 101.0), ("B", "2026-01", 5.0), ("B", "2026-02", None)])
    new = snap([("A", "2026-01", 100.0), ("A", "2026-02", 101.5), ("A", "2026-03", 99.0), ("B", "2026-02", None)])
    rev = u.revisions(old, new)
    assert rev[["series", "period", "kind"]].values.tolist() == [["A", "2026-02", "revised"], ["B", "2026-01", "removed"]]
    assert rev.loc[0, "diff"] == pytest.approx(0.5)
    assert rev.attrs["new"] == 1


def test_revisions_records_a_value_that_appears_in_a_published_period():
    rev = u.revisions(snap([("A", "2026-01", None)]), snap([("A", "2026-01", 3.0)]))
    assert rev["kind"].tolist() == ["revised"]


def test_quarterly_and_crosscheck(tmp_path):
    sid = ukrstat.CHECKS["CPI_YOY"][1]
    months = [f"2026-{m:02d}" for m in range(1, 7)]
    snap([(sid, p, 100 + i) for i, p in enumerate(months)]).to_csv(tmp_path / "cpi_m.csv.gz", index=False, compression="gzip")
    q = ukrstat.quarterly(tmp_path, "CPI_YOY")
    assert q.to_dict() == {"2026Q1": 2.0, "2026Q2": 5.0}
    hist = tmp_path / "history"
    hist.mkdir()
    pd.DataFrame({"2026Q1": [2.0]}, index=pd.Index(["CPI_YOY"], name="code")).to_csv(hist / "anchors_q.csv")
    pd.DataFrame(index=pd.Index([], name="code")).to_csv(hist / "series_q.csv")
    cc = ukrstat.crosscheck(tmp_path, hist)
    assert cc[["quarter", "ok"]].values.tolist() == [["2026Q1", True], ["2026Q2", None]]
