"""Block B4: labour market.

The labour force survey stopped after 2021, so unemployment for 2022-2025 is
taken from NBU estimates (UNEMP_EST, to verify). Okun's law is estimated on
2016-2025: the change in unemployment on real GDP growth. Labour supply shocks
(migration, mobilization) and the real wage rule are calibrated.
Since 2026-10-25 the sheet runs Okun by quarter (labour_q); U_SUPPLY and U_MIN stay in use.
"""
import pandas as pd

from macromodel.blocks.real_sector import ols, quarterly

UNEMP_EST = {"2022": 21.0, "2023": 17.0, "2024": 13.5, "2025": 11.5}
LF_2025 = 13500.0  # labour force on controlled territory, thousand; rough estimate, to verify

CALIBRATED = {
    ("LF", "MIGR"): (0.6, "Не используется: доля задаётся по годам в SCENARIOS строка 32"),
    ("U", "SUPPLY"): (0.5, "Половина изменения рабочей силы уходит в безработицу, половина в занятость"),
    ("RW", "const"): (2.0, "Не используется с 2026-10-23: зарплата по факторам, COEFS строки W_ (98–104)"),
    ("RW", "DU_L"): (-1.0, "Не используется с 2026-10-23: зарплата по факторам, COEFS строки W_ (98–104)"),
    ("LF", "GUEST"): (0.9, "Не используется: доля задаётся по годам в SCENARIOS строка 33"),
    ("U", "MIN"): (6.0, "Нижняя граница безработицы (структурная, минимум до войны 7–8%); дефицит кадров ниже неё идёт в зарплаты"),
}

COEF_ROWS = [("U", "const"), ("U", "GDP"), ("U", "SUPPLY"), ("LF", "MIGR"), ("RW", "const"), ("RW", "DU_L"), ("U", "MIN"), ("LF", "GUEST")]


def annual() -> pd.DataFrame:
    d = quarterly()
    year = d.index.str[:4]
    a = pd.DataFrame({
        "U": d["UNEMP"].groupby(year).mean(),
        "EMPL": d["EMPL"].groupby(year).mean(),
        "GDP": d["GDP_REAL"].groupby(year).sum(min_count=4).pct_change() * 100,
    })
    for y, u in UNEMP_EST.items():
        a.loc[y, "U"] = u
    a["DU"] = a["U"].diff()
    return a


def okun(first="2016", last="2025") -> dict:
    df = annual().loc[first:last, ["DU", "GDP"]].dropna()
    return ols(df["DU"], df[["GDP"]])


def coef_table() -> list[dict]:
    est = okun()
    rows = []
    for eq, var in COEF_ROWS:
        if (eq, var) in CALIBRATED:
            v, note = CALIBRATED[(eq, var)]
            rows.append({"eq": eq, "var": var, "coef": v, "se": None, "r2": None, "method": "калибровка", "note": note})
        else:
            rows.append({"eq": eq, "var": var, "coef": round(float(est["coef"][var]), 2),
                         "se": round(float(est["se"][var]), 2), "r2": round(float(est["r2"]), 2),
                         "method": "оценка МНК 2016–2025, годовые (закон Оукена)",
                         "note": "безработица 2022–2025 — оценки НБУ, сверить"})
    return rows


if __name__ == "__main__":
    print(annual().round(2).to_string())
    r = okun()
    print({k: round(v, 2) for k, v in r["coef"].items()}, {k: round(v, 2) for k, v in r["se"].items()}, round(r["r2"], 2))
