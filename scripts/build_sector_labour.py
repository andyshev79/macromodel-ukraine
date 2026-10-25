"""Write data/external/sector_labour_m.csv: average wage and staff numbers, monthly from
2010, for the whole economy and KVED sections O (public administration and defence),
P (education) and Q (health and social work), from the NBU files Wages_m and Number_m.

Gosstat stopped monthly labour statistics from 2022-02 to 2023-12. For wages it later
published quarterly averages by section; those (taken from index.minfin.com.ua, which
republishes them) fill the missing months, the quarter's value in each of its months, and
are marked so in the source column. Staff numbers for those months stay missing.

Usage: python scripts/build_sector_labour.py [--offline]
"""
import argparse
import io
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from macromodel.loaders import nbu_files  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--offline", action="store_true", help="use cached files only")
args = p.parse_args()

cache = ROOT / "data" / "raw"
parts = []
for name, pre, unit, src in (("wages_m", "WAGE", "грн в месяц", "НБУ Wages_m.xlsx (Госстат), средняя зарплата штатного работника"),
                             ("staff_m", "STAFF", "тыс. человек", "НБУ Number_m.xlsx (Госстат), среднеучётная численность штатных работников")):
    df = nbu_files.by_section_m(nbu_files.path(cache, name, refresh=not args.offline))
    long = df.rename(columns=lambda k: f"{pre}_{k}").stack().rename("value").reset_index()
    long.columns = ["month", "code", "value"]
    long["unit"], long["source"] = unit, src
    parts.append(long)
MINFIN = "https://index.minfin.com.ua/ua/labour/salary/average/branch/{y}/"
MINFIN_ROWS = {"TOTAL": "У середньому", "O": "Державне управління", "P": "Освіта", "Q": "Охорона здоров"}


def quarterly_wages(y: int) -> dict:
    path = cache / "minfin" / f"salary_branch_{y}.html"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(MINFIN.format(y=y), timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    t = next(x for x in pd.read_html(io.StringIO(path.read_text(encoding="utf-8"))) if x.shape[0] > 10)
    out = {}
    for k, lab in MINFIN_ROWS.items():
        row = t[t.iloc[:, 0].astype(str).str.startswith(lab)].iloc[0]
        for q in range(1, 5):
            for m in range(3 * q - 2, 3 * q + 1):
                out[(f"{y}-{m:02d}", f"WAGE_{k}")] = float(row.iloc[q])
    return out


have = set(zip(parts[0]["month"].astype(str), parts[0]["code"]))
fill = [(m, c, v) for y in (2022, 2023) for (m, c), v in quarterly_wages(y).items() if (m, c) not in have]
parts.append(pd.DataFrame({"month": [m for m, _, _ in fill], "code": [c for _, c, _ in fill], "value": [v for _, _, v in fill],
                           "unit": "грн в месяц",
                           "source": "Госстат, среднемесячная за квартал (через index.minfin.com.ua); то же значение во всех месяцах квартала"}))
out = pd.concat(parts)
out["month"] = out["month"].astype(str)
out = out.sort_values(["code", "month"])[["month", "code", "value", "unit", "source"]]
path = ROOT / "data" / "external" / "sector_labour_m.csv"
out.to_csv(path, index=False)
print(path, len(out))
print(out.groupby("code")["month"].agg(["min", "max", "count"]))
