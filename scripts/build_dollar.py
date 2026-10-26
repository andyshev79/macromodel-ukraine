"""Write data/external/dollar_m.csv: month-end UAH/USD and UAH/EUR and private remittances to Ukraine
(total, net compensation of employees, private transfers, official and informal channels, USD million)
from Andrey's MacroStat sheet Dollar (NBU rates_final.xlsx and Perekaz_m.xlsx).

Usage: python scripts/build_dollar.py [path to MacroStat.xlsx] [last month of facts, YYYY-MM]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from macromodel.loaders.macrostat import dollar_m  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "manual" / "MacroStat.xlsx"
last = sys.argv[2] if len(sys.argv) > 2 else "2026-09"  # the sheet says "9m2026"; later months are projections
df = dollar_m(path, last).dropna(how="all")
df.assign(source="MacroStat, лист Dollar (НБУ: официальный курс; приватные переводы Perekaz_m, с 2024 оценки НБУ)").to_csv(
    ROOT / "data" / "external" / "dollar_m.csv", index_label="month")
