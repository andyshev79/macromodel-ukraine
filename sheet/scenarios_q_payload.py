"""Optional quarterly detail in SCENARIOS and its links to B5, ANCHORS and the annual inputs.

Scenarios stay annual. A few inputs can be given by quarter:
- external financing tranches, per scenario (strike intensity on energy removed 2026-10-29);
- near-term quarters from fresh data and NBU estimates (GDP, CPI, FX, NBU rate), for all scenarios.
An empty quarter keeps the annual logic: the annual amount is split over the empty quarters
(financing) or the annual value is used (near-term rows).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Quarter columns C:L of SCENARIOS are 2026Q3..2028Q4, the same order as ANCHORS BB:BK.
"""
import json
import sys

from macromodel import scenario_layout as SL

QUARTERS = [f"{y}Q{q}" for y in (2026, 2027, 2028) for q in (1, 2, 3, 4)][2:]
QCOLS = "CDEFGHIJKL"
HEAD = SL.Q_HEAD
F = SL.FIN_Q
R = {"FIN": (F, F + 1, F + 2), "FIN_ACT": SL.FIN_ACT,
     "GDP": SL.GDP_Q, "CPI": SL.CPI_Q, "FX": SL.FX_Q, "RATE": SL.RATE_Q}
YEAR_COLS = {2026: ("C", "D"), 2027: ("E", "H"), 2028: ("I", "L")}  # first and last quarter column per year
ANNUAL_COL = {2026: "L", 2027: "M", 2028: "N"}
blank = [""] * len(QCOLS)
choose = lambda c, rows: (f"=IFERROR(IF(CHOOSE(MATCH($C$3;$A$8:$A$10;0);{c}{rows[0]};{c}{rows[1]};{c}{rows[2]})=\"\";\"\";"
                          f"CHOOSE(MATCH($C$3;$A$8:$A$10;0);{c}{rows[0]};{c}{rows[1]};{c}{rows[2]}));\"\")")

rows = [
    ["Квартальная разбивка (необязательно)"],
    ["Пустая ячейка — модель считает как раньше: финансирование года делится поровну между пустыми кварталами, остальные строки берутся из годовых значений и уравнений. "
     "Если заполнены все кварталы года, финансирование года = их сумма."],
    ["Параметр", "Единицы"] + QUARTERS,
    ["Сценарные допущения по кварталам"],
    ["Внешнее финансирование бюджета — База", "млн USD"] + blank,
    ["Внешнее финансирование бюджета — Пессимистичный", "млн USD"] + blank,
    ["Внешнее финансирование бюджета — Оптимистичный", "млн USD"] + blank,
    ["Внешнее финансирование — активный сценарий", "млн USD"] + [choose(c, R["FIN"]) for c in QCOLS],
    [""],
    ["Ближайшие кварталы: свежие данные и оценки НБУ (для всех сценариев)"],
    ["Рост реального ВВП", "% г/г"] + blank,
    ["ИПЦ", "% г/г, среднее за квартал", 10, 12.3] + blank[2:],  # 2026Q4: Andrey's estimate
    ["Курс UAH/USD, средний", "грн за 1 USD", 44.69, 44.91] + blank[2:],
    ["Учётная ставка НБУ", "%, конец квартала", 16, 16] + blank[2:],
]
out = {f"SCENARIOS!A{SL.Q_FIN}:L{SL.Q_FIN + len(rows) - 1}": rows}

# annual financing: the sum of quarters when all forecast quarters of the year are given
fa = R["FIN_ACT"]
out["B5_EXTERNAL!E17:G17"] = [[
    f"=IF(COUNT(SCENARIOS!C{fa}:D{fa})=2;SUM(ANCHORS!AZ29:BA29)+SUM(SCENARIOS!C{fa}:D{fa});SCENARIOS!L{SL.Y['FIN']})",
    f"=IF(COUNT(SCENARIOS!E{fa}:H{fa})=4;SUM(SCENARIOS!E{fa}:H{fa});SCENARIOS!M{SL.Y['FIN']})",
    f"=IF(COUNT(SCENARIOS!I{fa}:L{fa})=4;SUM(SCENARIOS!I{fa}:L{fa});SCENARIOS!N{SL.Y['FIN']})"]]

ov = lambda col, r: f"INDEX(SCENARIOS!$C${r}:$L${r};MATCH({col}$4;SCENARIOS!$C${HEAD}:$L${HEAD};0))"
# quarterly financing received: given tranche, else the rest of the year over the empty quarters
# 2026Q3: reserves are known, so the tranche is what closes the reserve change (B5 section 5); 2026Q4 = rest of the year
out["ANCHORS!BB29:BC29"] = [[f"=IF({ov('BB', fa)}<>\"\";{ov('BB', fa)};B5_EXTERNAL!J69-(B5_EXTERNAL!I72-B5_EXTERNAL!J72+B5_EXTERNAL!J71))",
                             f"=IF({ov('BC', fa)}<>\"\";{ov('BC', fa)};B5_EXTERNAL!$E$32-SUM($AZ29:$BB29))"]]
for start, (y, b5, actual) in {"BD": (2027, "F", ""), "BH": (2028, "G", "")}.items():
    c0, c1 = YEAR_COLS[y]
    q = f"SCENARIOS!${c0}${fa}:${c1}${fa}"
    n = {2026: 2, 2027: 4, 2028: 4}[y]
    out[f"ANCHORS!{start}29"] = [[f"=IF({ov(start, fa)}<>\"\";{ov(start, fa)};(B5_EXTERNAL!${b5}$32{actual}-SUM({q}))/({n}-COUNT({q})))"]]

# near-term overrides in ANCHORS (copied right over BB:BK)
o = lambda r: ov("BB", r)
out["ANCHORS!BB5"] = [[f"=IF({o(R['GDP'])}<>\"\";AX5*(1+{o(R['GDP'])}/100);BB6)"]]
# CPI (ANCHORS row 10) is written by cpi_blocks_payload: NBU blocks in B3_PRICES section 4
# FX: given quarter, else last quarter × (1 + quarterly depreciation rule of B5_EXTERNAL row 45); B5 columns J:S = BB:BK
ACOLS = ["BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK"]
out["ANCHORS!BB12:BK12"] = [[f"=IF({ov(a, R['FX'])}<>\"\";{ov(a, R['FX'])};{p}12*(1+B5_EXTERNAL!{b}45/100))"
                             for p, a, b in zip(ACOLS, ACOLS[1:], "JKLMNOPQRS")]]
out["ANCHORS!BB14"] = [[f"=IF({o(R['RATE'])}<>\"\";{o(R['RATE'])};BA14)"]]
out["ANCHORS!BD14"] = [[f"=IF({ov('BD', R['RATE'])}<>\"\";{ov('BD', R['RATE'])};BC14+(INDEX(B7_MONETARY!$E$20:$G$20;MATCH(BD$2;B7_MONETARY!$E$10:$G$10;0))-BC14)/(5-VALUE(RIGHT(BD$4;1))))"]]
json.dump(out, sys.stdout, ensure_ascii=False)
