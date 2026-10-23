"""Build the cell contents of B2_DEMAND and its COEFS rows (block B2).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Forecast formulas are written once (column BB) and copied right in the sheet.
"""
import json
import sys

from macromodel.blocks.demand import COMPONENTS, coef_table, link_other_to_consumption, real_levels_q, regressors
from macromodel.blocks.real_sector import annual_growth
from macromodel.blocks.shocks import SHOCK_ROW

COEF_FIRST = 23  # B1 uses COEFS rows 5-22
LAST_COL = 53  # BA = 2026Q2, last actual quarter
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}


def C(c, v):
    return f"COEFS!$E${crow[(f'GDPE_{c}', v)]}"


def col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


out = {}
end = COEF_FIRST + len(coefs) - 1
out[f"COEFS!A{COEF_FIRST}:L{end}"] = [
    [f"{r['eq']}_{r['var']}", "B2", r["eq"], r["var"], float(r["coef"]),
     "" if r["se"] is None else r["se"], "" if not r["se"] else round(r["coef"] / r["se"], 1),
     ("2011–2025" if "2011" in r["method"] else "2016–2025") if r["n"] else "", r["method"], "" if r["r2"] is None else r["r2"], "2026-10-21", r["note"]]
    for r in coefs]

x = regressors().loc["2025"]
g = annual_growth(real_levels_q())
top = [
    ["2. Спрос: ВВП по расходам"],
    [""],
    ["Что считает", "Реальные компоненты ВВП по расходам: C домохозяйств, C госуправления, ВНОК, экспорт, импорт, запасы"],
    ["Берёт", "B1_REAL (рост ВВП по производству, порты, оборона), COEFS"],
    ["Пишет в ANCHORS", "GDP_REAL_E; сверка с GDP_REAL_P на листе CHECKS"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Как в B1: годовой рост компонента применяется к тому же кварталу прошлого года. Импорт вычитается."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Как считается"],
    ["GDP_P", "Рост ВВП по производству (B1)", "%", "=B1_REAL!D29", "=B1_REAL!E29", "=B1_REAL!F29", "=B1_REAL!G29", "из B1_REAL"],
    ["PORTS", "Пропускная способность портов", "млн т", "=B1_REAL!D12", "=B1_REAL!E12", "=B1_REAL!F12", "=B1_REAL!G12", "из B1_REAL"],
    ["DEF", "Расходы на оборону", "% ВВП", "=B1_REAL!D15", "=B1_REAL!E15", "=B1_REAL!F15", "=B1_REAL!G15", "из B1_REAL"],
    ["REAL_WAGE", "Рост реальной зарплаты", "%", round(float(x["REAL_WAGE"]), 1)]
    + [f"=B4_LABOUR!{c}31" for c in "EFG"] + ["из B4_LABOUR (с учётом факта)"],
    ["REAL_DEF", "Рост реальных расходов на оборону", "%", round(float(x["REAL_DEF"]), 1)]
    + [f"=({c}13/{p}13)*(1+{c}11/100)*100-100" for c, p in zip("EFG", "DEF")] + ["доля в ВВП × реальный ВВП"],
]
sumif = lambda yr, r: f"SUMIF($H$30:$BK$30;{yr};$H${r}:$BK${r})"
dom = [f"=({sumif(c + '$10-1', 32)}*(1+{c}20/100)+{sumif(c + '$10-1', 33)}*(1+{c}21/100)+{sumif(c + '$10-1', 34)}*(1+{c}22/100))"
       f"/({sumif(c + '$10-1', 32)}+{sumif(c + '$10-1', 33)}+{sumif(c + '$10-1', 34)})*100-100" for c in "EFG"]
top.append(["DOM_DEMAND", "Рост внутреннего спроса (C + G + I)", "%", round(float(x["DOM_DEMAND"]), 1)] + dom + ["взвешенный рост компонентов"])
out["B2_DEMAND!A1:H16"] = top

