"""Build the cell contents of B8_CAPACITY, its COEFS rows and CHECKS (block B8).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
B8 only reads other blocks and SCENARIOS; it flags growth above capacity and does not
change the forecast, so the bottlenecks stay visible.
"""
import json
import sys

from macromodel import scenario_layout as SL
from macromodel.blocks.capacity import coef_table

COEF_FIRST = 80  # B1 5-22, B2 23-35, B3 36-44, B4 45-52, B5 53-59, B6 60-64, B7 65-79
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}
C = lambda eq, v: f"COEFS!$E${crow[(eq, v)]}"
k = lambda eq, v: f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (eq, v)):g}".replace(".", ",")

out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(coefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B8", r["eq"], r["var"], r["coef"], "", "", "2015–2025", "калибровка", "", "2026-10-22", r["note"]]
    for r in coefs]

pairs = list(zip("EFG", "DEF"))
YEARS = {"D": ("AR5:AU5", "AV5:AY5"), "E": ("AV5:AY5", "AZ5:BC5"), "F": ("AZ5:BC5", "BD5:BG5"), "G": ("BD5:BG5", "BH5:BK5")}
lim = {"L": "труд", "E": "энергия"}
rows = [
    ["8. Мощности"],
    [""],
    ["Что считает", "Предельный рост ВВП по рабочей силе и энергии, предельный рост экспорта по логистике; сравнивает с прогнозом"],
    ["Берёт", "ANCHORS (реальный ВВП), B4_LABOUR (занятость), B5_EXTERNAL (реальный экспорт), SCENARIOS (мощность энергосистемы, порты), COEFS"],
    ["Пишет в ANCHORS", "ничего: блок только проверяет. Итог — на листе CHECKS"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Потенциал — самый высокий рост, который выдерживает ограничение. Превышение > 0 — прогноз упирается в узкое место (строка «Узкое место»)."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Откуда"],
    ["GDP_G", "Рост реального ВВП (прогноз)", "%"] + [f"=SUM(ANCHORS!{b})/SUM(ANCHORS!{a})*100-100" for a, b in YEARS.values()] + ["ANCHORS"],
    ["EMPL_G", "Рост занятости", "%", ""] + [f"=B4_LABOUR!{c}23" for c in "EFG"] + ["B4_LABOUR"],
    ["ENERGY_CAP", "Доступная мощность энергосистемы в пик", "ГВт", ""] + [f"=SCENARIOS!{s}{SL.Y['CAP']}" for s in "LMN"] + ["SCENARIOS"],
    ["PORTS", "Пропускная способность морских портов", "млн т в год", ""] + [f"=SCENARIOS!{s}{SL.Y['PORTS']}" for s in "LMN"] + ["SCENARIOS"],
    ["EXP_G", "Рост реального экспорта (прогноз)", "%"] + [f"=B5_EXTERNAL!{c}11" for c in "DEFG"] + ["B2_DEMAND через B5"],
    [""],
    ["2. Потенциал и превышение, %"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["POT_L", "Потенциал по рабочей силе", f"рост занятости + {k('CAP','PROD_MAX')}% производительности", ""]
    + [f"=((1+{c}12/100)*(1+{C('CAP','PROD_MAX')}/100)-1)*100" for c in "EFG"],
    ["POT_E", "Потенциал по энергии", f"рост мощности + {k('CAP','EI')}% снижения электроёмкости", "", ""]
    + [f"=({c}13/{p}13*(1+{C('CAP','EI')}/100)-1)*100" for c, p in pairs[1:]]
    + ["2026 — база (мощность 2025 не задана); удары по энергетике — в самой мощности, ГВт"],
    ["POT_X", "Потенциал роста экспорта по логистике", f"{k('CAP','SEA_SHARE')} × рост портов + {1 - 0.6:g} × {k('CAP','LAND_G')}% суши".replace(".", ","), "", ""]
    + [f"=({C('CAP','SEA_SHARE')}*({c}14/{p}14-1)+(1-{C('CAP','SEA_SHARE')})*{C('CAP','LAND_G')}/100)*100" for c, p in pairs[1:]],
    ["POT_MIN", "Потенциал ВВП (минимум труда и энергии)", "MIN", ""] + [f"=MIN({c}19;{c}20)" for c in "EFG"],
    ["GDP_EXCESS", "Превышение роста ВВП над потенциалом", "прогноз − потенциал, п.п.", ""] + [f"={c}11-{c}22" for c in "EFG"]
    + ["> 0 — узкое место; проверка на листе CHECKS"],
    ["BINDING", "Узкое место", "ограничение с меньшим потенциалом", ""]
    + [f"=IF({c}23<=0;\"нет\";IF(OR({c}20=\"\";{c}19<={c}20);\"{lim['L']}\";\"{lim['E']}\"))" for c in "EFG"],
    ["EXP_EXCESS", "Превышение роста экспорта над логистикой", "прогноз − потенциал, п.п.", "", ""] + [f"={c}15-{c}21" for c in "FG"]
    + ["> 0 — не хватает портов и дорог"],
]
out[f"B8_CAPACITY!A1:H{len(rows)}"] = rows

look = lambda r: f"=IFERROR(INDEX(B8_CAPACITY!$D${r}:$G${r};MATCH(D$4;B8_CAPACITY!$D$10:$G$10;0));\"\")"
status = lambda r: f"=IF(OR(D{r}=\"\";D{r}=\"нет\");\"нет данных\";IF(D{r}<=$C${r};\"OK\";\"ВНИМАНИЕ\"))"
out["CHECKS!A29:D32"] = [
    ["Мощности: рост ВВП над потенциалом", "Прогноз − минимум потенциала по труду и энергии, п.п.; не выше порога", 0, look(23)],
    ["  статус", "", "", status(29)],
    ["Логистика: рост экспорта над пропускной способностью", "Прогноз − потенциал портов и суши, п.п.; не выше порога", 0, look(25)],
    ["  статус", "", "", status(31)],
]
json.dump(out, sys.stdout, ensure_ascii=False)
