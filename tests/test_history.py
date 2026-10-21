import pandas as pd
import pytest

from macromodel import history as h
from macromodel.loaders import nbu_api


def m(values, start="2023-01"):
    return pd.Series(values, index=pd.period_range(start, periods=len(values), freq="M"), dtype=float)


def test_period_is_the_one_before_reporting_date():
    assert nbu_api.period_of("20150401", "Q") == pd.Period("2015Q1")
    assert nbu_api.period_of("20150101", "M") == pd.Period("2014-12", "M")
    assert nbu_api.period_of("20240101", "Y") == pd.Period("2023", "Y")
    assert nbu_api.period_of("20240115", "D") == pd.Period("2024-01-15", "D")


def test_select_filters_dimensions_and_frequency():
    rows = [
        {"dt": "20240201", "freq": "M", "id_api": "G_S", "tzep": "USD", "t023": "1", "value": 5},
        {"dt": "20240201", "freq": "M", "id_api": "G_S", "tzep": "USD", "t023": "2", "value": 7},
        {"dt": "20240401", "freq": "Q", "id_api": "G_S", "tzep": "USD", "t023": "1", "value": 15},
    ]
    df = nbu_api.to_frame(rows)
    s = nbu_api.select(df, "G_S", "USD", freq="M", t023="1")
    assert s.to_dict() == {pd.Period("2024-01", "M"): 5}
    with pytest.raises(KeyError):
        nbu_api.select(df, "G_S", "USD", t023="9")


def test_ytd_to_q_uses_quarter_end_months_only():
    ytd = m([10, 20, 30, 40, 50, 60, None, 80, 90, 100, 110, 120])
    q = h.ytd_to_q(ytd)
    assert q.to_dict() == {"2023Q1": 30, "2023Q2": 30, "2023Q3": 30, "2023Q4": 30}


def test_ytd_avg_to_q():
    q = pd.Series([10.0, 12.0, 14.0, 16.0], index=pd.period_range("2020Q1", periods=4, freq="Q"))
    # YTD averages of quarters 10, 14, 18, 22
    assert h.ytd_avg_to_q(q).tolist() == [10, 14, 18, 22]


def test_chain_real_keeps_base_year_and_applies_yoy():
    idx = pd.period_range("2020Q1", "2022Q4", freq="Q")
    nominal = pd.Series(range(1, 13), index=idx, dtype=float) * 100
    yoy = pd.Series(10.0, index=idx)
    real = h.chain_real(nominal, yoy, base_year=2021)
    assert real[pd.Period("2021Q2")] == nominal[pd.Period("2021Q2")]
    assert real[pd.Period("2022Q2")] == pytest.approx(nominal[pd.Period("2021Q2")] * 1.1)
    assert real[pd.Period("2020Q2")] == pytest.approx(nominal[pd.Period("2021Q2")] / 1.1)


def test_m_to_q_needs_full_quarter():
    s = m([1, 2, 3, 4, 5])
    assert h.m_to_q(s, "SUM").to_dict() == {"2023Q1": 6}
    assert h.m_to_q(s, "END").to_dict() == {"2023Q1": 3}


def test_weighted_rate():
    r = m([10, 20, 30])
    v = m([1, 1, 2])
    assert h.weighted_m_to_q(r, v)["2023Q1"] == pytest.approx((10 + 20 + 60) / 4)


def test_annual_to_q():
    a = pd.Series({2020: 40.0})
    assert h.annual_to_q(a, "SUM").tolist() == [10] * 4
    assert h.annual_to_q(a, "AVG").tolist() == [40] * 4


def test_every_anchor_has_a_recipe():
    from macromodel.anchors import ANCHORS
    assert [a.code for a in ANCHORS] == [r.code for r in h.ANCHOR_RECIPES]
