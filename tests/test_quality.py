from macromodel.quality import META, TEST_YEARS, report


def test_report_covers_estimated_equations():
    rep = report()
    assert set(rep) == set(META)
    for r in rep.values():
        assert r["n"] == 10 and set(r["oos"]) == set(TEST_YEARS)
        assert r["verdict"] in {"надёжно", "приемлемо", "слабо", "только среднее"}


def test_in_sample_matches_blocks():
    from macromodel.blocks.prices import estimate
    assert abs(report()["CPI"]["r2"] - estimate()["CPI"]["r2"]) < 1e-9


def test_dummy_only_equation_is_a_mean():
    r = report()["GVA_G"]
    assert r["verdict"] == "только среднее" and abs(r["r2_ex22"]) < 1e-9
