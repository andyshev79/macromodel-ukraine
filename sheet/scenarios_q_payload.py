"""Optional quarterly detail in SCENARIOS and its links to B5, ANCHORS and the annual inputs.

Scenarios stay annual. A few inputs can be given by quarter:
- external financing tranches and energy strike intensity, per scenario;
- near-term quarters from fresh data and NBU estimates (GDP, CPI, FX, NBU rate), for all scenarios.
An empty quarter keeps the annual logic: the annual amount is split over the empty quarters
(financing) or the annual value is used (strikes, near-term rows).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Quarter columns C:L of SCENARIOS are 2026Q3..2028Q4, the same order as ANCHORS BB:BK.
"""
import json
import sys

QUARTERS = [f"{y}Q{q}" for y in (2026, 2027, 2028) for q in (1, 2, 3, 4)][2:]
QCOLS = "CDEFGHIJKL"
HEAD = 38
R = {"FIN": (40, 41, 42), "STRIKES": (43, 44, 45), "FIN_ACT": 46, "STRIKES_ACT": 47,
     "GDP": 50, "CPI": 51, "FX": 52, "RATE": 53}
YEAR_COLS = {2026: ("C", "D"), 2027: ("E", "H"), 2028: ("I", "L")}  # first and last quarter column per year
ANNUAL_COL = {2026: "L", 2027: "M", 2028: "N"}
blank = [""] * len(QCOLS)
choose = lambda c, rows: (f"=IFERROR(IF(CHOOSE(MATCH($C$3;$A$8:$A$10;0);{c}{rows[0]};{c}{rows[1]};{c}{rows[2]})=\"\";\"\";"
                          f"CHOOSE(MATCH($C$3;$A$8:$A$10;0);{c}{rows[0]};{c}{rows[1]};{c}{rows[2]}));\"\")")

rows = [
    ["Квартальная разбивка (необязательно)"],
    ["Пустая ячейка — модель считает как раньше: финансирование года делится поровну между пустыми кварталами, остальные строки берутся из годовых значений и уравнений. "
     "Если заполнены все кварталы года, финансирование года = их сумма. Удары: годовое значение = среднее кварталов (пустые = годовое)."],
    ["Параметр", "Единицы"] + QUARTERS,
    ["Сценарные допущения по кварталам"],
    ["Внешнее финансирование бюджета — База", "млн USD"] + blank,
    ["Внешнее финансирование бюджета — Пессимистичный", "млн USD"] + blank,
    ["Внешнее финансирование бюджета — Оптимистичный", "млн USD"] + blank,
    ["Интенсивность ударов по энергетике — База", "индекс 0–1"] + blank,
    ["Интенсивность ударов по энергетике — Пессимистичный", "индекс 0–1"] + blank,
    ["Интенсивность ударов по энергетике — Оптимистичный", "индекс 0–1"] + blank,
    ["Внешнее финансирование — активный сценарий", "млн USD"] + [choose(c, R["FIN"]) for c in QCOLS],
    ["Удары по энергетике — активный сценарий", "индекс 0–1"] + [choose(c, R["STRIKES"]) for c in QCOLS],
    [""],
    ["Ближайшие кварталы: свежие данные и оценки НБУ (для всех сценариев)"],
    ["Рост реального ВВП", "% г/г"] + blank,
    ["ИПЦ", "% г/г, среднее за квартал", 10] + blank[1:],
    ["Курс UAH/USD, средний", "грн за 1 USD", 44.69, 44.91] + blank[2:],
    ["Учётная ставка НБУ", "%, конец квартала", 16, 16] + blank[2:],
]
out = {f"SCENARIOS!A36:L{36 + len(rows) - 1}": rows}

# annual strike intensity of the active scenario = average of its quarters, empty quarters = annual value
for y, (c0, c1) in YEAR_COLS.items():
    a, q = ANNUAL_COL[y], f"{c0}{R['STRIKES_ACT']}:{c1}{R['STRIKES_ACT']}"
    base = {"L": "C17;F17;I17", "M": "D17;G17;J17", "N": "E17;H17;K17"}[a]
    out[f"SCENARIOS!{a}17"] = [[f"=IFERROR(LET(v;CHOOSE(MATCH($C$3;$A$8:$A$10;0);{base});n;COUNT({q});"
                                f"IF(n=0;v;(v*(4-n)+SUM({q}))/4));\"\")"]]

# annual financing: the sum of quarters when all forecast quarters of the year are given
fa = R["FIN_ACT"]
out["B5_EXTERNAL!E17:G17"] = [[
    f"=IF(COUNT(SCENARIOS!C{fa}:D{fa})=2;SUM(ANCHORS!AZ29:BA29)+SUM(SCENARIOS!C{fa}:D{fa});SCENARIOS!L20)",
    f"=IF(COUNT(SCENARIOS!E{fa}:H{fa})=4;SUM(SCENARIOS!E{fa}:H{fa});SCENARIOS!M20)",
    f"=IF(COUNT(SCENARIOS!I{fa}:L{fa})=4;SUM(SCENARIOS!I{fa}:L{fa});SCENARIOS!N20)"]]

ov = lambda col, r: f"INDEX(SCENARIOS!$C${r}:$L${r};MATCH({col}$4;SCENARIOS!$C${HEAD}:$L${HEAD};0))"
# quarterly financing received: given tranche, else the rest of the year over the empty quarters
for start, (y, b5, actual) in {"BB": (2026, "E", "-SUM($AZ29:$BA29)"), "BD": (2027, "F", ""), "BH": (2028, "G", "")}.items():
    c0, c1 = YEAR_COLS[y]
    q = f"SCENARIOS!${c0}${fa}:${c1}${fa}"
    n = {2026: 2, 2027: 4, 2028: 4}[y]
    out[f"ANCHORS!{start}29"] = [[f"=IF({ov(start, fa)}<>\"\";{ov(start, fa)};(B5_EXTERNAL!${b5}$32{actual}-SUM({q}))/({n}-COUNT({q})))"]]

# near-term overrides in ANCHORS (copied right over BB:BK)
o = lambda r: ov("BB", r)
out["ANCHORS!BB5"] = [[f"=IF({o(R['GDP'])}<>\"\";AX5*(1+{o(R['GDP'])}/100);BB6)"]]
out["ANCHORS!BB10"] = [[f"=IF({o(R['CPI'])}<>\"\";{o(R['CPI'])};INDEX(B3_PRICES!$E$19:$G$19;MATCH(BB$2;B3_PRICES!$E$10:$G$10;0)))"]]
out["ANCHORS!BB12"] = [[f"=IF({o(R['FX'])}<>\"\";{o(R['FX'])};BA12)"]]
out["ANCHORS!BD12"] = [[f"=IF({ov('BD', R['FX'])}<>\"\";{ov('BD', R['FX'])};AZ12*(1+INDEX(B3_PRICES!$E$11:$G$11;MATCH(BD$2;B3_PRICES!$E$10:$G$10;0))/100))"]]
out["ANCHORS!BB14"] = [[f"=IF({o(R['RATE'])}<>\"\";{o(R['RATE'])};BA14)"]]
out["ANCHORS!BD14"] = [[f"=IF({ov('BD', R['RATE'])}<>\"\";{ov('BD', R['RATE'])};BC14+(INDEX(B7_MONETARY!$E$20:$G$20;MATCH(BD$2;B7_MONETARY!$E$10:$G$10;0))-BC14)/(5-VALUE(RIGHT(BD$4;1))))"]]
json.dump(out, sys.stdout, ensure_ascii=False)