kv = lambda c, v: f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (f'GDPE_{c}', v)):.2f}".replace(".", ",").replace("-", "−")
eqs = {
    "HH": (f"{kv('HH', 'const')} + {kv('HH', 'REAL_WAGE')} × рост реальной зарплаты + влияние ставки (B7)",
           lambda c, p: f"={C('HH','const')}+{C('HH','REAL_WAGE')}*{c}$14+B7_MONETARY!{c}39"),
    "GOV": ("−1,24 + 0,17 × рост реальных расходов на оборону", lambda c, p: f"={C('GOV','const')}+{C('GOV','REAL_DEF')}*{c}$15"),
    "GFCF": ("1,5 + 2,0 × рост ВВП (акселератор) + влияние ставки (B7)",
             lambda c, p: f"={C('GFCF','const')}+{C('GFCF','GDP_P')}*{c}$11+B7_MONETARY!{c}40"),
    "EXP": ("−3,1 + 0,28 × рост портов + 0,07 × изменение загрузки металлургии",
            lambda c, p: f"={C('EXP','const')}+{C('EXP','PORTS')}*({c}$12/{p}$12-1)*100"
                         f"+COEFS!$E${SHOCK_ROW['MET_X']}*(MAX(B1_REAL!{c}$16;1)/MAX(B1_REAL!{p}$16;1)-1)*100"),
    "IMP": (f"{kv('IMP', 'const')} + {kv('IMP', 'DOM_DEMAND')} × рост внутреннего спроса", lambda c, p: f"={C('IMP','const')}+{C('IMP','DOM_DEMAND')}*{c}$16"),
    "INV": ("растут вместе с ВВП по производству", lambda c, p: f"={C('INV','GDP_P')}*{c}$11"),
}
names = {k: v[1] for k, v in COMPONENTS.items()} | {"INV": "Запасы и статистическое расхождение"}
rows = [["2. Рост реальных компонентов, % г/г"], ["Код", "Компонент", "Уравнение", 2025, 2026, 2027, 2028]]
for c in ["HH", "GOV", "GFCF", "EXP", "IMP", "INV"]:
    txt, f = eqs[c]
    hist = "" if c == "INV" else round(float(g.loc["2025", c]), 1)
    rows.append([f"GDPE_{c}", names[c], txt, hist] + [f(cc, pp) for cc, pp in zip("EFG", "DEF")])
rows.append(["GDP_REAL_E", "ВВП по расходам", "C + G + I + X − M + запасы"]
            + [f"={sumif(c + '$19', 38)}/{sumif(c + '$19-1', 38)}*100-100" for c in "DEFG"])
rows.append(["GAP_P_E", "Разрыв: ВВП по производству / по расходам − 1", "%, порог на листе CHECKS"]
            + [f"=B1_REAL!{c}29-{c}26" for c in "DEFG"])
out["B2_DEMAND!A18:G27"] = rows

lv = real_levels_q()
hdr = [["3. Реальные компоненты по кварталам, млн грн в ценах 2021"],
       ["", "", "", "", "", "", "Год", "=ANCHORS!H2"],
       ["Код", "Компонент", "", "", "", "", "", "=ANCHORS!H4"]]
codes = ["HH", "GOV", "GFCF", "EXP", "IMP", "INV"]
for c in codes:
    hdr.append([f"GDPE_{c}", names[c]])
hdr.append(["GDP_REAL_E", "ВВП по расходам", "", "", "", "", "", "=H32+H33+H34+H35-H36+H37"])
out["B2_DEMAND!A29:H38"] = hdr
quarters = [f"{y}Q{q}" for y in range(2015, 2027) for q in range(1, 5)][:46]
out["B2_DEMAND!H32:BA37"] = [[round(float(lv.loc[q, c]), 1) for q in quarters] for c in codes]
out["B2_DEMAND!BB32"] = [["=AX32*(1+INDEX($E20:$G20;MATCH(BB$30;$E$19:$G$19;0))/100)"]]

con = [["4. Вклад компонентов в рост ВВП, п.п. г/г"], ["Код", "Компонент", "", "", "", "", "", "=H31"]]
for c in codes:
    con.append([f"GDPE_{c}", names[c] + (" (со знаком минус)" if c == "IMP" else "")])
con.append(["GDP_REAL_E", "Рост ВВП по расходам, % г/г"])
out["B2_DEMAND!A40:H48"] = con
out["B2_DEMAND!L42"] = [["=IFERROR((L32-H32)/H$38*100;\"\")"]]
out["B2_DEMAND!L46"] = [["=IFERROR(-(L36-H36)/H$38*100;\"\")"]]
link = link_other_to_consumption()
out["COEFS!A35:L35"] = [["GVA_OTHER_HH", "B1", "GVA_OTHER", "GDPE_HH", round(float(link["coef"]["HH"]), 2),
                         round(float(link["se"]["HH"]), 2), round(float(link["coef"]["HH"] / link["se"]["HH"]), 1),
                         "2016–2025", "оценка МНК 2016–2025, годовые, дамми 2022", round(float(link["r2"]), 2),
                         "2026-10-21", "Торговля и госуправление к спросу не привязаны: оценка дала отрицательный наклон"]]
json.dump(out, sys.stdout, ensure_ascii=False)
