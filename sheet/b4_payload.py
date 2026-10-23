"""Build the cell contents of B4_LABOUR, its COEFS rows and ANCHORS forecast links (block B4).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Nominal wages come from their factors (macromodel.blocks.wages): last year's CPI, minimum wage,
budget pay (military and civilian), unemployment known before this year's GDP, de-shadowing.
So B1, B2, B3 and B4 have no circular reference.
"""
import json
import sys

from macromodel.blocks import wages as W
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

wc = W.coef_table()
out[f"COEFS!A{W.COEF_FIRST}:L{W.COEF_FIRST + len(wc) - 1}"] = [
    [f"W_{r['var']}", "B4", "W", r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), f"{W.FIRST}–{W.LAST}" if r["se"] else "", r["method"],
     "" if r["r2"] is None else r["r2"], "2026-10-23", r["note"]] for r in wc]
WC = lambda v: f"COEFS!$E${W.ROW[v]}"
wk = lambda v: f"{next(r['coef'] for r in wc if r['var'] == v):.2f}".replace(".", ",").replace("-", "−")
SC = dict(zip("EFG", "LMN"))  # active scenario columns in SCENARIOS
MINW_ROW, MIL_ROW, CIV_ROW, DESH_ROW = 68, 69, 70, 71
wa = W.annual().loc["2025"]

