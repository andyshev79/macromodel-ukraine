"""Build the cell contents of B5_EXTERNAL, its COEFS rows and ANCHORS forecast links (block B5).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
The exchange rate rule uses last year's reserves, so B2-B5 have no circular reference.
"""
import json
import sys

from macromodel.blocks.external import annual, coef_table

COEF_FIRST = 53  # B1 5-22, B2 23-35, B3 36-44, B4 45-52
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}
C = lambda eq, v: f"COEFS!$E${crow[(eq, v)]}"
k = lambda eq, v: f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (eq, v)):g}".replace(".", ",")

out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(coefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B5", r["eq"], r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), "2016–2025" if r["se"] else "", r["method"],
     "" if r["r2"] is None else r["r2"], "2026-10-22", r["note"]] for r in coefs]

a = annual().loc["2025"]
pairs = list(zip("EFG", "DEF"))
EFG = lambda f: [f(c, p) for c, p in pairs]
rows = [
    ["5. Внешний сектор"],
    [""],
    ["Что считает", "Экспорт и импорт в USD, платёжный баланс, потребность во внешнем финансировании, резервы, курс"],
    ["Берёт", "B2_DEMAND (реальный экспорт и импорт), B3_PRICES (газ, инфляция), SCENARIOS (пшеница, сталь, финансирование), COEFS"],
    ["Пишет в ANCHORS", "EXP_USD, IMP_USD, RES_USD, FIN_NEED_USD, FIN_RECEIVED_USD; курс 2027–2028 отдаёт в B3"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Годовые значения, млн USD. Разрыв > 0 покрывается резервами; ниже 3 месяцев импорта — проверка на листе CHECKS."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Откуда"],
    ["EXPR", "Рост реального экспорта", "%"] + [f"=B2_DEMAND!{c}23" for c in "DEFG"] + ["B2_DEMAND"],
    ["IMPR", "Рост реального импорта", "%"] + [f"=B2_DEMAND!{c}24" for c in "DEFG"] + ["B2_DEMAND"],
    ["WHEAT", "Цена пшеницы", "USD/т", 230] + [f"=SCENARIOS!{s}25" for s in "LMN"] + ["SCENARIOS"],
    ["STEEL", "Цена стали (заготовка)", "USD/т", 445] + [f"=SCENARIOS!{s}26" for s in "LMN"] + ["SCENARIOS"],
    ["PX", "Рост цен экспортного сырья", "%", round(float(a["PX"]), 1)] + EFG(lambda c, p: f"=(({c}13/{p}13-1)+({c}14/{p}14-1))/2*100") + ["среднее пшеницы и стали"],
    ["TTF_G", "Рост цены газа TTF", "%"] + [f"=B3_PRICES!{c}14" for c in "DEFG"] + ["B3_PRICES"],
    ["FIN", "Внешнее финансирование бюджета", "млн USD", round(float(a["FIN_RECEIVED_USD"]))] + [f"=SCENARIOS!{s}20" for s in "LMN"] + ["SCENARIOS (обещано)"],
    ["HICP", "Инфляция еврозоны", "%"] + [f"=B3_PRICES!{c}15" for c in "DEFG"] + ["B3_PRICES"],
    ["CPI", "ИПЦ Украины", "%"] + [f"=B3_PRICES!{c}20" for c in "DEFG"] + ["B3_PRICES"],
    [""],
    ["2. Торговля и платёжный баланс, млн USD"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["EXP_P", "Рост цен экспорта в USD", f"{k('EXP_P','const')} + {k('EXP_P','PX')} × рост цен сырья", round(float(a["EXP_P"]), 1)]
    + EFG(lambda c, p: f"={C('EXP_P','const')}+{C('EXP_P','PX')}*{c}15") + ["%, R² 0,87"],
    ["EXP_USD", "Экспорт товаров и услуг", "прошлый год × реальный рост × рост цен", round(float(a["EXP_USD"]))]
    + EFG(lambda c, p: f"={p}24*(1+{c}11/100)*(1+{c}23/100)"),
    ["IMP_P", "Рост цен импорта в USD", f"{k('IMP_P','const')} + {k('IMP_P','TTF')} × рост цены газа", round(float(a["IMP_P"]), 1)]
    + EFG(lambda c, p: f"={C('IMP_P','const')}+{C('IMP_P','TTF')}*{c}16") + ["%, R² 0,58"],
    ["IMP_USD", "Импорт товаров и услуг", "прошлый год × реальный рост × рост цен", round(float(a["IMP_USD"]))]
    + EFG(lambda c, p: f"={p}26*(1+{c}12/100)*(1+{c}25/100)"),
    ["TRADE_BAL", "Сальдо торговли", "экспорт − импорт"] + [f"={c}24-{c}26" for c in "DEFG"],
    ["REMIT", "Частные переводы", "на уровне 2025", round(float(a["REMIT_USD"]))] + EFG(lambda c, p: f"={p}28"),
    ["FDI", "Прямые инвестиции (чистые обязательства)", "на уровне 2025", round(float(a["FDI_L_USD"]))] + EFG(lambda c, p: f"={p}29"),
    ["OTHER", "Прочие потоки", "средний остаток 2022–2025", round(float(a["OTHER"]))] + EFG(lambda c, p: f"={C('BOP','OTHER')}")
    + ["доходы, погашения долга, частный отток"],
    ["FIN_NEED", "Потребность во внешнем финансировании", "−(сальдо + переводы + ПИИ + прочие)"] + [f"=-({c}27+{c}28+{c}29+{c}30)" for c in "DEFG"],
    ["FIN_RECEIVED", "Получено внешнего финансирования", "из драйверов"] + [f"={c}17" for c in "DEFG"],
    ["FIN_GAP", "Разрыв (потребность − получено)", "> 0: покрывается резервами"] + [f"={c}31-{c}32" for c in "DEFG"],
    ["RES", "Международные резервы, конец года", "прошлый год − разрыв", round(float(a["RES"]))] + EFG(lambda c, p: f"={p}34-{c}33"),
    ["RES_M", "Резервы, месяцев импорта", "резервы / импорт × 12"] + [f"={c}34/{c}26*12" for c in "DEFG"] + ["проверка на листе CHECKS"],
    ["RES_SHORT", "Не хватает до 3 месяцев импорта", "дополнительное финансирование"] + [f"=MAX(0;3*{c}26/12-{c}34)" for c in "DEFG"],
    [""],
    ["3. Курс"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["FX_DEP", "Девальвация гривны (средний курс)", "ИПЦ прошлого года − инфляция еврозоны + 3 п.п. × нехватка резервов ниже 5 месяцев",
     "=B3_PRICES!D11", "=B3_PRICES!E11"]
    + [f"={p}19-{c}18+{C('FX','RES')}*MAX(0;{C('FX','MONTHS')}-{p}35)" for c, p in pairs[1:]] + ["2026 — факт и данные НБУ; резервы берутся с лагом"],
    ["FX_AVG", "Курс UAH/USD, средний", "грн за 1 USD"] + [f"=AVERAGE(ANCHORS!{r})" for r in ["AV12:AY12", "AZ12:BC12", "BD12:BG12", "BH12:BK12"]],
]
out[f"B5_EXTERNAL!A1:H{len(rows)}"] = rows

look = lambda c, r: f"INDEX(B5_EXTERNAL!$E${r}:$G${r};MATCH({c}$2;B5_EXTERNAL!$E$10:$G$10;0))"
gr = lambda c, r: f"INDEX(B5_EXTERNAL!$E${r}:$G${r};MATCH({c}$2;B5_EXTERNAL!$E$10:$G$10;0))/INDEX(B5_EXTERNAL!$D${r}:$F${r};MATCH({c}$2;B5_EXTERNAL!$E$10:$G$10;0))"
out["ANCHORS!BB21"] = [[f"=AX21*{gr('BB', 24)}"]]
out["ANCHORS!BB22"] = [[f"=AX22*{gr('BB', 26)}"]]
out["ANCHORS!BC24"] = [[f"={look('BC', 34)}"]]  # 2026Q3 reserves are actual
out["ANCHORS!AZ28"] = [[f"={look('AZ', 31)}/4"]]
# 2026 already has two actual quarters of financing received: the rest of the year is split over Q3-Q4
out["ANCHORS!BB29"] = [["=(B5_EXTERNAL!$E$32-SUM($AZ29:$BA29))/2"]]
out["ANCHORS!BD29"] = [[f"={look('BD', 32)}/4"]]
out["B3_PRICES!F11:G11"] = [["=B5_EXTERNAL!F40", "=B5_EXTERNAL!G40"]]
out["B3_PRICES!H11"] = [["2026: курс из ANCHORS. 2027–2028 — из B5_EXTERNAL (инфляционный разрыв и резервы)"]]
out["CHECKS!A23:C24"] = [["Резервы, месяцев импорта", "Резервы / импорт × 12; не ниже порога", 3], ["  статус"]]
json.dump(out, sys.stdout, ensure_ascii=False)
