"""Build the cell contents of B9_CONSTRUCTION, its COEFS rows and SCENARIOS rows (block B9).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys

from macromodel import scenario_layout as SL
from macromodel.blocks.construction import COEF_FIRST, KINDS, ROW, area_growth, coef_rows, fact_ytd, history, kind_facts

num = lambda v, d=1: f"{v:.{d}f}".replace(".", ",").replace("-", "−")
fnum = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")  # inside formulas
C = lambda code: f"COEFS!$E${ROW[code]}"
cv = {r["code"]: r["coef"] for r in coef_rows()}
h = history()
e_civ = next(f"{r['period']}" for r in coef_rows() if r['code'] == 'F_CIVIL_HH')
ft = fact_ytd()  # Jan..last month of the current year, MacroStat
kf = kind_facts()  # by kind of construction, Ukrstat
ag = area_growth()  # floor area put into service and started
YRS = "DEFG"  # 2025..2028
pc = dict(zip("EFG", "DEF"))
ACT = dict(zip("EFG", "LMN"))
B4Q = {"D": ("D", "G"), "E": ("H", "K"), "F": ("L", "O"), "G": ("P", "S")}

mix = lambda c: f"{C('F_W_CIVIL')}*{c}22+{C('F_W_INFRA')}*{c}23+{C('F_W_FORT')}*{c}24+{c}14"  # block weights + rate

out = {}
rows = coef_rows()
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(rows) - 1}"] = [
    [r["code"], "B9", r["eq"], r["var"], float(r["coef"]), "" if r["se"] is None else float(r["se"]),
     "" if not r["se"] else round(float(r["coef"]) / float(r["se"]), 1), r["period"], r["method"],
     "" if r["r2"] is None else float(r["r2"]), "2026-10-26", r["note"]] for r in rows]

# SCENARIOS: financing of reconstruction, bn USD (base / pessimistic / optimistic), active columns L:N
FIN_ROW = SL.RECON  # SCENARIOS annual table, active columns L:N
fin = [2, 6, 8, 2, 2, 5, 3, 8, 10]
# the annual SCENARIOS rows are typed in the annual table since 2026-10-29 (labels: scenarios_quarterly_payload)

text = [
    ["9. Строительство"],
    [""],
    ["Что считает", "Рост строительства по трём блокам: жильё и коммерция, инфраструктура и восстановление, фортификации; "
                    "проверки: история, деньги на восстановление, рабочие руки, энергия"],
    ["Берёт", "B2_DEMAND (потребление, ВНОК), B1_REAL (оборона, ВВП, мощность энергосистемы), B4_LABOUR (демобилизация), "
              "B5_EXTERNAL (курс), B7_MONETARY (ставка), SCENARIOS (восстановление, его финансирование), COEFS"],
    ["Пишет в", "B1_REAL строка 23 (ВДС строительства)"],
    ["Статус", "в работе: версия 2 (2026-10-26): веса и уравнение зданий — по индексам Госстата по видам строительства; доля фортификаций — оценка Claude"],
    ["Как читать", "Годовые значения. Строительство — около 1,7% ВВП (2025): даже быстрый рост добавляет к ВВП немного, "
                   "главный эффект восстановления идёт через материалы, транспорт и импорт."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Источник"],
    ["HH", "Рост потребления домохозяйств", "% г/г", "=B2_DEMAND!D20"] + [f"=B2_DEMAND!{c}20" for c in "EFG"] + ["B2_DEMAND"],
    ["DEF_L", "Рост реальных оборонных расходов", "% г/г", ""] +
    [f"=(B1_REAL!{c}15/B1_REAL!{pc[c]}15)*(1+B1_REAL!{pc[c]}31/100)*100-100" for c in "EFG"] +
    ["доля в ВВП × ВВП прошлого года (без циклической ссылки)"],
    ["REC_PP", "Восстановление", "п.п. к росту ВНОК", 0] + [f"=SUMIF(B2_DEMAND!$H$30:$BK$30;{c}$10;B2_DEMAND!$H$55:$BK$55)/4" for c in "EFG"] +
    [f"SCENARIOS строка {SL.PEACE_I} по кварталам после прекращения огня (B2_DEMAND раздел 5), среднее за год"],
    ["RATE_F", "Влияние ставки на строительство", "п.п.", ""] + [f"=B7_MONETARY!{c}41" for c in "EFG"] + ["B7_MONETARY"],
    ["REC_FIN", "Деньги на восстановление", "млрд USD", ""] + [f"=SCENARIOS!{ACT[c]}{FIN_ROW}" for c in "EFG"] +
    [f"SCENARIOS строка {FIN_ROW}"],
    ["GFCF_USD", "ВНОК в реальном выражении", "млрд USD 2025", round(h["gfcf_usd"], 1)] +
    [f"={pc[c]}16*(1+B2_DEMAND!{c}22/100)" for c in "EFG"] + ["2025 — Госстат / средний курс; дальше рост B2"],
    ["DEMOB", "Демобилизовано за год", "тыс. человек", ""] +
    [f"=SUM(B4_LABOUR!{B4Q[c][0]}18:{B4Q[c][1]}18)" for c in "EFG"] + ["B4_LABOUR строка 18"],
    ["CAP_G", "Рост доступной мощности энергосистемы", "%", ""] +
    [f"=(B1_REAL!{c}13/B1_REAL!{pc[c]}13-1)*100" for c in "EFG"] + ["B1_REAL строка 13"],
    ["FACT", f"Факт строительной продукции, январь–{ft['last']} {ft['year']}", "% г/г", "", round(ft["yoy"], 1), "", "",
     f"MacroStat, лист SectorIndexes M (Госстат, нарастающим итогом): {ft['months']} мес. из 12"],
    ["2. Блоки строительства, рост % г/г"],
    ["Код", "Блок", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["F_CIVIL", "Жильё и коммерческая недвижимость",
     f"{num(cv['F_CIVIL_const'], 2)} + {num(cv['F_CIVIL_HH'], 2)} × рост потребления домохозяйств", ""] +
    [f"={C('F_CIVIL_const')}+{C('F_CIVIL_HH')}*{c}11" for c in "EFG"] +
    [f"индекс строительства зданий (Госстат), {e_civ} без войны: спрос населения и бизнеса"],
    ["F_INFRA", "Инфраструктура и восстановление", "восстановление / вес блока (весь эффект ложится на этот блок)", ""] +
    [f"=COEFS!$E$171*{c}13/{C('F_W_INFRA')}" for c in "EFG"] +
    ["без восстановления — на уровне прошлого года; COEFS GVA_F_REC (строка 171)"],
    ["F_FORT", "Фортификации и оборонное строительство", "рост реальных оборонных расходов", ""] +
    [f"={c}12" for c in "EFG"] + ["при мире падает вместе с оборонными расходами"],
    ["CONSTR", "Строительная продукция", f"веса блоков + влияние ставки; {ft['year']}: факт {ft['months']} мес. + модель на остаток года",
     round(h["constr_25"], 1)] +
    [f"=({ft['months']}*{c}19+{12 - ft['months']}*({mix(c)}))/12" if c == "E" else f"={mix(c)}" for c in "EFG"] +
    [f"веса {num(cv['F_W_CIVIL'], 2)} / {num(cv['F_W_INFRA'], 2)} / {num(cv['F_W_FORT'], 2)}: здания и инженерные сооружения — "
     f"Госстат 2023–2025, доля фортификаций — оценка Claude"],
    ["GVA_F", "ВДС строительства", f"{num(cv['F_LINK_const'], 2)} + {num(cv['F_LINK_CONSTR'], 2)} × строительная продукция",
     round(h["gva_f_25"], 1)] +
    [f"={C('F_LINK_const')}+{C('F_LINK_CONSTR')}*{c}25" for c in "EFG"] + ["идёт в B1_REAL строка 23"],
    [""],
    ["3. Проверки"],
    ["Код", "Проверка", "Правило", 2025, 2026, 2027, 2028, "Комментарий"],
    ["CHK_HIST", "Рост в коридоре истории",
     f"10–90-й процентиль {h['years']} без войны: от {num(h['lo'])} до {num(h['hi'])}%", ""] +
    [f"=IF(AND({c}25>={fnum(h['lo'])};{c}25<={fnum(h['hi'])});\"OK\";\"ВНИМАНИЕ: главная причина — \"&"
     f"INDEX({{\"жильё\"\\\"восстановление\"\\\"фортификации\"}};MATCH(MAX(ABS({C('F_W_CIVIL')}*{c}22);ABS({C('F_W_INFRA')}*{c}23);"
     f"ABS({C('F_W_FORT')}*{c}24));{{ABS({C('F_W_CIVIL')}*{c}22)\\ABS({C('F_W_INFRA')}*{c}23)\\ABS({C('F_W_FORT')}*{c}24)}};0)))"
     for c in "EFG"] + ["выход объяснён сценарием (восстановление, мир) — сознательный выбор"],
    ["REC_NEED", "Нужно денег на восстановление", "п.п. восстановления × ВНОК прошлого года, млрд USD", ""] +
    [f"={c}13/100*{pc[c]}16" for c in "EFG"] + [""],
    ["REC_CHK", "Восстановление обеспечено деньгами", "нужно ≤ есть", ""] +
    [f"=IF({c}31<={c}15;\"OK\";\"ВНИМАНИЕ: не хватает \"&ROUND({c}31-{c}15;1)&\" млрд USD\")" for c in "EFG"] +
    [f"если не хватает — снизить SCENARIOS строку {SL.PEACE_I} или поднять финансирование"],
    ["LAB_NEED", "Нужно дополнительных рабочих", "занятые × ((1 + рост) / (1 + производительность) − 1), тыс.", ""] +
    [f"={C('F_LAB_BASE')}*((1+{c}25/100)/(1+{C('F_LAB_PROD')}/100)-1)" for c in "EFG"] +
    ["база — занятые 2025 (оценка); упрощённо от уровня 2025"],
    ["LAB_SUPPLY", "Приток рабочих", "демобилизованные × доля + естественный приток, тыс.", ""] +
    [f"={c}17*{C('F_LAB_DEMOB')}+{C('F_LAB_BASE')}*{C('F_LAB_NAT')}/100" for c in "EFG"] + [""],
    ["LAB_CHK", "Рабочих хватает", "нужно ≤ приток", ""] +
    [f"=IF({c}33<={c}34;\"OK\";\"ВНИМАНИЕ: не хватает \"&ROUND({c}33-{c}34;0)&\" тыс. рабочих\")" for c in "EFG"] +
    ["узкое место: без притока рабочих рост строительства невозможен"],
    ["EN_CHK", "Энергия", "рост строительства > 15% при падении мощности энергосистемы — ВНИМАНИЕ", ""] +
    [f"=IF(AND({c}25>15;{c}18<0);\"ВНИМАНИЕ: стройка растёт, мощность падает\";\"OK\")" for c in "EFG"] +
    ["материалы (цемент, металл) — проверка появится с данными о производстве"],
]
FY = ["2023", "2024", "2025", str(kf["year"])]
fk = kf["facts"]
gr = ag["growth"]
part = f"янв–{kf['last'][:3]} {kf['year']}"
text += [
    [""],
    ["4. Факт по видам строительства и опережающие индикаторы (Госстат)"],
    ["Код", "Показатель", "Единицы", 2023, 2024, 2025, part, "Источник"],
] + [[f"K_{k}", f"Индекс: {name.lower()}", "% г/г, с начала года"] + [round(fk[k][y], 1) for y in FY] +
     ["Госстат, индекс строительной продукции по видам (прислал Андрей 2026-10-26)"] for k, name in KINDS.items()] + [
    ["A_RES_DONE", "Ввод жилья, общая площадь", "% г/г", *[round(gr["RES_DONE"][y], 1) for y in FY],
     f"Госстат; {ag['year']} — {ag['quarters']} кв. нарастающим итогом; 2025 — {num(ag['res_done'], 2)} млн м²"],
    ["A_NRES_DONE", "Ввод нежилых зданий, общая площадь", "% г/г", *[round(gr["NRES_DONE"][y], 1) for y in FY], "Госстат"],
    ["A_START", "Начато строительство зданий, общая площадь", "% г/г", *[round(gr["START"][y], 1) for y in FY],
     "жилые и нежилые; опережает работы на 1–2 года"],
    ["A_RES_START", "  в том числе жилых", "% г/г", *[round(gr["RES_START"][y], 1) for y in FY], "Госстат"],
    ["A_NRES_START", "  в том числе нежилых", "% г/г", *[round(gr["NRES_START"][y], 1) for y in FY], "Госстат"],
    [""],
    ["5. Проверки по видам строительства"],
    ["Код", "Проверка", "Правило", 2025, 2026, 2027, 2028, "Комментарий"],
]
R = {r[0]: i + 1 for i, r in enumerate(text) if r and r[0]}
eng = f"({C('F_W_INFRA')}*E23+{C('F_W_FORT')}*E24)/({C('F_W_INFRA')}+{C('F_W_FORT')})"
text += [
    ["KIND_BLD", f"Блок «жильё и коммерция» {kf['year']} против факта зданий", "|модель − факт| ≤ 10 п.п.", "",
     f"=IF(ABS(E22-G{R['K_BLD']})<=10;\"OK\";\"ВНИМАНИЕ: модель \"&ROUND(E22;1)&\", факт \"&G{R['K_BLD']})", "", "",
     "модель — годовой рост; факт — с начала года"],
    ["KIND_ENG", f"Инфраструктура и фортификации {kf['year']} против факта инженерных сооружений",
     "|модель − факт| ≤ 10 п.п.", "",
     f"=IF(ABS({eng}-G{R['K_ENG']})<=10;\"OK\";\"ВНИМАНИЕ: модель \"&ROUND({eng};1)&\", факт \"&G{R['K_ENG']})", "", "",
     "среднее двух блоков с их весами"],
    ["START_CHK", "Здания следуют за начатым строительством",
     "начато > +10%, а здания следующего года < 0 — ВНИМАНИЕ (и наоборот: начато < −10%, а здания > +10%)", "", "",
     f"=IF(OR(AND(G{R['A_START']}>10;F22<0);AND(G{R['A_START']}<-10;F22>10));\"ВНИМАНИЕ: здания \"&ROUND(F22;1)&\" при начатом \"&ROUND(G{R['A_START']};1)&\"%\";\"OK\")",
     "", f"начато {ag['year']}, {ag['quarters']} кв., к прошлому году"],
]
out[f"B9_CONSTRUCTION!A1:H{len(text)}"] = text
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
