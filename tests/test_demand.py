from macromodel.blocks.demand import coef_table, estimate, real_levels_q


def test_components_add_up_to_gdp():
    lv = real_levels_q().dropna()
    total = lv.HH + lv.GOV + lv.GFCF + lv.EXP - lv.IMP + lv.INV
    assert ((total - lv.GDP).abs() < 1).all()


def test_signs_of_main_elasticities():
    est = estimate()
    assert est["HH"]["coef"]["REAL_WAGE"] > 0
    assert est["EXP"]["coef"]["PORTS"] > 0
    assert est["IMP"]["coef"]["DOM_DEMAND"] > 0


def test_coef_table_has_all_rows():
    assert len(coef_table()) == 12
