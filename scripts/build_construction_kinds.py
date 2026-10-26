"""Write data/external/construction_kind_m.csv and data/external/housing_area_q.csv from Ukrstat
CSV exports that Andrey sent on 2026-10-26.

construction_kind_m.csv: construction output index by kind of construction (total, buildings,
residential, non-residential, civil engineering works), monthly from 2015, three bases: % to the
same month of last year (yoy), from January % to the same months of last year (ytd) and % to the
previous month (mom).

housing_area_q.csv: floor area put into service and at the start of construction, residential and
non-residential buildings, m², cumulative from January, quarterly from 2018.

Usage: python scripts/build_construction_kinds.py <index.csv> <area.csv>
"""
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"
BASE = {"До відповідного місяця попереднього року": "yoy", "До відповідного періоду попереднього року": "ytd",
        "До попереднього місяця": "mom"}
KIND = {"Будівництво": "TOT", "Будівлі": "BLD", "Житлові будинки": "RES", "Нежитлові будівлі": "NRES",
        "Інженерні споруди": "ENG"}
AREA = {("Загальна площа житлових будинків, прийнятих в експлуатацію", "Житлові будинки"): "RES_DONE",
        ("Загальна площа нежитлових будівель, прийнятих в експлуатацію", "Нежитлові будівлі"): "NRES_DONE",
        ("Загальна площа житлових будинків і нежитлових будівель на початок будівництва", "Житлові будинки"): "RES_START",
        ("Загальна площа житлових будинків і нежитлових будівель на початок будівництва", "Нежитлові будівлі"): "NRES_START"}


def rows(path):
    r = list(csv.reader(open(path, encoding="utf-8-sig")))
    return r[0][13:], [x for x in r[1:] if len(x) > 13]


def index(path) -> pd.DataFrame:
    head, body = rows(path)
    d = {f"{KIND[x[4]]}_{BASE[x[1]]}": pd.to_numeric(pd.Series(x[13:], index=head), errors="coerce") for x in body}
    df = pd.DataFrame(d)
    df.index = [s.replace("-M", "-") for s in df.index]
    return df[sorted(df.columns)]


def area(path) -> pd.DataFrame:
    head, body = rows(path)
    d = {AREA[(x[0], x[3])]: pd.to_numeric(pd.Series(x[13:], index=head), errors="coerce")
         for x in body if (x[0], x[3]) in AREA and x[4] == "Загалом" and x[1] == "Не застосовується"}
    df = pd.DataFrame(d)[list(AREA.values())]
    df.index = [s.replace("-Q", "Q") for s in df.index]
    return df


if __name__ == "__main__":
    src = "Госстат, экспорт таблиц (прислал Андрей 2026-10-26); 2026 — предварительные"
    index(sys.argv[1]).assign(source=src).to_csv(EXT / "construction_kind_m.csv", index_label="month")
    area(sys.argv[2]).assign(source=src).to_csv(EXT / "housing_area_q.csv", index_label="quarter")
