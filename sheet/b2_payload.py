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
    ["Пишет в ANCHORS", "GDP_REAL_E; сверка с GDP_REAL_P на листе CHECKS"],
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

eqs = {
    "HH": (f"{kv('HH', 'const')} + {kv('HH', 'REAL_WAGE')} × рост реальных трудовых доходов + влияние ставки (B7) + эффект мира "
           "(только кварталы после прекращения огня, раздел 5)",
           lambda c, p: f"={C('HH','const')}+{C('HH','REAL_WAGE')}*{c}$14+B7_MONETARY!{c}39+" + peace_y(c).format(r=PHH)),
    "GOV": (f"{pnum('GDPE_GOV', 'O_SH')} × раздел O из B1 (численность военных и штат) + остальное × "
            f"({kv('GOV', 'const')} + {kv('GOV', 'REAL_DEF')} × рост реальных расходов на оборону)",
            lambda c, p: f"={P('GDPE_GOV','O_SH')}*B1_REAL!{c}$74+(1-{P('GDPE_GOV','O_SH')})*"
                         f"({C('GOV','const')}+{C('GOV','REAL_DEF')}*{c}$15)"),
    "GFCF": ("1,5 + 2,0 × рост ВВП (акселератор) + влияние ставки (B7) + 0,03 × изменение загрузки металлургии "
             "(капвложения металлургов и руды) + восстановление (только кварталы после прекращения огня, раздел 5)",
             lambda c, p: f"={C('GFCF','const')}+{C('GFCF','GDP_P')}*{c}$11+B7_MONETARY!{c}40"
                          f"+COEFS!$E${GFCF_MET_ROW}*(B1_REAL!{c}$16-B1_REAL!{p}$16)+" + peace_y(c).format(r=PI)),
    "EXP": (f"агро ({AGRO_SH_TXT}) × реальный агроэкспорт B10 + остальное × (−3,1 + 0,28 (доля, что следует за уровнем портов к 2025) + "
            + f"{estimated()['MET_X'][0]:.2f}".replace(".", ",") + " × изменение загрузки металлургии + руда на экспорт после прекращения огня, B8_CAPACITY раздел 3)",
            lambda c, p: f"={AGRO_SH}*B10_AGRO!{c}41+(1-{AGRO_SH})*({C('EXP','const')}+{port_g(C('EXP','PORTS'), c, p)}"
                         f"+COEFS!$E${SHOCK_ROW['MET_X']}*(B1_REAL!{c}$16-B1_REAL!{p}$16)"
                         f"+COEFS!$E${REC.CR['REC_ORE_XEXP']}*(B8_CAPACITY!{B8Y[c]}{RL.ACT['ORE_XTRA']}-B8_CAPACITY!{B8Y[p]}{RL.ACT['ORE_XTRA']}))"),
    "IMP": (f"оборонный ({pnum('GDPE_IMP', 'DEF_SH')}) × рост реальных расходов на оборону + гражданский × "
            f"({kv('IMP', 'const')} + {kv('IMP', 'DOM_DEMAND')} × рост внутреннего спроса)",
            lambda c, p: f"={P('GDPE_IMP','DEF_SH')}*{c}$15+(1-{P('GDPE_IMP','DEF_SH')})*"
                         f"({C('IMP','const')}+{C('IMP','DOM_DEMAND')}*{c}$16)"),
    "INV": ("растут вместе с ВВП по производству; в кварталах (раздел 3) плюс зерно, которое не вывезли порты (B10_AGRO строка 42)",
            lambda c, p: f"={C('INV','GDP_P')}*{c}$11"),
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
            + [f"=B1_REAL!{c}31-{c}26" for c in "DEFG"])
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
    if code != "INV":
        return f"={p4}{r + 12}*(1+{g}/100)"
    # inventories are a flow: grain the ports cannot ship adds to them this year (B10_AGRO row 42, change of the
    # carry-over stock), last year's addition is taken out so it does not pile up year after year
    stock = lambda y, x: f"N(INDEX(B10_AGRO!$D$42:$G$42;MATCH({y};B10_AGRO!$D$10:$G$10;0)))/100*{x}35"
    return (f"={p4}37*(1+{g}/100)+{AGRO_SH}*({stock(q + '$30', p4)}-{stock(q + '$30-1', p8)})")


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
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
