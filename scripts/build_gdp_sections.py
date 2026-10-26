"""Write data/external/gdp_sections_q.csv: GDP by production method for the sections B1 keeps in
GVA_OTHER (E, I, K, L, M, N, P, Q, R, S) and taxes and subsidies on products, nominal UAH million and
real % y/y, quarterly, from Andrey's MacroStat sheet GDP_Q (Ukrstat).

Usage: python scripts/build_gdp_sections.py [path to MacroStat.xlsx]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from macromodel.loaders.macrostat import gdp_sections_q  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw" / "manual" / "MacroStat.xlsx"
df = gdp_sections_q(path).loc["2010Q1":].dropna(how="all")
df.assign(source="MacroStat, лист GDP_Q (Госстат, ВВП производственным методом)").to_csv(
    ROOT / "data" / "external" / "gdp_sections_q.csv", index_label="quarter")
