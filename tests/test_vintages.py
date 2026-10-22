import json
from pathlib import Path

import pytest

from macromodel.vintages import build, errors, num, save

META = {"vintage": "test", "date": "2026-10-22", "scenario": "База", "last_actual": "2026Q2"}


def test_num_parses_sheet_display():
    assert num("4 878 980,5") == 4878980.5
    assert num("8,9%") == 8.9
    assert num("") is None and num("нет") == "нет"


def test_build_save_and_errors(tmp_path: Path):
    annual = [["GDP_REAL", "ВВП", "млн грн", "SUM", "4 296 489,1", "1", "2", "3"]]
    scen = [["Квартал", "", "нет", "2027Q1", ""]]
    checks = [["CHK", "Проверка", "%", "1", "2", "3", "OK", "OK", "ВНИМАНИЕ"]]
    concl = [["Ключевой момент", "рост"], ["Узкое место", "люди"]]
    v = build(META, annual, scen, checks, concl, [2026, 2027, 2028])
    assert v["kind"].value_counts().to_dict() == {"output": 4, "input": 3, "check": 3, "conclusion": 2}
    assert list(v.loc[v["kind"] == "conclusion", "name"]) == ["Ключевой момент", "Узкое место"]
    store = save(v, tmp_path / "v.csv")
    e = errors(store)
    assert list(e["year"]) == [2025] and abs(e["error_pct"].iloc[0]) < 0.01


def test_conclusions_are_required():
    with pytest.raises(ValueError, match="Узкое место"):
        build(META, [], [], [], [["Ключевой момент", "рост"]], [2026, 2027, 2028])
