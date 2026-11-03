"""Build the cell contents of B2_DEMAND and its COEFS rows (block B2).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Forecast formulas are written once (column BB) and copied right in the sheet.
"""
import json
import sys

from macromodel.blocks.demand import COMPONENTS, coef_table, peace_coefs, link_other_to_consumption, real_levels_q, regressors
from macromodel.blocks.real_sector import annual_growth
from macromodel.blocks.shocks import SHOCK_ROW, estimated
from sheet import recovery_layout as RL
from sheet import recovery_payload as REC

B8Y = dict(zip("DEFG", "NOPQ"))  # B2 annual columns -> year columns of B8_CAPACITY section 3

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
     r.get("period", "2016–2025") if r["n"] else "", r["method"], "" if r["r2"] is None else r["r2"], "2026-10-21", r["note"]]
    for r in coefs]

x = regressors().loc["2025"]
g = annual_growth(real_levels_q())
top = [
    ["2. Спрос: ВВП по расходам"],
    [""],
    ["Что считает", "Реальные компоненты ВВП по расходам: C домохозяйств, C госуправления, ВНОК, экспорт, импорт, запасы"],
    ["Берёт", "B1_REAL (рост ВВП по производству, порты, оборона), COEFS"],
    ["Пишет в ANCHORS", "GDP_REAL_E = GDP_REAL_P: с 03.11.2026 импорт — замыкающая статья (раздел 6); B5 переводит его в доллары"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Как в B1: годовой рост компонента применяется к тому же кварталу прошлого года. Импорт вычитается."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Как считается"],
    ["GDP_P", "Рост ВВП по производству (B1)", "%", "=B1_REAL!D31", "=B1_REAL!E31", "=B1_REAL!F31", "=B1_REAL!G31", "из B1_REAL"],
    ["PORTS", "Пропускная способность портов", "млн т", "=B1_REAL!D12", "=B1_REAL!E12", "=B1_REAL!F12", "=B1_REAL!G12", "из B1_REAL"],
    ["DEF", "Расходы на оборону", "% ВВП", "=B1_REAL!D15", "=B1_REAL!E15", "=B1_REAL!F15", "=B1_REAL!G15", "из B1_REAL"],
    ["REAL_WAGE", "Рост реальной зарплаты", "%", round(float(x["REAL_WAGE"]), 1)]
    + [f"=B4_LABOUR!{c}31" for c in "EFG"] + ["из B4_LABOUR (с учётом факта)"],  # B4 payload rewrites this row
    ["REAL_DEF", "Рост реальных расходов на оборону", "%", round(float(x["REAL_DEF"]), 1)]
    + [f"=({c}13/{p}13)*(1+{c}11/100)*100-100" for c, p in zip("EFG", "DEF")] + ["доля в ВВП × реальный ВВП"],
]
sumif = lambda yr, r: f"SUMIF($H$30:$BK$30;{yr};$H${r}:$BK${r})"
dom = [f"=({sumif(c + '$10-1', 32)}*(1+{c}20/100)+{sumif(c + '$10-1', 33)}*(1+{c}21/100)+{sumif(c + '$10-1', 34)}*(1+{c}22/100))"
       f"/({sumif(c + '$10-1', 32)}+{sumif(c + '$10-1', 33)}+{sumif(c + '$10-1', 34)})*100-100" for c in "EFG"]
top.append(["DOM_DEMAND", "Рост внутреннего спроса (C + G + I)", "%", round(float(x["DOM_DEMAND"]), 1)] + dom + ["взвешенный рост компонентов"])
out["B2_DEMAND!A1:H16"] = top

# Peace effect after a ceasefire, annual, per scenario (SCENARIOS rows PEACE_ROW..; active columns L:N)
from macromodel import scenario_layout as SL

PEACE_ROW = SL.PEACE_C  # SCENARIOS annual table: PEACE_C, the next row PEACE_I
assert SL.PEACE_I == PEACE_ROW + 1
ACT_C = dict(zip("EFG", "LMN"))
# the annual SCENARIOS rows are typed in the annual table since 2026-10-29 (labels: scenarios_quarterly_payload)

