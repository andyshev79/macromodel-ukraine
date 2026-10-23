import openpyxl
import pandas as pd
import pytest

from macromodel import history as h
from macromodel.loaders import metals, nbu_files


def test_yoy_from_mom_needs_twelve_consecutive_months():
    idx = pd.period_range("2023-01", periods=14, freq="M")
    mom = pd.Series(101.0, index=idx)
    yoy = h._yoy_from_mom(mom)
    assert list(yoy.index.astype(str)) == ["2023-12", "2024-01", "2024-02"]
    assert yoy.iloc[0] == pytest.approx((1.01 ** 12 - 1) * 100)
    gap = mom.drop(pd.Period("2023-06", "M"))
    assert h._yoy_from_mom(gap).empty


def test_annual_agg_rules():
    assert h.annual_agg("GDP_NOM") == "SUM"          # anchor says so
    assert h.annual_agg("CPI_FOOD_YOY") == "END"     # y/y price index: December
    assert h.annual_agg("IND_C8_YOY") == "AVG"       # volume y/y: mean of quarters
    assert h.annual_agg("EXPG_METALS_USD") == "SUM"
    assert h.annual_agg("PX_WHEAT_USD") == "AVG"
    assert h.annual_agg("M3") == "END"


def test_annual_real_gdp_chains_back_through_index():
    real = pd.Series({"2010": 100.0, "2011": 105.0})
    idx = pd.Series({2009: 85.0, 2010: 104.0, 2011: 105.0})
    out = h._annual_real_gdp(None, real, idx)
    assert out[2009] == pytest.approx(100 / 1.04)
    assert out[2011] == 105.0


def test_month_names_full_and_short():
    assert nbu_files._month("берез") == 3
    assert nbu_files._month("бер") == 3
    assert nbu_files._month("серп*") == 8
    assert nbu_files._month("січ-серп") is None


def test_trade_groups_year_labels_as_numbers_and_text(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "1.1"
    ws.append([None])
    ws.append(["Найменування", None, "Description", 2020, None, "2021", None, 2021])
    ws.append([None, None, None, "груд", None, "січ", "лют", "січ-лют"])
    for lab in nbu_files.TRADE_GROUPS.values():
        ws.append([lab, lab, lab, 10, None, 1, 2, 3])
    p = tmp_path / "t.xlsx"
    wb.save(p)
    df = nbu_files.trade_groups_m(p, "1.1")
    assert list(df.index.astype(str)) == ["2020-12", "2021-01", "2021-02"]
    assert df.loc[pd.Period("2021-02", "M"), "METALS"] == 2


def test_copied_year_is_dropped():
    from macromodel.loaders import macrostat
    idx = pd.period_range("2011-01", periods=36, freq="M")
    vals = [100.0 + (i % 12) for i in range(24)] + [100.0] * 12
    df = pd.DataFrame({"X": vals}, index=idx)
    out = macrostat._drop_copied_years(df)
    assert sorted(set(out.index.year)) == [2011, 2013]


def test_metals_monthly_matches_published_totals():
    m = metals.monthly()
    nine = m.loc["2026-01":"2026-09"].sum()
    # Ukrmetallurgprom, January-September 2026: steel 4.43, pig iron 4.46, rolled 3.73 million t
    assert abs(nine["STEEL_KT"] - 4430) < 15 and abs(nine["PIG_IRON_KT"] - 4460) < 15 and abs(nine["ROLLED_KT"] - 3730) < 15
    assert abs(m.loc["2025-01":"2025-12", "PIG_IRON_KT"].sum() / 1000 - metals.annual().loc[2025, "PIG_IRON_MT"]) < 0.05


def test_surveys_parse(tmp_path):
    import openpyxl
    from datetime import datetime
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "UKR"
    ws.append([None, "Інфляційні очікування"])
    ws.append([None, "банків", "підприємств", "домогосподарств", "фінансових аналітиків"])
    ws.append([datetime(2026, 1, 1), 9.4, "#N/A", 10.9, 7.5])
    ws.append([datetime(2026, 2, 1), "#N/A", 11.1, 13.5, "#N/A"])
    ws.append([None])
    ws.append(["*", "примітка"])
    wb.save(tmp_path / "s.xlsx")
    s = nbu_files.surveys_m(tmp_path / "s.xlsx")
    assert s.loc["2026-01", "BANKS"] == 9.4 and pd.isna(s.loc["2026-02", "BANKS"]) and len(s) == 2
