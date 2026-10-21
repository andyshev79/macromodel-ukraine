import pandas as pd

from macromodel.aggregate import to_quarter, to_year


def test_quarter_avg_end_sum():
    s = pd.Series([1.0, 2.0, 3.0, 10.0], index=pd.to_datetime(["2024-01-05", "2024-02-05", "2024-03-29", "2024-04-01"]))
    assert to_quarter(s, "AVG")["2024Q1"] == 2.0
    assert to_quarter(s, "END")["2024Q1"] == 3.0
    assert to_quarter(s, "SUM")["2024Q2"] == 10.0


def test_year_needs_four_quarters():
    q = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=["2023Q1", "2023Q2", "2023Q3", "2023Q4", "2024Q1"])
    y = to_year(q, "SUM")
    assert y["2023"] == 10.0
    assert "2024" not in y.index