PEACE_COEF_FIRST = 168  # after B4 MIL_ rows 164-167
pc = peace_coefs()
prow = {(r["eq"], r["var"]): PEACE_COEF_FIRST + i for i, r in enumerate(pc)}
out[f"COEFS!A{PEACE_COEF_FIRST}:L{PEACE_COEF_FIRST + len(pc) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B2", r["eq"], r["var"], r["coef"], "", "", "", r["method"], "", "2026-10-25", r["note"]] for r in pc]
P = lambda eq, v: f"COEFS!$E${prow[(eq, v)]}"
pnum = lambda eq, v: f"{next(r['coef'] for r in pc if (r['eq'], r['var']) == (eq, v)):.2f}".replace(".", ",")

from macromodel.blocks.agro import ROW as AGRO_ROW, coef_rows as agro_coefs
AGRO_SH = f"COEFS!$E${AGRO_ROW['A_AGRO_SH']}"
AGRO_SH_TXT = f"{next(r['coef'] for r in agro_coefs() if r['code'] == 'A_AGRO_SH'):.2f}".replace(".", ",")
kv = lambda c, v: f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (f'GDPE_{c}', v)):.2f}".replace(".", ",").replace("-", "−")
# Section 5: the peace effect by quarter. SCENARIOS rows PEACE_ROW, PEACE_ROW + 1 are the effect in quarters after the ceasefire
# (row 16), not in the whole year: reconstruction and spending cannot start before it. A quarter that is the first
# peaceful one against the same quarter a year ago also gets last year's effect (the level jump reaches it only now).
SEC5 = 50
CF, FLAG, PHH, PI = SEC5 + 2, SEC5 + 3, SEC5 + 4, SEC5 + 5
peace_y = lambda c: f"SUMIF($H$30:$BK$30;{c}$19;$H${{r}}:$BK${{r}})/4"
GFCF_MET_ROW = 232
GFCF_MET = 0.03
# Port-dependent share K of the sector moves with the ports' level against 2025 (D12), the rest does not:
# growth = ((1 - K) + K * ports / ports 2025) / (same a year ago) - 1. Closing and reopening the ports cancel out,
# and a fall cannot take more than the share K (2026-10-28; was K x % change of the ports).
port_g = lambda k, c, p: f"(((1-{k})+{k}*{c}$12/$D$12)/((1-{k})+{k}*{p}$12/$D$12)*100-100)"

