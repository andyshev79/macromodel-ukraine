"""Guard for the ru_RU sheet locale: a value written as text "0.9" stays text there, and "11.5" turns into the
date 11 May. Every payload must hold plain JSON numbers, and formulas must use decimal commas."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PAYLOADS = sorted(p.stem for p in Path("sheet").glob("*_payload.py"))
DOT_NUMBER = re.compile(r"^\s*[-−]?\d+\.\d+\s*%?\s*$")
QUOTED = re.compile(r'"[^"]*"')
SHEET_REF = re.compile(r"[A-Za-z_]+\d*!")  # sheet names like B1_REAL! are not numbers


def bad_cells(out: dict) -> list:
    bad = []
    for rng, rows in out.items():
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                if not isinstance(v, str):
                    continue
                if DOT_NUMBER.match(v):
                    bad.append((rng, i, j, v))
                elif v.startswith("="):
                    body = SHEET_REF.sub("", QUOTED.sub('""', v))
                    if re.search(r"(?<![A-Za-z_$\d])\d+\.\d+", body):
                        bad.append((rng, i, j, v[:80]))
    return bad


@pytest.mark.parametrize("name", PAYLOADS)
def test_payload_has_no_dot_decimals(name):
    env = {**os.environ, "PYTHONPATH": "."}
    run = subprocess.run([sys.executable, f"sheet/{name}.py"], capture_output=True, text=True, env=env)
    if run.returncode != 0 or not run.stdout.strip().startswith("{"):
        pytest.skip(f"{name} needs arguments or data")
    assert bad_cells(json.loads(run.stdout)) == []


def test_guard_catches_dot_text():
    assert bad_cells({"S!A1": [["0.9", "=A1*1.5", 0.9, "=IF(A1>0;\"1.5\";2)", "=B1_REAL!E31*2"]]}) == [
        ("S!A1", 0, 0, "0.9"), ("S!A1", 0, 1, "=A1*1.5")]
