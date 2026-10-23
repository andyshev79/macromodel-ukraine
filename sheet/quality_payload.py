"""Build the MODEL_QUALITY sheet from macromodel.quality: one row per estimated equation
with fit and out-of-sample errors, then actual vs fitted values by year.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Rerun after re-estimating the blocks or updating the history.
"""
import json
import sys
from datetime import date

from macromodel import quarterly
from macromodel.quality import FIRST, LAST, META, NOTES, TEST_YEARS, report

HEADER_ROW = 7
YEARS = [str(y) for y in range(int(FIRST), int(LAST) + 1)]
r1 = lambda v: None if v != v else round(float(v), 1)  # NaN -> empty
r2 = lambda v: None if v != v else round(float(v), 2)


def comment(eq: str, r: dict) -> str:
    parts = []
    if r["verdict"] == "только среднее":
        parts.append("Драйвера нет: прогноз — средний рост вне 2022")
    if r["r2"] - r["r2_ex22"] > 0.4:
        parts.append(f"высокий R² держится на 2022 (без него {r['r2_ex22']:.2f})".replace(".", ","))
    if r["verdict"] != "только среднее" and r["ratio"] >= 1:
        parts.append(f"ретропрогноз не лучше простого правила ({r['bench_rule']})")
    if r["min_t"] == r["min_t"] and r["min_t"] < 2:
        weak = [k for k, t in r["t"].items() if abs(t) < 2]
        parts.append("незначим: " + ", ".join(weak))
    if r["bias_note"]:
        parts.append(f"систематически {r['bias_note']} в 2023–2025")
    if eq in NOTES:
        parts.append(NOTES[eq])
    s = "; ".join(parts)
    return s[:1].upper() + s[1:]


rep = report()
n = len(rep)
last = HEADER_ROW + n
out = {}
out["MODEL_QUALITY!A1:A5"] = [
    ["Качество моделей"],
    [f"Только оценённые уравнения (МНК, годовые {FIRST}–{LAST}). Откалиброванные коэффициенты проверить на истории нельзя — см. COEFS, столбец L. "
     f"Пересчитано {date.today().isoformat()} (Python: macromodel/quality.py)."],
    ["Ретропрогноз: уравнение оценивается на годах до t и прогнозирует год t (2023, 2024, 2025) при известных драйверах. "
     "Ошибка = факт − модель: плюс — модель занизила, минус — завысила."],
    ["Простое правило — лучшее из двух: «как в прошлом году» или «среднее прошлых лет без 2022». Отношение < 1 — модель лучше правила. "
     "Вердикт: надёжно — отношение < 0,8 и все драйверы с |t| ≥ 2; приемлемо — отношение < 1; слабо — не лучше правила."],
    ["R² без 2022 показывает, сколько объясняют драйверы: дамми 2022 подгоняет военный год точно и завышает обычный R²."],
]
out["MODEL_QUALITY!A6:H6"] = [[
    "Итого:",
    f'=COUNTIF(P{HEADER_ROW + 1}:P{last};"надёжно")&" надёжно, "&COUNTIF(P{HEADER_ROW + 1}:P{last};"приемлемо")&" приемлемо, "'
    f'&COUNTIF(P{HEADER_ROW + 1}:P{last};"слабо")&" слабо, "&COUNTIF(P{HEADER_ROW + 1}:P{last};"только среднее")&" только среднее; '
    f'откалибровано коэффициентов: "&COUNTIF(COEFS!I:I;"калибровка")',
]]
head = ["Блок", "Уравнение", "Что объясняет", "Ед.", "n", "R²", "R² без 2022", "Мин. |t| драйвера"] \
    + [f"Ошибка {y}" for y in TEST_YEARS] + ["Ср. абс. ошибка", "Простое правило", "Отношение", "Смещение", "Вердикт", "Комментарий"]
rows = [head]
for eq, r in rep.items():
    blk, desc, unit = META[eq]
    rows.append([blk, eq, desc, unit, r["n"], r2(r["r2"]), r2(r["r2_ex22"]), r1(r["min_t"])]
                + [r1(r["oos"].get(y, float("nan"))) for y in TEST_YEARS]
                + [r1(r["mae"]), r1(r["bench"]), r2(r["ratio"]), r1(r["bias"]), r["verdict"], comment(eq, r)])
out[f"MODEL_QUALITY!A{HEADER_ROW}:Q{last}"] = rows

# Quarterly re-estimation of the same relation, where drivers exist by quarter
qe = quarterly.estimate()
qrows = [["Квартальная: n", "R²", "Мин. |t| (Ньюи–Уэст)", "Ср. абс. ошибка", "В модели"]]
for eq in rep:
    if eq in qe:
        r = qe[eq]
        qrows.append([r["n"], r2(r["r2"]), r1(r["min_t"]), r1(r["mae"]), "квартальная" if eq in quarterly.USED else "годовая"])
    else:
        qrows.append(["", "", "", "", "годовая"])
out[f"MODEL_QUALITY!R{HEADER_ROW}:V{last}"] = qrows

fit_row = last + 3
fit = [["Факт и модель по годам (оценка на всех годах; эти коэффициенты стоят в COEFS)"],
       ["Уравнение", "Ряд"] + [int(y) for y in YEARS]]
for eq, r in rep.items():
    fit.append([eq, "факт"] + [r1(r["actual"].get(y, float("nan"))) for y in YEARS])
    fit.append([eq, "модель"] + [r1(r["fitted"].get(y, float("nan"))) for y in YEARS])
out[f"MODEL_QUALITY!A{fit_row}:L{fit_row + len(fit) - 1}"] = fit
json.dump(out, sys.stdout, ensure_ascii=False)