# Government consumption (03.11.2026): section O (pay) + defence purchases + education and health. Purchases follow real
# defence spending 1 : 1, so the end of the war takes imported arms out of G and, through the closing item, out of imports.
# (A first version used defence spending without soldiers' pay; B4 MIL_REAL swings by a third in 2027 and blew purchases up.)
G_CIV_ROW, IMP_SH_PEACE_ROW, IMP_SH_WAR_ROW = 252, 254, 255
G_CIV = f"COEFS!$E${G_CIV_ROW}"
CIV_SH = 0.16
CIV_SH_TXT = f"{CIV_SH:.2f}".replace(".", ",")
PROC_TXT = f"{1 - CIV_SH - next(r['coef'] for r in pc if (r['eq'], r['var']) == ('GDPE_GOV', 'O_SH')):.2f}".replace(".", ",")
eqs = {
    "HH": (f"{kv('HH', 'const')} + {kv('HH', 'REAL_WAGE')} × рост реальных трудовых доходов + влияние ставки (B7) + эффект мира "
           "(только кварталы после прекращения огня, раздел 5)",
           lambda c, p: f"={C('HH','const')}+{C('HH','REAL_WAGE')}*{c}$14+B7_MONETARY!{c}39+" + peace_y(c).format(r=PHH)),
    "GOV": (f"{pnum('GDPE_GOV', 'O_SH')} × раздел O из B1 (численность военных и штат) + {PROC_TXT} × оборонные закупки "
            f"(1 : 1 к реальным расходам на оборону, строка 15) + {CIV_SH_TXT} × образование и здравоохранение B1",
            lambda c, p: f"={P('GDPE_GOV','O_SH')}*B1_REAL!{c}$74+(1-{P('GDPE_GOV','O_SH')}-{G_CIV})*{c}$15+{G_CIV}*B1_REAL!{c}$30"),
    "GFCF": ("1,5 + 2,0 × рост ВВП (акселератор) + влияние ставки (B7) + 0,03 × изменение загрузки металлургии "
             "(капвложения металлургов и руды) + восстановление (только кварталы после прекращения огня, раздел 5)",
             lambda c, p: f"={C('GFCF','const')}+{C('GFCF','GDP_P')}*{c}$11+B7_MONETARY!{c}40"
                          f"+COEFS!$E${GFCF_MET_ROW}*(B1_REAL!{c}$16-B1_REAL!{p}$16)+" + peace_y(c).format(r=PI)),
    "EXP": (f"агро ({AGRO_SH_TXT}) × реальный агроэкспорт B10 + остальное × (−3,1 + 0,28 (доля, что следует за уровнем портов к 2025) + "
            + f"{estimated()['MET_X'][0]:.2f}".replace(".", ",") + " × изменение загрузки металлургии + руда на экспорт после прекращения огня, B8_CAPACITY раздел 3)",
            lambda c, p: f"={AGRO_SH}*B10_AGRO!{c}41+(1-{AGRO_SH})*({C('EXP','const')}+{port_g(C('EXP','PORTS'), c, p)}"
                         f"+COEFS!$E${SHOCK_ROW['MET_X']}*(B1_REAL!{c}$16-B1_REAL!{p}$16)"
                         f"+COEFS!$E${REC.CR['REC_ORE_XEXP']}*(B8_CAPACITY!{B8Y[c]}{RL.ACT['ORE_XTRA']}-B8_CAPACITY!{B8Y[p]}{RL.ACT['ORE_XTRA']}))"),
    "IMP": ("замыкающая статья: C + G + I + X + запасы − ВВП по производству, по кварталам (раздел 3); "
            "что спрос берёт сверх своего производства, ввозится (раздел 6, правило В20 в README)",
            lambda c, p: f"={sumif(c + '$19', 36)}/{sumif(c + '$19-1', 36)}*100-100"),
    "INV": ("вклад, п.п. ВВП: та же доля в ВВП по производству, что в том же квартале год назад, плюс зерно, "
            "которое не вывезли порты (B10_AGRO строка 42)",
            lambda c, p: f"=({sumif(c + '$19', 37)}-{sumif(c + '$19-1', 37)})/{sumif(c + '$19-1', 38)}*100"),
}
names = {k: v[1] for k, v in COMPONENTS.items()} | {"INV": "Запасы и статистическое расхождение"}
rows = [["2. Рост реальных компонентов, % г/г"], ["Код", "Компонент", "Уравнение", 2025, 2026, 2027, 2028]]
for c in ["HH", "GOV", "GFCF", "EXP", "IMP", "INV"]:
    txt, f = eqs[c]
    hist = "" if c == "INV" else round(float(g.loc["2025", c]), 1)
    rows.append([f"GDPE_{c}", names[c], txt, hist] + [f(cc, pp) for cc, pp in zip("EFG", "DEF")])
rows.append(["GDP_REAL_E", "ВВП по расходам", "C + G + I + X − M + запасы"]
            + [f"={sumif(c + '$19', 38)}/{sumif(c + '$19-1', 38)}*100-100" for c in "DEFG"])
rows.append(["IMP_SH", "Доля импорта во внутреннем спросе (C + G + I)", "реальные, за год; коридор на листе CHECKS строка 6 "
             "(с 03.11.2026 вместо разрыва: ВВП по расходам = ВВП по производству по построению)"]
            + [f"={sumif(c + '$19', 36)}/({sumif(c + '$19', 32)}+{sumif(c + '$19', 33)}+{sumif(c + '$19', 34)})" for c in "DEFG"])
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
# forecast quarters BB..BK: the same quarter a year ago times the year's growth of the component
FC = [col(i) for i in range(LAST_COL, LAST_COL + 10)]  # col(53) = BB
growth = lambda q, r: f"INDEX($E${r}:$G${r};MATCH({q}$30;$E$19:$G$19;0))"


