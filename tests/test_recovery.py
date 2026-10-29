"""B8_CAPACITY section 3: slow recovery after downtime and destruction, and the level-based manufacturing index."""
from sheet import recovery_layout as RL
from sheet.recovery_payload import build
from sheet import b1_payload


def _rows():
    return {int(k.split("!A")[1].split(":")[0]): v[0] for k, v in build().items() if k.startswith("B8_CAPACITY!")}


def test_layout_fits_and_feeds_active_rows():
    rows = _rows()
    assert min(rows) == RL.R0 and max(rows) == RL.LAST
    for s in range(3):
        for ind in RL.IND:
            assert rows[RL.ind_row(s, ind, "EFF")][0] == f"{ind}_EFF_{s}"
    assert rows[RL.ACT["MET"]][0] == "MET" and rows[RL.ACT["ORE_XTRA"]][0] == "ORE_XTRA"


def test_model_takes_lowest_of_scenario_markets_destruction_after_ceasefire():
    rows = _rows()
    r = RL.ind_row(0, "MET", "EFF")
    f = rows[r][4]  # 2026Q4
    k = RL.sc_row(0)
    assert f.startswith(f"=IF(E{k}=0;E{r - 3};MIN(") and all(f"E{r - i}" in f for i in (1, 2, 3))


def test_recovery_time_grows_with_downtime():
    rows = _rows()
    par = rows[RL.ind_row(0, "MET", "PAR")]
    assert par[3] == "=COEFS!$E$241+COEFS!$E$242*C" + str(RL.ind_row(0, "MET", "PAR"))


def test_ore_is_metallurgy_plus_exports_only_after_ceasefire():
    rows = _rows()
    f = rows[RL.ACT["ORE"]][3]
    assert f.startswith(f"=D{RL.ACT['MET']}+IF(D{RL.ACT['K']}=0;0;")


def test_manufacturing_index_sums_levels_not_growth_rates():
    # fixed-weight averaging of growth let metallurgy jump +265% from a 10% base and add 18 points
    f = b1_payload.ind_lvl("G")
    assert "G$16/$D$16" in f and f.count("(1+E") == 3 and f.count("(1+G") == 3
    assert b1_payload.ind_lvl("D").count("*1") == 3