a = annual().loc["2025"]
pairs = list(zip("EFG", "DEF"))
avg = {"D": "AV{r}:AY{r}", "E": "AZ{r}:BC{r}", "F": "BD{r}:BG{r}", "G": "BH{r}:BK{r}", "C": "AR{r}:AU{r}"}
A = lambda c, r: f"AVERAGE(ANCHORS!{avg[c].format(r=r)})"
rows = [
    ["4. Рынок труда"],
    [""],
    ["Что считает", "Рабочая сила, безработица, занятость, производительность, реальная и номинальная зарплата"],
    ["Берёт", "B1_REAL (рост ВВП), SCENARIOS (миграция, мобилизация, бюджетные ориентиры по зарплатам), B3_PRICES (ИПЦ), COEFS"],
    ["Пишет в ANCHORS", "UNEMP, EMPL, WAGE_NOM; трудовые доходы (с военными) отдаёт в B2, зарплату без детенизации в B3"],
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
    ["LF", "Рабочая сила", "прошлый год + доля × миграция украинцев + доля × иностранные рабочие − мобилизация", LF_2025]
    + [f"={p}18+SCENARIOS!{s}32*{c}12+SCENARIOS!{s}33*{c}15-{c}13" for (c, p), s in zip(pairs, "LMN")]
    + ["тыс. человек; 2025 — оценка; доли — SCENARIOS строки 32–33"],
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
    ["RW_M", "Рост реальной зарплаты, модель", "номинальная по факторам / ИПЦ", ""]
    + [f"=((1+{c}29/100)/(1+{c}14/100)-1)*100" for c, p in pairs] + ["для чтения; зарплата считается в разделе 4"],
    ["NW_M", "Рост номинальной зарплаты, модель", "по факторам, раздел 4 (строка 42)", ""]
    + [f"={c}42" for c, p in pairs] + ["заполняет кварталы без факта в ANCHORS"],
    ["WAGE_NOM_G", "Рост номинальной зарплаты с учётом факта", "среднее за год по ANCHORS"]
    + [f"={A(c, 20)}/{A(p, 20)}*100-100" for c, p in [("D", "C")] + pairs] + ["по отчётности (с детенизацией)"],
    ["REAL_WAGE", "Рост реальной зарплаты с учётом факта", "номинальная / ИПЦ"]
    + [f"=((1+{c}30/100)/(1+{c}14/100)-1)*100" for c in "DEFG"] + ["по отчётности; в B2 идёт строка 46"],
    ["WAGE_NOM", "Средняя номинальная зарплата", "грн в месяц"] + [f"={A(c, 20)}" for c in "DEFG"],
    [""],
    ["4. Зарплата по факторам: бюджетные ориентиры из SCENARIOS (строки 68–71), коэффициенты из COEFS"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["MINW_G", "Рост минимальной зарплаты", "SCENARIOS строка 68, средняя за год", round(float(wa["MINW"]), 1),
     f"=(SCENARIOS!L{MINW_ROW}/{int(W.min_wage()['2025'])}-1)*100"]
    + [f"=(SCENARIOS!{SC[c]}{MINW_ROW}/SCENARIOS!{SC[p]}{MINW_ROW}-1)*100" for c, p in pairs[1:]] + ["%; 2025 = 8000 грн"],
    ["MIL_G", "Рост довольствия на одного военного", "SCENARIOS строка 69", ""]
    + [f"=SCENARIOS!{SC[c]}{MIL_ROW}" for c, p in pairs] + ["%"],
    ["CIV_G", "Рост оплаты гражданских бюджетников", "SCENARIOS строка 70 (учителя, врачи, госслужащие)", ""]
    + [f"=SCENARIOS!{SC[c]}{CIV_ROW}" for c, p in pairs] + ["%"],
    ["PUB_G", "Рост фонда оплаты труда госбюджета", f"{wk('MIL_CB')} × военные + остальное × гражданские", round(float(wa["PUB"]), 1)]
    + [f"={WC('MIL_CB')}*{c}37+(1-{WC('MIL_CB')})*{c}38" for c, p in pairs] + ["%; доля военных COEFS"],
    ["DU_W", "Изменение безработицы для зарплат", "закон Оукена на ВВП прошлого года + изменение рабочей силы", float(a["DU"])]
    + [f"={C('U','const')}+{C('U','GDP')}*{p}11+{C('U','SUPPLY')}*{c}19" for c, p in pairs]
    + ["п.п.; без ВВП текущего года: нет циклической ссылки"],
    ["DESH", "Детенизация", "SCENARIOS строка 71", ""] + [f"=SCENARIOS!{SC[c]}{DESH_ROW}" for c, p in pairs]
    + ["п.п. к росту зарплаты по отчётности; не новый доход"],
    ["NW_F", "Рост номинальной зарплаты по факторам",
     f"{wk('const')} + {wk('CPI_L')} × ИПЦ прошлого года + {wk('MINW')} × минимальная + {wk('PUB')} × фонд госбюджета "
     f"{wk('DU')} × изменение безработицы + детенизация", ""]
    + [f"={WC('const')}+{WC('CPI_L')}*{p}14+{WC('MINW')}*{c}36+{WC('PUB')}*{c}39+{WC('DU')}*{c}40+{c}41" for c, p in pairs]
    + ["%; оценка 2016–2025 без 2022, COEFS W_"],
    ["WAGE_ECON", "Рост зарплаты без детенизации", "строка 30 − детенизация", float(wa["WAGE"])]
    + [f"={c}30-{c}41" for c, p in pairs] + ["идёт в B3 (ИПЦ)"],
    ["RW_ECON", "Рост реальной зарплаты без детенизации", "строка 43 / ИПЦ"]
    + [f"=((1+{c}43/100)/(1+{c}14/100)-1)*100" for c in "DEFG"],
    ["MIL_REAL", "Рост реального довольствия военных", "строка 37 / ИПЦ", ""]
    + [f"=((1+{c}37/100)/(1+{c}14/100)-1)*100" for c, p in pairs],
    ["INCOME", "Рост реальных трудовых доходов домохозяйств", f"(1 − {wk('MIL_HH')}) × зарплата + {wk('MIL_HH')} × довольствие военных", ""]
    + [f"=(1-{WC('MIL_HH')})*{c}44+{WC('MIL_HH')}*{c}45" for c, p in pairs] + ["идёт в B2 (потребление)"],
]
out[f"B4_LABOUR!A1:H{len(rows)}"] = rows

look = lambda c, r: f"INDEX(B4_LABOUR!$E${r}:$G${r};MATCH({c}$2;B4_LABOUR!$E$10:$G$10;0))"
out["ANCHORS!AV18:AY19"] = [["=B4_LABOUR!$D$22"] * 4, ["=B4_LABOUR!$D$20"] * 4]
# 2026Q1-Q2 have no survey data either, so EMPL and UNEMP start at AZ
out["ANCHORS!AZ18"] = [[f"={look('AZ', 22)}"]]
out["ANCHORS!AZ19"] = [[f"={look('AZ', 20)}"]]
out["ANCHORS!BB20"] = [[f"=AX20*(1+{look('BB', 29)}/100)"]]
out["B2_DEMAND!E14:H14"] = [["=B4_LABOUR!E46", "=B4_LABOUR!F46", "=B4_LABOUR!G46", "из B4_LABOUR: зарплата без детенизации и довольствие военных"]]
out["B3_PRICES!E12:H12"] = [["=B4_LABOUR!E43", "=B4_LABOUR!F43", "=B4_LABOUR!G43", "из B4_LABOUR: с учётом факта, без детенизации"]]
# Budget targets as numbers, by scenario (SCENARIOS rows 65-71); written on first build only (--coefs skips)
choose = lambda r, cols: f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{';'.join(f'{c}{r}' for c in cols)})"
act = lambda r: [choose(r, cols) for cols in ("CFI", "DGJ", "EHK")]
out[f"SCENARIOS!A{MINW_ROW - 3}:O{DESH_ROW}"] = [
    ["Зарплаты: бюджетные ориентиры"],
    ["Параметр", "Единицы", "База", "", "", "Пессимистичный", "", "", "Оптимистичный", "", "", "Активный", "", "", "Источник"],
    ["", ""] + [2026, 2027, 2028] * 4,
    ["Минимальная зарплата", "грн в месяц, средняя за год"] + [8647, 9546, 10377] * 3 + act(MINW_ROW)
    + ["Закон о госбюджете 2026; 2027–2028 — Бюджетная декларация 2027–2029"],
    ["Денежное довольствие на одного военного (ставки и боевые выплаты)", "% рост за год"] + [10, 5, 5, 10, 15, 10, 10, 0, 0] + act(MIL_ROW)
    + ["Повышения в бюджете 2026 нет, но фонд оплаты труда госбюджета за 1 пол. 2026 +18% г/г (боевые выплаты, контракты). "
       "Дальше оценка Claude: пессимистичный — повышение для набора, оптимистичный — без повышений после прекращения огня. "
       "Численность военных меняет рабочую силу (строка 23), а не ставку"],
    ["Оплата труда гражданских бюджетников (учителя, врачи, госслужащие)", "% рост средней за год"]
    + [20, 10, 8, 20, 5, 5, 20, 12, 10] + act(CIV_ROW)
    + ["2026: учителя +30% с 1 января; остальные меньше; оценка Claude, уточнить по бюджету"],
    ["Детенизация зарплат", "п.п. к росту средней зарплаты"] + [0.5, 1, 1, 0, 0.5, 0.5, 0.5, 1.5, 2] + act(DESH_ROW)
    + ["Оценка Claude: вывод зарплат из тени (налоговые изменения, контроль ГНС); растёт после войны"],
]
if "--coefs" in sys.argv:
    out = {k: v for k, v in out.items() if not k.startswith("SCENARIOS")}
json.dump(out, sys.stdout, ensure_ascii=False)
