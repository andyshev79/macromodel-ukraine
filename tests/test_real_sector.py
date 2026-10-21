import pandas as pd

from macromodel.blocks.real_sector import annual_growth, chain_real, estimate, real_levels_q


def test_chain_real_keeps_base_year_and_growth():
    q = [f"{y}Q{i}" for y in (2020, 2021, 2022) for i in range(1, 5)]
    nom = pd.Series(100.0, index=q)
    yoy = pd.Series(10.0, index=q)
    real = chain_real(nom, yoy)
    assert real["2021Q1"] == 100
    assert round(real["2022Q1"], 6) == 110
    assert round(real["2020Q1"], 6) == round(100 / 1.1, 6)


def test_sectors_sum_to_gdp():
    lv = real_levels_q()
    total = lv.drop(columns=["GDP"]).sum(axis=1)
    assert ((total - lv["GDP"]).abs() < 1).all()


def test_harvest_elasticity_is_positive():
    assert estimate()["A"]["coef"]["HARVEST"] > 0
    assert len(annual_growth(real_levels_q())) >= 10
