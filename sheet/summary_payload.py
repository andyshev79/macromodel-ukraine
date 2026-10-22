"""Build the SUMMARY sheet (indicators × quarters and years, one block per scenario) and SUMMARY_DATA.

The model computes one active scenario at a time (SCENARIOS!C3), so SUMMARY reads value
snapshots of each scenario kept in SUMMARY_DATA. To refresh a scenario: set SCENARIOS!C3,
paste values of ANCHORS!AR5:BK31 into SUMMARY_DATA!B{start} and ANNUAL!N5:R31 into V{start}
(start rows in BLOCK_START). Derived rows (growth, % of GDP, bn UAH) are formulas.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys

SCENARIOS = ["База", "Пессимистичный", "Оптимистичный"]
CODES = ["GDP_REAL", "GDP_REAL_P", "GDP_REAL_E", "GDP_NOM", "DEFL", "CPI_YOY", "PPI_YOY", "FX_AVG", "FX_EOP",
         "NBU_RATE", "LOAN_RATE", "DEP_RATE", "POP", "EMPL", "UNEMP", "WAGE_NOM", "EXP_USD", "IMP_USD",
         "TRADE_BAL", "RES_USD", "GFCF", "CFC", "BUDGET_DEF", "FIN_NEED_USD", "FIN_RECEIVED_USD",
         "FIN_GAP_USD", "DEBT_GDP"]  # ANCHORS rows 5-31
DERIVED = ["GDP_G", "DEF_GDP", "GDP_NOM_BN", "DEF_BN"]
BLOCK = len(CODES) + len(DERIVED)
BLOCK_START = {s: 3 + i * BLOCK for i, s in enumerate(SCENARIOS)}
QUARTERS = [f"{y}Q{q}" for y in range(2024, 2029) for q in range(1, 5)]  # data columns B:U
QCOLS = [chr(66 + i) for i in range(20)]  # B..U
YCOLS = list("VWXYZ")  # 2024..2028
LAST_DATA = BLOCK_START[SCENARIOS[-1]] + BLOCK - 1

out = {}
out["SUMMARY_DATA!A1"] = [["Снимки трёх сценариев для листа SUMMARY (значения). Обновление: выбрать сценарий в SCENARIOS!C3, "
                           "вставить значения ANCHORS!AR5:BK31 в колонку B и ANNUAL!N5:R31 в колонку V блока сценария."]]
out["SUMMARY_DATA!A2:Z2"] = [["Ключ"] + QUARTERS + list(range(2024, 2029))]
for s, start in BLOCK_START.items():
    rows = [[f"{s}|{c}"] for c in CODES]
    r = {c: start + i for i, c in enumerate(CODES)}
    g, n, d = r["GDP_REAL"], r["GDP_NOM"], r["BUDGET_DEF"]
    rows.append([f"{s}|GDP_G"] + [""] * 4 + [f"=IFERROR({c}{g}/{p}{g}*100-100;\"\")" for c, p in zip(QCOLS[4:], QCOLS)]
                + [""] + [f"=IFERROR({c}{g}/{p}{g}*100-100;\"\")" for c, p in zip(YCOLS[1:], YCOLS)])
    rows.append([f"{s}|DEF_GDP"] + [f"=IFERROR({c}{d}/{c}{n}*100;\"\")" for c in QCOLS + YCOLS])
    rows.append([f"{s}|GDP_NOM_BN"] + [f"=IFERROR({c}{n}/1000;\"\")" for c in QCOLS + YCOLS])
    rows.append([f"{s}|DEF_BN"] + [f"=IFERROR({c}{d}/1000;\"\")" for c in QCOLS + YCOLS])
    out[f"SUMMARY_DATA!A{start}:Z{start + BLOCK - 1}"] = rows

ROWS = [  # code in SUMMARY_DATA, name, units
    ("GDP_G", "Реальный ВВП", "% г/г"),
    ("GDP_NOM_BN", "Номинальный ВВП", "млрд грн"),
    ("CPI_YOY", "Инфляция (ИПЦ)", "% г/г, конец периода"),
    ("PPI_YOY", "Цены производителей (ИЦП)", "% г/г, конец периода"),
    ("FX_AVG", "Курс UAH/USD", "грн, средний"),
    ("NBU_RATE", "Учётная ставка НБУ", "%, конец периода"),
    ("LOAN_RATE", "Ставка по новым кредитам в гривне", "%, среднее"),
    ("DEP_RATE", "Ставка по новым депозитам в гривне", "%, среднее"),
    ("EMPL", "Занятые", "тыс. человек"),
    ("UNEMP", "Безработица", "%"),
    ("WAGE_NOM", "Средняя зарплата", "грн в месяц"),
    ("EXP_USD", "Экспорт товаров и услуг", "млн USD"),
    ("IMP_USD", "Импорт товаров и услуг", "млн USD"),
    ("TRADE_BAL", "Сальдо торговли", "млн USD"),
    ("RES_USD", "Международные резервы", "млн USD, конец периода"),
    ("DEF_BN", "Дефицит госбюджета", "млрд грн"),
    ("DEF_GDP", "Дефицит госбюджета", "% ВВП"),
    ("FIN_NEED_USD", "Потребность во внешнем финансировании", "млн USD"),
    ("FIN_RECEIVED_USD", "Получено внешнего финансирования", "млн USD"),
    ("FIN_GAP_USD", "Разрыв внешнего финансирования", "млн USD"),
    ("DEBT_GDP", "Госдолг", "% ВВП, конец периода"),
]
PERIODS = [p for y in range(2025, 2029) for p in [f"{y}Q{q}" for q in range(1, 5)] + [y]]  # columns D:W
HEAD, FIRST = 4, 7
STEP = len(ROWS) + 3
SUM_START = {s: FIRST + i * STEP for i, s in enumerate(SCENARIOS)}

out["SUMMARY!A1:C2"] = [["Сводная таблица прогноза"],
                        ["Показатели по кварталам и годам для трёх сценариев. Модель считает один активный сценарий, поэтому значения "
                         "берутся из снимков на листе SUMMARY_DATA; обновить — попросить Claude «обнови сводную». Годовые значения — "
                         "как на листе ANNUAL (сумма, среднее или конец года по типу показателя)."]]
out[f"SUMMARY!A{HEAD}:W{HEAD + 1}"] = [
    ["Код", "Показатель", "Единицы"] + PERIODS,
    ["", "", ""] + [f"=IF(ISNUMBER(D$4);IF(D$4&\"Q4\"<=SCENARIOS!$C$4;\"факт\";IF(D$4&\"Q1\"<=SCENARIOS!$C$4;\"факт + прогноз\";\"прогноз\"));"
                    f"IF(D$4<=SCENARIOS!$C$4;\"факт\";\"прогноз\"))".replace("D$", f"{c}$")
                    for c in [chr(68 + i) for i in range(20)]]]
masters = {}
for s, h in SUM_START.items():
    out[f"SUMMARY!A{h}:C{h + len(ROWS)}"] = [[s, f"Сценарий: {s}", ""]] + [[c, n, u] for c, n, u in ROWS]
    masters[s] = (f"SUMMARY!D{h + 1}", f"=IFERROR(INDEX(SUMMARY_DATA!$B$3:$Z${LAST_DATA};"
                                     f"MATCH($A${h}&\"|\"&$A{h + 1};SUMMARY_DATA!$A$3:$A${LAST_DATA};0);"
                                     f"MATCH(D$4;SUMMARY_DATA!$B$2:$Z$2;0));\"\")")
for s, (cell, f) in masters.items():
    out[cell] = [[f]]
if "--layout" in sys.argv:
    print(json.dumps({"BLOCK_START": BLOCK_START, "SUM_START": SUM_START, "rows": len(ROWS)}))
else:
    json.dump(out, sys.stdout, ensure_ascii=False)
