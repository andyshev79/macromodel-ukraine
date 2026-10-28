"""Build the cell contents of B6_FISCAL, its COEFS rows and ANCHORS forecast links (block B6).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). Amounts in bn UAH.
"""
import json
import sys

import pandas as pd

from macromodel.blocks.fiscal import annual, coef_table
from macromodel.blocks.real_sector import HIST

COEF_FIRST = 60  # B1 5-22, B2 23-35, B3 36-44, B4 45-52, B5 53-59
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}
C = lambda eq, v: f"COEFS!$E${crow[(eq, v)]}"
k = lambda eq, v: f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (eq, v)):g}".replace(".", ",")

out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(coefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B6", r["eq"], r["var"], r["coef"], "", "", "2025", "калибровка", "", "2026-10-22", r["note"]]
    for r in coefs]

a = annual()
h = a.loc["2025"]
sched = pd.read_csv(HIST / "debt_schedule_y.csv", index_col=0)["external_repayment"]
sched.index = sched.index.astype(str)
Q4 = {"E": "BC", "F": "BG", "G": "BK"}  # ANCHORS columns of the fourth quarter
B5Q = {"E": "H80:K80", "F": "L80:O80", "G": "P80:S80"}  # B5_EXTERNAL quarter columns of each year (row 80: euro revaluation of FX debt)
pairs = list(zip("EFG", "DEF"))
EFG = lambda f: [f(c, p) for c, p in pairs]
r1 = lambda x: round(float(x), 1)
rows = [
    ["6. Бюджет и долг"],
    [""],
    ["Что считает", "Доходы, расходы и дефицит госбюджета, разрыв его финансирования, госдолг"],
    ["Берёт", "B3_PRICES (номинальный ВВП), SCENARIOS (оборона, финансирование), B5_EXTERNAL (курс), график погашений, COEFS"],
    ["Пишет в ANCHORS", "BUDGET_DEF, DEBT_GDP"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "млрд грн. Доли откалиброваны на 2025 год (COEFS). Разрыв > 0 — бюджету не хватает денег при обещанном финансировании."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Откуда"],
    ["GDP_NOM", "Номинальный ВВП", "млрд грн"] + [f"=B3_PRICES!{c}26" for c in "DEFG"] + ["B3_PRICES"],
    ["DEF_GDP", "Расходы на оборону", "% ВВП", r1(h["BUDGET_DEFENCE"] / h["GDP_NOM"] * 100)] + [f"=SCENARIOS!{s}21" for s in "LMN"] + ["SCENARIOS"],
    ["FIN", "Внешнее финансирование бюджета", "млн USD"] + [f"=B5_EXTERNAL!{c}17" for c in "DEFG"] + ["SCENARIOS через B5"],
    ["FX", "Курс UAH/USD, средний", "грн за 1 USD"] + [f"=B5_EXTERNAL!{c}41" for c in "DEFG"] + ["B5_EXTERNAL"],
    ["FX_DEP", "Девальвация гривны", "%"] + [f"=B5_EXTERNAL!{c}40" for c in "DEFG"] + ["B5_EXTERNAL"],
    ["DEBT_REPAY_EXT", "Погашение внешнего госдолга (основная сумма)", "млрд грн; график Минфина × прогнозный курс / курс графика",
     r1(sched["2025"])] + [f"={str(r1(sched[y])).replace('.', ',')}*{c}14/{C('DEBT','FX_SCHED')}" for c, y in zip("EFG", ["2026", "2027", "2028"])]
    + [f"график Минфина (MacroStat, лист Debt) в гривне по курсу {k('DEBT','FX_SCHED')} (COEFS DEBT_FX_SCHED); проценты — в прочих расходах"],
    [""],
    ["2. Доходы и расходы, млрд грн"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["REV_OWN", "Собственные доходы", f"{k('REV','OWN')}% ВВП", r1(h["REV_OWN"])] + EFG(lambda c, p: f"={C('REV','OWN')}/100*{c}11") + ["без грантов"],
    ["GRANTS", "Гранты", f"{k('FIN','GRANT_SHARE')} × внешнее финансирование × курс", r1(h["GRANTS"])]
    + EFG(lambda c, p: f"={C('FIN','GRANT_SHARE')}*{c}13*{c}14/1000"),
    ["REV", "Доходы всего", "собственные + гранты"] + [f"={c}20+{c}21" for c in "DEFG"],
    ["EXP_DEF", "Расходы на оборону", "доля из SCENARIOS × ВВП", r1(h["BUDGET_DEFENCE"])] + EFG(lambda c, p: f"={c}12/100*{c}11"),
    ["EXP_OTHER", "Прочие расходы", f"{k('EXP','OTHER')}% ВВП", r1(h["BUDGET_EXP"] - h["BUDGET_DEFENCE"])] + EFG(lambda c, p: f"={C('EXP','OTHER')}/100*{c}11")
    + ["соцрасходы, проценты, госуправление"],
    ["EXP", "Расходы всего", "оборона + прочие"] + [f"={c}23+{c}24" for c in "DEFG"],
    ["BUDGET_DEF", "Дефицит бюджета (+ = дефицит)", "расходы − доходы"] + [f"={c}25-{c}22" for c in "DEFG"],
    ["BUDGET_DEF_GDP", "Дефицит бюджета", "% ВВП"] + [f"={c}26/{c}11*100" for c in "DEFG"],
    [""],
    ["3. Финансирование, млрд грн"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["NEED", "Потребность в займах", "дефицит + погашение основной суммы внешнего долга"] + [f"={c}26+{c}16" for c in "DEFG"],
    ["EXT_LOANS", "Внешние займы", "(1 − доля грантов) × финансирование × курс"]
    + [f"=(1-{C('FIN','GRANT_SHARE')})*{c}13*{c}14/1000" for c in "DEFG"],
    ["DOM", "Чистое внутреннее финансирование", f"{k('FIN','DOM')}% ВВП"] + [f"={C('FIN','DOM')}/100*{c}11" for c in "DEFG"] + ["ОВГЗ, НБУ"],
    ["GAP", "Разрыв финансирования бюджета", "потребность − внешние займы − внутреннее"] + [f"={c}31-{c}32-{c}33" for c in "DEFG"]
    + ["2025 ≈ 0 по построению"],
    ["GAP_USD", "Разрыв финансирования бюджета", "млн USD"] + [f"={c}34/{c}14*1000" for c in "DEFG"] + ["проверка на листе CHECKS"],
    [""],
    ["4. Госдолг"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["DEBT", "Государственный и гарантированный долг", "валютный долг по курсу конца года + гривневый", r1(h["DEBT"])]
    + EFG(lambda c, p: f"={c}44+{c}46") + ["конец года; разрыв тоже считается долгом"],
    ["DEBT_GDP", "Госдолг", "% ВВП"] + [f"={c}39/{c}11*100" for c in "DEFG"],
    [""],
    ["FX_EOP", "Курс UAH/USD на конец года", "грн за 1 USD", round(float(h["FX_EOP"]), 2)]
    + [f"=IF(ANCHORS!{Q4[c]}13<>\"\";ANCHORS!{Q4[c]}13;ANCHORS!{Q4[c]}12)" for c in "EFG"]
    + ["ANCHORS: конец 4 кв.; где прогноза конца периода нет — средний курс 4 кв."],
    ["DEBT_FX_USD", "Валютный (внешний) госдолг", "млрд USD; прошлый год + внешние займы − погашение", r1(h["EXT_DEBT_USD"])]
    + EFG(lambda c, p: f"={p}43+({c}32-{c}16)/{c}14+SUM(B5_EXTERNAL!{B5Q[c]})")
    + ["2025 — внешний долг сектора госуправления (НБУ); + переоценка евро к доллару (B5_EXTERNAL строка 80)"],
    ["DEBT_FX", "Валютный долг в гривне", "млрд USD × курс на конец года"] + [f"={c}43*{c}42" for c in "DEFG"]
    + ["здесь прогнозный курс: Минфин показывает долг по текущему курсу"],
    ["REVAL", "Переоценка валютного долга", "долг прошлого года × изменение курса, млрд грн", ""]
    + EFG(lambda c, p: f"={p}43*({c}42-{p}42)") + ["рост долга без новых займов"],
    ["DEBT_DOM", "Гривневый госдолг", "прошлый год + дефицит − (внешние займы − погашение)", f"=D39-D44"]
    + EFG(lambda c, p: f"={p}46+{c}26-({c}32-{c}16)") + ["ОВГЗ и кредиты НБУ; валютные ОВГЗ (небольшая часть) учтены как гривневые"],
    ["FX_SHARE", "Доля валютного долга", "%"] + [f"={c}44/{c}39*100" for c in "DEFG"],
]
out[f"B6_FISCAL!A1:H{len(rows)}"] = rows

# 2026 by Treasury months: state budget balance, bn UAH (+ = deficit), from the cumulative
# figures on index.minfin.com.ua (Treasury), 28.10.2026. Months without data stay blank.
DEF_2026_M = [-17.927, 50.233, 98.034, 143.964, 133.710, -104.859, -115.890, 382.803]
MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
MC = [chr(68 + i) for i in range(12)]  # D..O
M0 = len(rows) + 2  # section title row
out[f"B6_FISCAL!A{M0}:P{M0 + 7}"] = [
    ["5. Дефицит госбюджета 2026 по месяцам (Казначейство), млрд грн, + = дефицит"],
    ["Код", "Показатель", "Единицы"] + MONTHS + ["Комментарий"],
    ["DEF_M_FACT", "Дефицит месяца, факт", "млрд грн"] + DEF_2026_M + [""] * (12 - len(DEF_2026_M))
    + ["index.minfin.com.ua (Казначейство), разница накопленных итогов; новый месяц — вписать в пустую ячейку"],
    ["DEF_M_REST", "Остаток годового дефицита на месяц без данных", "млрд грн",
     f"=IFERROR(($E$26-SUM($D${M0 + 2}:$O${M0 + 2}))/COUNTBLANK($D${M0 + 2}:$O${M0 + 2});0)"]
    + [""] * 11 + ["годовой дефицит модели (E26) минус факт, поровну на оставшиеся месяцы"],
    ["DEF_M", "Дефицит месяца: факт или остаток", "млрд грн"]
    + [f"=IF({c}{M0 + 2}<>\"\";{c}{M0 + 2};$D${M0 + 3})" for c in MC] + ["идёт в ANCHORS: 3 кв. = июл–сен, 4 кв. = остаток года"],
    ["DEF_M_2025Q4", "Средний дефицит месяца в 4 кв. 2025", "млрд грн", "=ANCHORS!$AY$27/3/1000"] + [""] * 11
    + ["самый напряжённый квартал истории (декабрьские выплаты)"],
    ["DEF_M_RATIO", "Остаток на месяц к 4 кв. 2025", "раз", f"=IFERROR(D{M0 + 3}/D{M0 + 5};0)"] + [""] * 11
    + ["> 1,5 — годовой дефицит модели вряд ли выполним за оставшиеся месяцы (CHECKS)"],
    [""],
]
look = lambda c, r: f"INDEX(B6_FISCAL!$E${r}:$G${r};MATCH({c}$2;B6_FISCAL!$E$10:$G$10;0))"
# 2026: Q3 = July-September by Treasury months (fact or rest of the year), Q4 = the rest of the annual deficit
out["ANCHORS!BB27:BC27"] = [[f"=SUM(B6_FISCAL!$J${M0 + 4}:$L${M0 + 4})*1000", "=B6_FISCAL!$E$26*1000-SUM($AZ27:$BB27)"]]
out["ANCHORS!BD27"] = [[f"={look('BD', 26)}*1000/4"]]
out["ANCHORS!BB31"] = [[f"={look('BB', 40)}"]]
out["CHECKS!A25:D26"] = [
    ["Разрыв финансирования бюджета", "Потребность − внешние займы − внутреннее, млн USD; не выше порога", 0,
     "=IFERROR(INDEX(B6_FISCAL!$D$35:$G$35;MATCH(D$4;B6_FISCAL!$D$10:$G$10;0));\"\")"],
    ["  статус", "", "", "=IF(D25=\"\";\"нет данных\";IF(D25<=$C$25;\"OK\";\"ВНИМАНИЕ\"))"]]
out["CHECKS!A43:D44"] = [
    ["Дефицит 2026: остаток года на месяц", "Сколько дефицита в месяц осталось на месяцы без данных Казначейства, "
     "к среднему месяцу 4 кв. 2025 (B6_FISCAL раздел 5); не выше порога", 1.5, f"=B6_FISCAL!D{M0 + 6}"],
    ["  статус", "", "", "=IF(D43=\"\";\"нет данных\";IF(D43<=$C$43;\"OK\";\"ВНИМАНИЕ\"))"]]
json.dump(out, sys.stdout, ensure_ascii=False)
