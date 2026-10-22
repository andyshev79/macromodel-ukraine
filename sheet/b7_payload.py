"""Build the cell contents of B7_MONETARY, its COEFS rows and ANCHORS forecast links (block B7).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). Stocks in bn UAH.
The rate rule reads this year's CPI (B3) and reserves (B5); neither depends on the rate,
so there is no circular reference.
"""
import json
import sys

from macromodel.blocks.monetary import annual, coef_table, credit_q

COEF_FIRST = 65  # B1 5-22, B2 23-35, B3 36-44, B4 45-52, B5 53-59, B6 60-64
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}
C = lambda eq, v: f"COEFS!$E${crow[(eq, v)]}"
k = lambda eq, v: f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (eq, v)):g}".replace(".", ",")

out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(coefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B7", r["eq"], r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), "2016–2025" if r["se"] else "2025", r["method"],
     "" if r["r2"] is None else r["r2"], "2026-10-22", r["note"]] for r in coefs]

h = annual().loc["2025"]
q2 = credit_q().loc["2026Q2"]  # last actual quarter of bank loans
pairs = list(zip("EFG", "DEF"))
EFG = lambda f: [f(c, p) for c, p in pairs]
bn = lambda x: round(float(x) / 1000, 1)
YEARS = {"D": "AV{r}:AY{r}", "E": "AZ{r}:BC{r}", "F": "BD{r}:BG{r}", "G": "BH{r}:BK{r}"}
avg = lambda r: [f"=AVERAGE(ANCHORS!{YEARS[c].format(r=r)})" for c in "DEFG"]
rows = [
    ["7. Монетарный блок"],
    [""],
    ["Что считает", "Учётная ставка НБУ, ставки по новым кредитам и депозитам, кредиты и депозиты в гривне, избыточная ликвидность"],
    ["Берёт", "B3_PRICES (ИПЦ, номинальный ВВП), B5_EXTERNAL (резервы), ANCHORS (факт ставок), COEFS"],
    ["Пишет в ANCHORS", "NBU_RATE (с 2027), LOAN_RATE и DEP_RATE (с 2026Q3)"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Ставка на конец года по правилу; внутри года ставка идёт к ней равными шагами. Кредиты, депозиты и сертификаты НБУ — млрд грн на конец года."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Откуда"],
    ["CPI", "ИПЦ, средний за год", "%"] + [f"=B3_PRICES!{c}20" for c in "DEFG"] + ["B3_PRICES"],
    ["GDP_NOM_G", "Рост номинального ВВП", "%"] + [f"=B3_PRICES!{c}25" for c in "DEFG"] + ["B3_PRICES"],
    ["GDP_NOM", "Номинальный ВВП", "млрд грн"] + [f"=B3_PRICES!{c}26" for c in "DEFG"] + ["B3_PRICES"],
    ["RES_M", "Резервы, месяцев импорта", "месяцев"] + [f"=B5_EXTERNAL!{c}35" for c in "DEFG"] + ["B5_EXTERNAL"],
    [""],
    ["2. Ставки, %"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["RES_PREM", "Надбавка за нехватку резервов", f"{k('RATE','RES')} п.п. × месяцев ниже {k('RATE','MONTHS')}, не больше {k('RATE','RES_MAX')}", ""]
    + EFG(lambda c, p: f"=MIN({C('RATE','RES_MAX')};{C('RATE','RES')}*MAX(0;{C('RATE','MONTHS')}-{c}14))"),
    ["RATE_M", "Учётная ставка по правилу, конец года",
     f"{k('RATE','const')} + {k('RATE','CPI')} × ИПЦ + {k('RATE','RATE_L')} × ставка прошлого года + надбавка", ""]
    + EFG(lambda c, p: f"={C('RATE','const')}+{C('RATE','CPI')}*{c}11+{C('RATE','RATE_L')}*{p}20+{c}18") + ["R² 0,73; 2026 — для сравнения с фактом"],
    ["RATE", "Учётная ставка, конец года", "2025–2026 из ANCHORS, дальше правило", "=ANCHORS!AY14", "=ANCHORS!BC14", "=F19", "=G19"],
    ["RATE_AVG", "Учётная ставка, средняя за год", "среднее кварталов ANCHORS"] + avg(14),
    ["REAL_RATE", "Реальная учётная ставка", "средняя ставка − средний ИПЦ"] + [f"={c}21-{c}11" for c in "DEFG"] + ["проверка на листе CHECKS"],
    ["LOAN_RATE", "Ставка по новым кредитам в гривне", f"{k('LOAN','const')} + {k('LOAN','RATE_AVG')} × учётная ставка"] + avg(15) + ["R² 0,73; поквартально в ANCHORS"],
    ["DEP_RATE", "Ставка по новым депозитам в гривне", f"{k('DEP','const')} + {k('DEP','RATE_AVG')} × учётная ставка"] + avg(16) + ["R² 0,47; поквартально в ANCHORS"],
    [""],
    ["3. Кредиты, депозиты и ликвидность, млрд грн"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["LOANS_G", "Рост кредитов в гривне", f"{k('LOANS_G','const')} + {k('LOANS_G','GDPN_G')} × рост номинального ВВП {k('LOANS_G','REAL')} × (ставка по кредитам − ИПЦ)".replace("  ", " ").replace("ВВП -", "ВВП − "),
     round(float(h["LOANS_G"]), 1)]
    + EFG(lambda c, p: f"={C('LOANS_G','const')}+{C('LOANS_G','GDPN_G')}*{c}12+{C('LOANS_G','REAL')}*({c}23-{c}11)") + ["%, R² 0,54"],
    ["LOANS", "Кредиты в гривне, конец года", "прошлый год × рост; 2026 — факт на июнь + полгода роста по модели", bn(h["LOANS"]),
     f"={bn(q2['LOANS_UAH'])}*(1+E28/200)".replace(".", ",")] + EFG(lambda c, p: f"={p}29*(1+{c}28/100)")[1:]
    + ["корпорации и домохозяйства"],
    ["DEPS", "Депозиты в гривне, конец года", f"{k('DEPS','GDP')}% номинального ВВП", bn(h["DEPS"])] + EFG(lambda c, p: f"={C('DEPS','GDP')}/100*{c}13")
    + ["доля 2025 года"],
    ["DEPS_G", "Рост депозитов в гривне", "%"] + EFG(lambda c, p: f"=({c}30/{p}30-1)*100"),
    ["LDR", "Кредиты / депозиты", "%"] + [f"={c}29/{c}30*100" for c in "DEFG"] + ["низкая доля — банки держат деньги в ОВГЗ и сертификатах"],
    ["CD", "Депозитные сертификаты НБУ (избыточная ликвидность)", f"прошлый год + {k('LIQ','SHARE')} × (прирост депозитов − прирост кредитов)", bn(h["CD"])]
    + EFG(lambda c, p: f"={p}33+{C('LIQ','SHARE')}*(({c}30-{p}30)-({c}29-{p}29))"),
    ["CD_DEP", "Сертификаты НБУ / депозиты", "%"] + [f"={c}33/{c}30*100" for c in "DEFG"],
]
out[f"B7_MONETARY!A1:H{len(rows)}"] = rows

look = lambda c, r: f"INDEX(B7_MONETARY!$E${r}:$G${r};MATCH({c}$2;B7_MONETARY!$E$10:$G$10;0))"
# the rate moves to the year-end value in equal steps over the quarters left
out["ANCHORS!BD14"] = [[f"=BC14+({look('BD', 20)}-BC14)/(5-VALUE(RIGHT(BD$4;1)))"]]
out["ANCHORS!BB15"] = [[f"={C('LOAN','const')}+{C('LOAN','RATE_AVG')}*BB14"]]
out["ANCHORS!BB16"] = [[f"={C('DEP','const')}+{C('DEP','RATE_AVG')}*BB14"]]
out["CHECKS!A27:D28"] = [
    ["Реальная учётная ставка", "Средняя ставка НБУ − средний ИПЦ, п.п.; не ниже порога", 0,
     "=IFERROR(INDEX(B7_MONETARY!$D$22:$G$22;MATCH(D$4;B7_MONETARY!$D$10:$G$10;0));\"\")"],
    ["  статус", "", "", "=IF(D27=\"\";\"нет данных\";IF(D27>=$C$27;\"OK\";\"ВНИМАНИЕ\"))"]]
json.dump(out, sys.stdout, ensure_ascii=False)
