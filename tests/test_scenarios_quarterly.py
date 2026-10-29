"""Quarterly SCENARIOS block: annual cells are formulas over the quarters, and the fill follows the ceasefire quarter."""
from sheet import recovery_layout as RL
from sheet.scenarios_quarterly_payload import PARAMS, ROW, QLAB, PROTECTED, build, fill_war, protect, annual_formula


def test_rows_do_not_overlap_and_stay_below_old_table():
    rows = sorted(ROW.values())
    assert rows[0] > 200 and all(b - a == 4 for a, b in zip(rows, rows[1:]))


def test_annual_cells_are_formulas_over_their_quarters():
    out = build()
    for code, ar, *_ in PARAMS:
        cells = out[f"SCENARIOS!C{ar}:K{ar}"][0]
        assert all(c.startswith("=") for c in cells)
        if code in RL.IND:  # metallurgy and ports: annual = average of the after-recovery path in B8_CAPACITY
            assert f"B8_CAPACITY!C{RL.EFF_ROWS[code][0]}" in cells[0]
        else:
            assert str(ROW[code]) in cells[0]


def test_2026_average_weights_first_half_twice():
    assert annual_formula("avg", 205, 2026) == "=(2*C205+D205+E205)/4"


def test_ceasefire_quarter_splits_the_year():
    # war level 70 in 2026, annual 2027 = 90 with ceasefire in 2027Q3: two war quarters, then the rest of the year
    line = fill_war([70, 90, 108], (2027, 3), "war_up", 84.8)
    q = dict(zip(QLAB, line[1:]))
    assert q["2027Q1"] == q["2027Q2"] == 70 and q["2027Q3"] == q["2027Q4"] == 110
    assert abs(sum(q[f"2027Q{i}"] for i in range(1, 5)) / 4 - 90) < 1e-9


def test_stop_month_mixes_first_half_and_war_level():
    line = fill_war([60, 15, 50], (None, None), "war_down", 100, stop=9)
    assert line[1] == round((2 * 100 + 60) / 3, 1) and line[2] == 60


def test_protect_blanks_annual_inputs_in_other_payloads():
    ar = sorted(PROTECTED)[0]
    out = protect({f"SCENARIOS!A{ar}:N{ar}": [["x", "y"] + [1] * 9 + ["=L", "=M", "=N"]]})
    row = out[f"SCENARIOS!A{ar}:N{ar}"][0]
    assert row[:2] == ["x", "y"] and row[2:11] == [None] * 9 and row[11] == "=L"
