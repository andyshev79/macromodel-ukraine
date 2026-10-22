"""Build the cell contents of B4_LABOUR, its COEFS rows and ANCHORS forecast links (block B4).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Real wages use only last year's GDP and unemployment, so B1, B2, B3 and B4 have no circular reference.
"""
import json
import sys

from macromodel.blocks.labour import LF_2025, annual, coef_table

COEF_FIRST = 45  # B1 5-22, B2 23-35, B3 36-44
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}
C = lambda eq, v: f"COEFS!$E${crow[(eq, v)]}"

out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(coefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B4", r["eq"], r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), "2016–2025" if r["se"] else "", r["method"],
     "" if r["r2"] is None else r["r2"], "2026-10-21", r["note"]] for r in coefs]

a = annual().loc["2025"]
pairs = list(zip("EFG", "DEF"))
avg = {"D": "AV{r}:AY{r}", "E": "AZ{r}:BC{r}", "F": "BD{r}:BG{r}", "G": "BH{r}:BK{r}", "C": "AR{r}:AU{r}"}
A = lambda c, r: f"AVERAGE(ANCHORS!{avg[c].format(r=r)})"
rows = [
    ["4. Рынок труда"],
    [""],
    ["Что считает", "Рабочая сила, безработица, занятость, производительность, реальная и номинальная зарплата"],
    ["Берёт", "B1_REAL (рост ВВП), SCENARIOS (миграция, мобилизация), B3_PRICES (ИПЦ), COEFS"],
    ["Пишет в ANCHORS", "UNEMP, EMPL, WAGE_NOM; реальную зарплату отдаёт в B2, номинальную в B3"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Обследование рабочей силы прекращено после 2021: 2025 год — оценка (синие ячейки), её стоит сверить."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Откуда"],
    ["GDP", "Рост реального ВВП", "%", "=B1_REAL!D29", "=B1_REAL!E29", "=B1_REAL!F29", "=B1_REAL!G29", "B1_REAL"],
    ["MIGR", "Чистая миграция украинцев", "тыс. человек", "", "=SCENARIOS!L22", "=SCENARIOS!M22", "=SCENARIOS!N22", "SCENARIOS"],
    ["MOB", "Мобилизация (чистый отток)", "тыс. человек", "", "=SCENARIOS!L23", "=SCENARIOS!M23", "=SCENARIOS!N23", "SCENARIOS"],
    ["CPI", "ИПЦ, средний за год", "%", "=B3_PRICES!D20", "=B3_PRICES!E20", "=B3_PRICES!F20", "=B3_PRICES!G20", "B3_PRICES"],
    ["GUEST", "Чистый приток иностранных рабочих", "тыс. человек", "", "=SCENARIOS!L31", "=SCENARIOS!M31", "=SCENARIOS!N31", "SCENARIOS"],
    ["2. Рабочая сила и безработица"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["LF", "Рабочая сила", "прошлый год + 0,6 × миграция украинцев + 0,9 × иностранные рабочие − мобилизация", LF_2025]
    + [f"={p}18+{C('LF','MIGR')}*{c}12+{C('LF','GUEST')}*{c}15-{c}13" for c, p in pairs] + ["тыс. человек; 2025 — оценка"],
    ["SUPPLY", "Изменение рабочей силы", "%"] + [""] + [f"=({c}18/{p}18-1)*100" for c, p in pairs],
    ["UNEMP", "Уровень безработицы", "прошлый год − 0,39 × рост ВВП + 0,5 × изменение рабочей силы, не ниже 6%", float(a["U"])]
    + [f"=MAX({C('U','MIN')};{p}20+{C('U','const')}+{C('U','GDP')}*{c}11+{C('U','SUPPLY')}*{c}19)" for c, p in pairs]
    + ["%, закон Оукена R² 0,89; 2025 — оценка НБУ; нижняя граница COEFS!E51"],
    ["DU", "Изменение безработицы", "п.п.", float(a["DU"])] + [f"={c}20-{p}20" for c, p in pairs],
    ["EMPL", "Занятые", "рабочая сила × (1 − безработица)"] + [f"={c}18*(1-{c}20/100)" for c in "DEFG"] + ["тыс. человек"],
    ["EMPL_G", "Рост занятости", "%", ""] + [f"=({c}22/{p}22-1)*100" for c, p in pairs],
    ["PROD", "Рост производительности труда", "ВВП / занятые", ""] + [f"=(1+{c}11/100)/(1+{c}23/100)*100-100" for c, p in pairs]
    + ["проверка на листе CHECKS"],
    [""],
    ["3. Зарплаты"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["RW_M", "Рост реальной зарплаты, модель", "2 + рост ВВП прошлого года − 1 × изменение безработицы прошлого года", ""]
    + [f"={C('RW','const')}+{p}11+{C('RW','DU_L')}*{p}21" for c, p in pairs] + ["только лаги: нет циклической ссылки с B1–B3"],
    ["NW_M", "Рост номинальной зарплаты, модель", "реальная зарплата + ИПЦ прошлого года", ""]
    + [f"=((1+{c}28/100)*(1+{p}14/100)-1)*100" for c, p in pairs] + ["заполняет кварталы без факта в ANCHORS"],
    ["WAGE_NOM_G", "Рост номинальной зарплаты с учётом факта", "среднее за год по ANCHORS"]
    + [f"={A(c, 20)}/{A(p, 20)}*100-100" for c, p in [("D", "C")] + pairs] + ["идёт в B3 (ИПЦ)"],
    ["REAL_WAGE", "Рост реальной зарплаты с учётом факта", "номинальная / ИПЦ"]
    + [f"=((1+{c}30/100)/(1+{c}14/100)-1)*100" for c in "DEFG"] + ["идёт в B2 (потребление)"],
    ["WAGE_NOM", "Средняя номинальная зарплата", "грн в месяц"] + [f"={A(c, 20)}" for c in "DEFG"],
]
out[f"B4_LABOUR!A1:H{len(rows)}"] = rows

look = lambda c, r: f"INDEX(B4_LABOUR!$E${r}:$G${r};MATCH({c}$2;B4_LABOUR!$E$10:$G$10;0))"
out["ANCHORS!AV18:AY19"] = [["=B4_LABOUR!$D$22"] * 4, ["=B4_LABOUR!$D$20"] * 4]
# 2026Q1-Q2 have no survey data either, so EMPL and UNEMP start at AZ
out["ANCHORS!AZ18"] = [[f"={look('AZ', 22)}"]]
out["ANCHORS!AZ19"] = [[f"={look('AZ', 20)}"]]
out["ANCHORS!BB20"] = [[f"=AX20*(1+{look('BB', 29)}/100)"]]
out["B2_DEMAND!E14:H14"] = [["=B4_LABOUR!E31", "=B4_LABOUR!F31", "=B4_LABOUR!G31", "из B4_LABOUR (с учётом факта)"]]
out["B3_PRICES!E12:H12"] = [["=B4_LABOUR!E30", "=B4_LABOUR!F30", "=B4_LABOUR!G30", "из B4_LABOUR (с учётом факта)"]]
json.dump(out, sys.stdout, ensure_ascii=False)