def qcell(code, r, q):
    p4, p8 = col(_ci(q) - 4), col(_ci(q) - 8)
    g = growth(q, r)
    if code in ("HH", "GFCF"):  # the year's average peace effect out, this quarter's effect in
        pr = PHH if code == "HH" else PI
        g = f"({g}-SUMIF($H$30:$BK$30;{q}$30;$H${pr}:$BK${pr})/4+{q}{pr})"
    if code == "IMP":  # closing item (03.11.2026): what demand takes beyond domestic production is imported
        return f"={q}32+{q}33+{q}34+{q}35+{q}37-ANCHORS!{q}6"
    if code != "INV":
        return f"={p4}{r + 12}*(1+{g}/100)"
    # inventories are a flow: grain the ports cannot ship adds to them this year (B10_AGRO row 42, change of the
    # carry-over stock), last year's addition is taken out so it does not pile up year after year
    stock = lambda y, x: f"N(INDEX(B10_AGRO!$D$42:$G$42;MATCH({y};B10_AGRO!$D$10:$G$10;0)))/100*{x}35"
    return (f"={p4}37*ANCHORS!{q}6/ANCHORS!{p4}6+{AGRO_SH}*({stock(q + '$30', p4)}-{stock(q + '$30-1', p8)})")


def _ci(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n - 1


out["B2_DEMAND!BB32:BK37"] = [[qcell(c, 20 + k, q) for q in FC] for k, c in enumerate(codes)]

con = [["4. Вклад компонентов в рост ВВП, п.п. г/г"], ["Код", "Компонент", "", "", "", "", "", "=H31"]]
for c in codes:
    con.append([f"GDPE_{c}", names[c] + (" (со знаком минус)" if c == "IMP" else "")])
con.append(["GDP_REAL_E", "Рост ВВП по расходам, % г/г"])
out["B2_DEMAND!A40:H48"] = con
cf = "IFERROR(INDEX(SCENARIOS!$L$16:$N$16;MATCH(\"2*\";SCENARIOS!$L$16:$N$16;0));\"нет\")"
eff = lambda q, srow: (f"=IF({q}$30<2026;0;{q}{FLAG}*INDEX(SCENARIOS!$L${srow}:$N${srow};{q}$30-2025)"
                       f"+IF({q}$30>2026;INDEX(SCENARIOS!$L${srow}:$N${srow};{q}$30-2026)*({q}{FLAG}-{col(_ci(q) - 4)}{FLAG});0))")
out[f"B2_DEMAND!A{SEC5}:H{PI}"] = [
    ["5. Эффект мира по кварталам"],
    ["Код", "Показатель", "", "", "", "", "", "=H31"],
    ["CEASEFIRE", "Квартал прекращения огня (SCENARIOS строка 16, активный сценарий)", "=" + cf],
    ["PEACE_Q", "Квартал после прекращения огня", "1 — мир, 0 — война"],
    ["PEACE_HH", "Эффект мира в потреблении", f"п.п. к росту г/г: значение года (SCENARIOS строка {PEACE_ROW}) после прекращения огня; "
     "первый мирный квартал к военному год назад получает и прошлогодний"],
    ["PEACE_I", "Эффект восстановления в ВНОК", f"п.п. к росту г/г: то же по SCENARIOS строка {PEACE_ROW + 1}"],
]
allq = [col(i) for i in range(7, LAST_COL + 10)]  # H..BK
out[f"B2_DEMAND!H{SEC5 + 1}:BK{PI}"] = [
    [f"={q}$31" for q in allq],
    [""] * len(allq),
    [f"=IF($C${CF}=\"нет\";0;IF({q}$31>=$C${CF};1;0))" for q in allq],
    ["" if _ci(q) < LAST_COL else eff(q, PEACE_ROW) for q in allq],
    ["" if _ci(q) < LAST_COL else eff(q, PEACE_ROW + 1) for q in allq],
]
out[f"COEFS!A{GFCF_MET_ROW}:L{GFCF_MET_ROW}"] = [[
    "GDPE_GFCF_MET", "B2", "GDPE_GFCF", "MET", GFCF_MET, "", "", "2024–2025", "оценка", "", "2026-10-28",
    "ВНОК на 1 п.п. изменения загрузки металлургии (B1_REAL строка 16): капвложения металлургов и железорудных "
    "комбинатов ≈ 0,7 млрд USD из ~30 млрд USD ВНОК 2024–2025 (Метинвест, АрселорМиттал Кривой Рог, Ferrexpo). "
    "Остановленные заводы не инвестируют. Оценка Claude"]]
out["B2_DEMAND!L42"] = [["=IFERROR((L32-H32)/H$38*100;\"\")"]]
out["B2_DEMAND!L46"] = [["=IFERROR(-(L36-H36)/H$38*100;\"\")"]]
link = link_other_to_consumption()
out["COEFS!A35:L35"] = [["GVA_OTHER_HH", "B1", "GVA_OTHER", "GDPE_HH", round(float(link["coef"]["HH"]), 2),
                         round(float(link["se"]["HH"]), 2), round(float(link["coef"]["HH"] / link["se"]["HH"]), 1),
                         "2016–2025", "оценка МНК 2016–2025, годовые, дамми 2022", round(float(link["r2"]), 2),
                         "2026-10-21", "Торговля и госуправление к спросу не привязаны: оценка дала отрицательный наклон"]]
# --- Section 6 (03.11.2026): imports are the closing item; the BoP squeeze and the check against NBU facts
SEC6 = 57
B5Q = {col(LAST_COL - 6 + i): col(3 + i) for i in range(16)}  # B2 AV..BK (2025Q1..2028Q4) -> B5_EXTERNAL D..S
sec6 = [["6. Импорт — замыкающая статья: сжатие из-за нехватки валюты и сверка с фактом НБУ"],
        ["Код", "Показатель", "Как считается", "", "", "", "", "=H31"],
        ["IMP_CUT_R", "Сжатие импорта (B5 раздел 7), реальное", "млн грн 2021: сжатие USD / импорт USD × реальный импорт (строка 36)"],
        ["GDPE_HH_POST", "Потребление после сжатия", "строка 32 − сжатие × доля C в C + I: товаров нет — их не потребили"],
        ["GDPE_GFCF_POST", "ВНОК после сжатия", "строка 34 − сжатие × доля I в C + I"],
        ["GDPE_IMP_POST", "Импорт после сжатия", "строка 36 − сжатие; ВВП не меняется: спрос и импорт падают на одно и то же"],
        ["IMP_SH_Q", "Доля импорта во внутреннем спросе", "строка 36 / (C + G + I)"],
        ["IMP_NBU", "Импорт модели против факта НБУ, п.п.", "квартал с фактом НБУ, но без нацсчетов: рост реального импорта − "
         "(рост импорта в USD − рост цен импорта B5 строка 25); проверка на CHECKS строка 46"]]
out[f"B2_DEMAND!A{SEC6}:H{SEC6 + 7}"] = sec6
q4c = lambda q: col(_ci(q) - 4)
cut = lambda q: f"IFERROR(B5_EXTERNAL!{B5Q[q]}92/B5_EXTERNAL!{B5Q[q]}57;0)*{q}36" if q in B5Q else "0"
r6 = SEC6 + 2
out[f"B2_DEMAND!H{SEC6 + 1}:BK{SEC6 + 7}"] = [
    [f"={q}$31" for q in allq],
    ["" if q not in B5Q else "=" + cut(q) for q in allq],
    ["" if q not in B5Q else f"={q}32-{q}{r6}*{q}32/({q}32+{q}34)" for q in allq],
    ["" if q not in B5Q else f"={q}34-{q}{r6}*{q}34/({q}32+{q}34)" for q in allq],
    ["" if q not in B5Q else f"={q}36-{q}{r6}" for q in allq],
    [f"={q}36/({q}32+{q}33+{q}34)" for q in allq],
    ["" if _ci(q) < LAST_COL else
     f"=IF(ISFORMULA(B5_EXTERNAL!{B5Q[q]}57);\"\";({q}36/{q4c(q)}36-1)*100-((B5_EXTERNAL!{B5Q[q]}57/B5_EXTERNAL!{B5Q[q4c(q)]}57)"
     f"/(1+INDEX(B5_EXTERNAL!$E$25:$G$25;{q}$30-2025)/100)-1)*100)" for q in allq],
]
out[f"COEFS!A{G_CIV_ROW}:L{IMP_SH_WAR_ROW}"] = [
    ["GDPE_GOV_CIV", "B2", "GDPE_GOV", "CIV_SH", CIV_SH, "", "", "2025", "оценка", "", "2026-11-03",
     "Доля образования и здравоохранения в потреблении госуправления (бюджеты 2025: ~550 из ~3500 млрд грн). Оценка Claude"],
    [""] * 12,
    ["IMP_SH_PEACE", "B2", "IMP_SH", "PEACE", 0.47, "", "", "2015–2021", "оценка", "", "2026-11-03",
     "Верх коридора доли импорта во внутреннем спросе в мирные годы: максимум 2015–2021 0,43 + запас. Выше — спрос завышен "
     "или производство занижено; объяснить"],
    ["IMP_SH_WAR", "B2", "IMP_SH", "WAR", 0.52, "", "", "2022–2026", "оценка", "", "2026-11-03",
     "Верх коридора в годы войны: 2024–2025 0,45–0,46, 1 пол. 2026 0,54 (сезонно выше года), оборона и энергия. Оценка Claude"],
]
# CHECKS: row 6 was production vs expenditure (now equal by construction); rows 46-50 new
yrs = lambda c: f"B2_DEMAND!$H$30:$BK$30;{c}$4"
sh = lambda c: (f"=IFERROR(SUMIF({yrs(c)};B2_DEMAND!$H$36:$BK$36)/(SUMIF({yrs(c)};B2_DEMAND!$H$32:$BK$32)"
                f"+SUMIF({yrs(c)};B2_DEMAND!$H$33:$BK$33)+SUMIF({yrs(c)};B2_DEMAND!$H$34:$BK$34));\"\")")
peace = lambda c: f"OR({c}$4<2022;SUMIF({yrs(c)};B2_DEMAND!$H$53:$BK$53)=4)"
CY = [col(3 + i) for i in range(14)]  # D..Q = 2015..2028
out["CHECKS!A6:Q7"] = [
    ["Импорт (замыкающая статья) / внутренний спрос", "Реальный импорт / (C + G + I) за год. С 03.11.2026 ВВП по расходам = ВВП по "
     "производству по построению, импорт замыкает баланс (B2 раздел 6). Не выше коридора: мир 0,47, война 0,52 (COEFS 254–255)",
     "0,47 / 0,52"] + [sh(c) for c in CY],
    ["  статус", "", ""] + [f"=IF({c}6=\"\";\"нет данных\";IF({c}6>IF({peace(c)};COEFS!$E${IMP_SH_PEACE_ROW};COEFS!$E${IMP_SH_WAR_ROW});"
                            f"\"ВНИМАНИЕ\";\"OK\"))" for c in CY],
]
dom = lambda c, k: f"(SUMIF({yrs(c)}{k};B2_DEMAND!$H$32:$BK$32)+SUMIF({yrs(c)}{k};B2_DEMAND!$H$33:$BK$33)+SUMIF({yrs(c)}{k};B2_DEMAND!$H$34:$BK$34))"
out["CHECKS!A46:Q50"] = [
    ["Импорт: модель против факта НБУ", "Рост реального импорта B2 − (рост импорта НБУ в USD − рост цен импорта), п.п., по кварталам, "
     "где факт НБУ уже есть, а нацсчетов ещё нет (B2_DEMAND строка 64); по модулю не выше порога", 5]
    + [f"=IFERROR(MAX(ARRAYFORMULA(IF((B2_DEMAND!$BB$30:$BK$30={c}$4)*ISNUMBER(B2_DEMAND!$BB$64:$BK$64);ABS(B2_DEMAND!$BB$64:$BK$64);\"\")));\"\")"
       if c >= "M" else "" for c in CY],
    ["  статус", "", ""] + [f"=IF(OR({c}46=\"\";{c}46=0);\"нет данных\";IF({c}46>$C$46;\"ВНИМАНИЕ\";\"OK\"))" for c in CY],
    [""],
    ["Импорт г/г против внутреннего спроса", "Рост реального импорта − рост C + G + I, п.п.; по модулю не выше порога "
     "(2016–2025: до 9 п.п.). Больше — объяснить: оборона, энергия, восстановление, сжатие", 10]
    + ["" if c == "D" else f"=IFERROR((SUMIF({yrs(c)};B2_DEMAND!$H$36:$BK$36)/SUMIF({yrs(c)}-1;B2_DEMAND!$H$36:$BK$36)-"
       f"{dom(c, '')}/{dom(c, '-1')})*100;\"\")" for c in CY],
    ["  статус", "", ""] + ["" if c == "D" else f"=IF({c}49=\"\";\"нет данных\";IF(ABS({c}49)>$C$49;\"ВНИМАНИЕ\";\"OK\"))" for c in CY],
]
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
