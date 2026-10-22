"""Save a forecast vintage: CSV in data/vintages and rows for the VINTAGES sheet.

Usage: python -m sheet.vintage_payload SNAPSHOT_DIR START_ROW
SNAPSHOT_DIR holds meta.json, annual.json, scenarios.json, checks.json, conclusions.json
exported from the model sheet (layouts in macromodel.vintages.build). Prints JSON
{range: values} for the sheet; the formula columns M:O are copied down from row 10.
"""
import json
import sys
from pathlib import Path

from macromodel.vintages import build, save

KIND = {"input": "ввод", "output": "результат", "check": "проверка", "conclusion": "вывод"}

src = Path(sys.argv[1])
start = int(sys.argv[2])
rd = lambda name: json.loads((src / f"{name}.json").read_text())
meta = rd("meta")
years = meta.pop("years")
v = build(meta, rd("annual"), rd("scenarios"), rd("checks"), rd("conclusions"), years)
save(v)

cell = lambda x: "" if x is None or x != x else x
rows = [[r.vintage, r.date, r.scenario, r.last_actual, KIND[r.kind], r.code, cell(r.name), cell(r.units),
         "" if r.year != r.year else int(r.year), cell(r.value), cell(r.status), cell(r.note)]
        for r in v.itertuples()]
print(json.dumps({f"VINTAGES!A{start}:L{start + len(rows) - 1}": rows}, ensure_ascii=False))
