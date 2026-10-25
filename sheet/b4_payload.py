"""Build the cell contents of B4_LABOUR, its COEFS rows, ANCHORS links and the quarterly labour
scenarios in SCENARIOS (block B4, by quarter since 2026-10-25).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
Quarter columns D:S of B4 are 2025Q1..2028Q4. Each quarter is compared with the same quarter a
year before (macromodel.blocks.labour_q), so the seasonal pattern carries into the forecast.
Wages use CPI of past quarters, GDP four quarters back and budget targets, so B1-B4 have no
circular reference. Section 4 sums the quarters into years for B2, B3, B8.
--coefs: COEFS and links only, without the SCENARIOS inputs.
"""
import json
import sys

from macromodel.blocks import labour_q as L
from macromodel.blocks import wages as W
from macromodel.blocks.labour import LF_2025, UNEMP_EST, coef_table

COEF_FIRST = 45  # B1 5-22, B2 23-35, B3 36-44
UNUSED = "Не используется с 2026-10-25: рынок труда по кварталам, COEFS 128–146. "
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}
C = lambda eq, v: f"COEFS!$E${crow[(eq, v)]}"
num = lambda v, d=2: f"{v:.{d}f}".replace(".", ",").replace("-", "−")

out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(coefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B4", r["eq"], r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), "2016–2025" if r["se"] else "", r["method"],
     "" if r["r2"] is None else r["r2"], "2026-10-21",
     (UNUSED if (r["eq"], r["var"]) in {("U", "const"), ("U", "GDP")} else "") + r["note"]] for r in coefs]
wc = W.coef_table()
out[f"COEFS!A{W.COEF_FIRST}:L{W.COEF_FIRST + len(wc) - 1}"] = [
    [f"W_{r['var']}", "B4", "W", r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), f"{W.FIRST}–{W.LAST}" if r["se"] else "", r["method"],
     "" if r["r2"] is None else r["r2"], "2026-10-23", ("" if r["var"] in W.CALIBRATED else UNUSED) + r["note"]] for r in wc]
WC = lambda v: f"COEFS!$E${W.ROW[v]}"
qc = L.coef_rows()
QROW = {(r["eq"], r["var"]): L.COEF_FIRST + i for i, r in enumerate(qc)}
QC = lambda eq, v: f"COEFS!$E${QROW[(eq, v)]}"
qk = lambda eq, v, d=2: num(next(r["coef"] for r in qc if (r["eq"], r["var"]) == (eq, v)), d)
out[f"COEFS!A{L.COEF_FIRST}:L{L.COEF_FIRST + len(qc) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B4", r["eq"], r["var"], round(r["coef"], 3 if r["eq"].startswith("SEAS") else 3),
     "" if r["se"] is None else round(r["se"], 3), "" if r["se"] is None else round(r["coef"] / r["se"], 1),
     r["period"], r["method"], "" if r["r2"] is None else round(r["r2"], 2), "2026-10-25", r["note"]] for r in qc]

# --- quarter columns ---
def col(i: int) -> str:  # 0 -> A
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def idx(c: str) -> int:
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n - 1


QS = [f"{y}Q{q}" for y in (2025, 2026, 2027, 2028) for q in (1, 2, 3, 4)]
COLS = [col(3 + i) for i in range(16)]  # D..S
ANCH = [col(idx("AV") + i) for i in range(16)]  # 2025Q1..2028Q4 in ANCHORS
ANCH4 = [col(idx("AR") + i) for i in range(16)]  # same quarter a year before
FACT = 6  # 2025Q1..2026Q2 are history
YEAR_SC = {"2026": "L", "2027": "M", "2028": "N"}  # SCENARIOS active annual columns
SCQ = dict(zip(COLS[6:], "CDEFGHIJKL"))  # B4 2026Q3.. -> SCENARIOS quarter columns
prev = lambda c, k=1: COLS[COLS.index(c) - k]
year = lambda c: QS[COLS.index(c)][:4]
qn = lambda c: QS[COLS.index(c)][-1]

# SCENARIOS rows: quarterly labour targets, 3 scenarios + active each
SQ_FIRST = 80
PARAMS = ["MINW", "MIL", "CIV", "MIGR", "MOB", "GUEST", "DEC", "MILN", "MILINT"]
SROW = {p: SQ_FIRST + 2 + 4 * i for i, p in enumerate(PARAMS)}  # first (Base) row of each parameter
ACT = {p: SROW[p] + 3 for p in PARAMS}
SQ_LAST = SROW[PARAMS[-1]] + 4  # note row

x = L.data()
mq = L.min_wage_q()
hist_pub = [round(float(x.loc[q, "PUB"]), 1) for q in QS[:FACT]]
hist_cb = [round(float(L.Q.long_quarterly().loc[q, "CB_EXP_WAGES"])) for q in QS[:FACT]]  # budget wage bill, UAH mn
hist_minw = [float(mq[q]) for q in QS[:FACT]]
HIST_MIL = [0, 0, 0, 0, 0, 0]  # % raise in quarter, 2025Q1..2026Q2: base pay unchanged in 2026 (checked 2026-10-25)
HIST_CIV = [0, 0, 0, 0, 22, 0]  # 2026Q1: teachers +30%, social workers ×2.5 base, doctors to 35k (checked 2026-10-25)
U25 = UNEMP_EST["2025"]
DEC = L.dec_drivers()
NOW = L.nowcast()
NOW_C = COLS[QS.index(NOW["q"])] if NOW and NOW["q"] in QS[FACT:] else None
ADJ_C = NOW_C or COLS[FACT - 1]  # quarter whose equation error carries forward
SEAS = lambda k, c: QC(f"SEAS_{k}", f"Q{qn(c)}")

H = ["Код", "Показатель", "Уравнение / единицы"] + QS + ["Комментарий"]
fc = COLS[FACT:]  # forecast-capable columns from 2026Q3
nf = COLS[4:]  # from 2026Q1 (a year of history behind)
r = {}  # row numbers by code, filled as rows are added
rows = []


def add(code, *cells):
    rows.append([code, *cells])
    if code:
        r[code] = len(rows)


def line(code, name, eq, f, comment="", cols=COLS):
    vals = [f(c) if c in cols else "" for c in COLS]
    add(code, name, eq, *vals, comment)


add("4. Рынок труда по кварталам")
add("")
add("Что считает", "Рабочая сила, безработица и занятость с сезонностью; зарплата по факторам; производительность")
add("Берёт", f"ANCHORS (ВВП, ИПЦ, факт зарплат), SCENARIOS (строки {SQ_FIRST}–{SQ_LAST - 1}: минимальная зарплата, повышения военным и "
             "бюджетникам, миграция, мобилизация по кварталам, декабрьская премия; строки 32–33, 71), COEFS (WQ_, UQ_, SEAS_, DEC_)")
add("Пишет", "ANCHORS: EMPL, UNEMP, WAGE_NOM по кварталам; годовые итоги (раздел 4) — в B2 (доходы), B3 (зарплата), B8 (занятость)")
add("Статус", "версия 2 (2026-10-25): кварталы")
add("Как читать", "Каждый квартал сравнивается с тем же кварталом прошлого года (г/г); уровень = тот же квартал прошлого "
                  "года × (1 + рост). Так сезонность (летом больше работы в агро, в декабре премии и «13-я зарплата», "
                  "летом отпускные) переносится в прогноз. Обследования рабочей силы нет после 2021: 2025–2026Q2 — оценки.")
add("")
add("1. Драйверы")
add(*H)
line("GDP_G", "Рост реального ВВП", "% г/г", lambda c: f"=(ANCHORS!{ANCH[COLS.index(c)]}5/ANCHORS!{ANCH4[COLS.index(c)]}5-1)*100", "ANCHORS, строка 5")
line("CPI", "ИПЦ", "% г/г", lambda c: f"=ANCHORS!{ANCH[COLS.index(c)]}10", "ANCHORS, строка 10 (B3, блоки НБУ)")
line("CPI_L", "ИПЦ четырёх прошлых кварталов", "среднее, % г/г",
     lambda c: f"=AVERAGE(ANCHORS!{ANCH4[COLS.index(c)]}10:{col(idx(ANCH[COLS.index(c)]) - 1)}10)", "индексация по прошлой инфляции")
flow = lambda p, annual_row: lambda c: (0 if year(c) == "2025" else f"=SCENARIOS!{YEAR_SC[year(c)]}{annual_row}/4"
                                         if c not in SCQ else f"=SCENARIOS!{SCQ[c]}{ACT[p]}")
line("MIGR", "Чистая миграция украинцев", "тыс. человек за квартал", flow("MIGR", 22),
     "2026Q1–Q2: годовая (строка 22) / 4; дальше SCENARIOS строки 94–97")
line("MOB", "Мобилизация (чистый отток)", "тыс. человек за квартал", flow("MOB", 23), "SCENARIOS строки 98–101")
line("GUEST", "Чистый приток иностранных рабочих", "тыс. человек за квартал", flow("GUEST", 31), "SCENARIOS строки 102–105")
line("MIL_N", "Численность военных", "тыс. человек, среднее за квартал",
     lambda c: f"={QC('MIL', 'N_2025')}" if COLS.index(c) < FACT else f"=SCENARIOS!{SCQ[c]}{ACT['MILN']}",
     f"до 2026Q2 — оценка COEFS MIL_N_2025 (ЗСУ 880–990 тыс. плюс НГУ и ГПСУ); дальше SCENARIOS строки {SROW['MILN']}–{ACT['MILN']}")
line("DEMOB", "Демобилизованные", "сокращение численности военных за квартал",
     lambda c: f"=MAX(0;{prev(c)}{r['MIL_N']}-{c}{r['MIL_N']})", "тыс. человек; возвращаются в рабочую силу (раздел 2)", COLS[1:])
line("SH_MIGR", "Доля мигрантов в рабочей силе", "доля", lambda c: f"=SCENARIOS!{YEAR_SC[year(c)]}32", "SCENARIOS строка 32", nf)
line("SH_GUEST", "Доля иностранных рабочих в рабочей силе", "доля", lambda c: f"=SCENARIOS!{YEAR_SC[year(c)]}33", "SCENARIOS строка 33", nf)
add("")
add("2. Рабочая сила, безработица, занятость")
add(*H)
line("LF_SA", "Рабочая сила без сезонности", "прошлый квартал + доли × миграция и иностранцы − мобилизация + демобилизованные",
     lambda c: LF_2025 if year(c) == "2025" else
     f"={prev(c)}{len(rows) + 1}+{c}{r['SH_MIGR']}*{c}{r['MIGR']}+{c}{r['SH_GUEST']}*{c}{r['GUEST']}-{c}{r['MOB']}"
     f"+{QC('MIL', 'DEMOB_LF')}*{c}{r['DEMOB']}",
     "тыс. человек; 2025 — оценка (официальной нет); демобилизованные × COEFS MIL_DEMOB_LF")
line("SUPPLY", "Изменение рабочей силы", "% г/г", lambda c: f"=({c}{r['LF_SA']}/{prev(c, 4)}{r['LF_SA']}-1)*100", "", nf)
line("SEAS_LF", "Сезонность рабочей силы", "COEFS SEAS_LF", lambda c: f"={SEAS('LF', c)}", "агросектор: летом больше")
line("LF", "Рабочая сила", "без сезонности × сезонность", lambda c: f"={c}{r['LF_SA']}*{c}{r['SEAS_LF']}", "тыс. человек")
line("DU_O", "Изменение безработицы", f"{qk('UQ', 'const')} {qk('UQ', 'GDP')} × рост ВВП + {num(0.5, 1)} × изменение рабочей силы",
     lambda c: f"={QC('UQ', 'const')}+{QC('UQ', 'GDP')}*{c}{r['GDP_G']}+{C('U', 'SUPPLY')}*{c}{r['SUPPLY']}",
     "п.п. г/г; закон Оукена по кварталам, COEFS UQ_", nf)
line("SEAS_U", "Сезонность безработицы", "COEFS SEAS_U, п.п.", lambda c: f"={SEAS('U', c)}", "зимой выше")
line("UNEMP", "Уровень безработицы", "тот же квартал прошлого года + изменение, не ниже 6% + сезонность",
     lambda c: f"={num(U25, 1)}+{c}{r['SEAS_U']}" if year(c) == "2025" else
     f"=MAX({C('U', 'MIN')}+{c}{r['SEAS_U']};{prev(c, 4)}{len(rows) + 1}+{c}{r['DU_O']})",
     "%; 2025 — оценка НБУ 11,5 + сезонность; нижняя граница COEFS!E51")
line("EMPL", "Занятые", "рабочая сила × (1 − безработица)", lambda c: f"={c}{r['LF']}*(1-{c}{r['UNEMP']}/100)", "тыс. человек")
line("EMPL_G", "Рост занятости", "% г/г", lambda c: f"=({c}{r['EMPL']}/{prev(c, 4)}{r['EMPL']}-1)*100", "", nf)
line("PROD", "Рост производительности труда", "ВВП / занятые, % г/г",
     lambda c: f"=((1+{c}{r['GDP_G']}/100)/(1+{c}{r['EMPL_G']}/100)-1)*100", "проверка на листе CHECKS", nf)
add("")
add(f"3. Зарплата по факторам: ориентиры SCENARIOS (строки {SROW['MINW']}–{ACT['CIV']}), коэффициенты COEFS (WQ_)")
add(*H)
line("MINW", "Минимальная зарплата", "грн в месяц, средняя за квартал",
     lambda c: hist_minw[COLS.index(c)] if COLS.index(c) < FACT else f"=SCENARIOS!{SCQ[c]}{ACT['MINW']}",
     "факт по датам повышений; дальше SCENARIOS")
line("MINW_G", "Рост минимальной зарплаты", "% г/г",
     lambda c: round(float(x.loc[QS[COLS.index(c)], "MINW"]), 1) if year(c) == "2025" else
     f"=({c}{r['MINW']}/{prev(c, 4)}{r['MINW']}-1)*100")
for p, name, hist, note in [
        ("MIL", "военных (ставки)", HIST_MIL, "2026: ставки не менялись (сверено 25.10.2026, thepage.ua «Зарплата військових з 1 травня 2026»); рост фонда госбюджета +18% в 1 п/г — от численности и контрактов «18–24», не от ставок"),
        ("CIV", "гражданских бюджетников", HIST_CIV, "2026Q1: учителя +30% с 1 января (МОН), соцработники — коэфф. 2,5 к окладу, врачи первичного звена до 35 тыс. грн; +22% по всем гражданским — оценка Claude по весам (сверено 25.10.2026)")]:
    line(f"{p}_UP", f"Повышение оплаты {name}", "% к прошлому кварталу",
         lambda c, h=hist, p=p: h[COLS.index(c)] if COLS.index(c) < FACT else f"=SCENARIOS!{SCQ[c]}{ACT[p]}",
         note + "; дальше SCENARIOS")
    line(f"{p}_IDX", f"Уровень оплаты {name}", "индекс, 2025Q1 = 100",
         lambda c, p=p: 100 if c == COLS[0] else f"={prev(c)}{len(rows) + 1}*(1+{c}{r[p + '_UP']}/100)")
    line(f"{p}_G", f"Рост оплаты {name}", "% г/г", lambda c, p=p: f"=({c}{r[p + '_IDX']}/{prev(c, 4)}{r[p + '_IDX']}-1)*100", "", nf)
line("MIL_INT", "Боевые выплаты", "доля от уровня войны, 0–1",
     lambda c: 1 if COLS.index(c) < FACT else f"=SCENARIOS!{SCQ[c]}{ACT['MILINT']}",
     f"1 — как во время боёв; после прекращения огня падает; SCENARIOS строки {SROW['MILINT']}–{ACT['MILINT']}")
line("MIL_PAY", "Выплата на одного военного", "ставки × (1 − доля боевых × (1 − боевые выплаты))",
     lambda c: f"={c}{r['MIL_IDX']}*(1-{QC('MIL', 'COMBAT_SH')}*(1-{c}{r['MIL_INT']}))",
     "индекс, 2025Q1 = 100; доля боевых COEFS MIL_COMBAT_SH")
line("MIL_FUND", "Фонд довольствия военных", "тот же квартал год назад × численность × выплата",
     lambda c: f"={WC('MIL_CB')}*{hist_cb[COLS.index(c)]}" if COLS.index(c) < FACT else
     f"={prev(c, 4)}{len(rows) + 1}*({c}{r['MIL_N']}/{prev(c, 4)}{r['MIL_N']})*({c}{r['MIL_PAY']}/{prev(c, 4)}{r['MIL_PAY']})",
     "млн грн за квартал; до 2026Q2 — доля военных COEFS W_MIL_CB × фонд оплаты труда сводного бюджета (Казначейство)")
line("MIL_FUND_G", "Рост фонда довольствия военных", "% г/г",
     lambda c: f"=({c}{r['MIL_FUND']}/{prev(c, 4)}{r['MIL_FUND']}-1)*100", "", nf)
line("PUB_G", "Рост оплаты в госсекторе для уравнения зарплат", f"{num(0.7, 1)} × ставки военных + {num(0.3, 1)} × гражданские",
     lambda c: hist_pub[COLS.index(c)] if COLS.index(c) < FACT else
     f"={WC('MIL_CB')}*{c}{r['MIL_G']}+(1-{WC('MIL_CB')})*{c}{r['CIV_G']}",
     "% г/г; до 2026Q2 — факт Казначейства; доля военных COEFS W_MIL_CB. Ставки, а не фонд: сокращение армии и боевых "
     "уже идёт в доходы (раздел 4, MIL_REAL) и в рабочую силу (DEMOB), иначе учли бы дважды")
line("DU_W", "Изменение безработицы для зарплат", "закон Оукена на ВВП год назад + изменение рабочей силы",
     lambda c: f"={QC('UQ', 'const')}+{QC('UQ', 'GDP')}*{prev(c, 4)}{r['GDP_G']}+{C('U', 'SUPPLY')}*{c}{r['SUPPLY']}",
     "п.п.; без ВВП текущего квартала: нет циклической ссылки", nf)
line("DESH", "Детенизация", "SCENARIOS строка 71, п.п. к росту г/г", lambda c: f"=SCENARIOS!{YEAR_SC[year(c)]}71", "не новый доход", nf)
line("NW_F", "Рост номинальной зарплаты по факторам",
     f"{qk('WQ', 'const')} + {qk('WQ', 'CPI_L')} × ИПЦ прошлых кварталов + {qk('WQ', 'MINW')} × минимальная + "
     f"{qk('WQ', 'PUB')} × фонд госбюджета {qk('WQ', 'DU')} × изменение безработицы + детенизация",
     lambda c: f"={QC('WQ', 'const')}+{QC('WQ', 'CPI_L')}*{c}{r['CPI_L']}+{QC('WQ', 'MINW')}*{c}{r['MINW_G']}"
               f"+{QC('WQ', 'PUB')}*{c}{r['PUB_G']}+{QC('WQ', 'DU')}*{c}{r['DU_W']}+{c}{r['DESH']}",
     "% г/г; 2026Q1–Q2 — проверка модели на факте", nf)
line("ADJ", "Поправка на ошибку уравнения", "факт г/г − по факторам; дальше × затухание",
     lambda c: f"={c}{len(rows) + 4}-{c}{r['NW_F']}" if c == ADJ_C else f"={prev(c)}{len(rows) + 1}*{QC('WQ', 'RHO')}",
     f"п.п.; ошибка в {QS[COLS.index(ADJ_C)]} переносится вперёд и затухает (COEFS WQ_RHO)", COLS[COLS.index(ADJ_C):])
line("DEC_P", "Декабрьская премия", "декабрь к тренду ноябрь–январь, %",
     lambda c: round(DEC["last"], 1) if c == "G" else f"=SCENARIOS!{SCQ[c]}{ACT['DEC']}",
     f"премии, «13-я зарплата», помощь; {DEC['last_year']} — факт; дальше SCENARIOS. История: COEFS DEC_",
     [c for c in COLS[3:] if qn(c) == "4"])
dec_adj = lambda c: f"*(1+{c}{r['DEC_P']}/300)/(1+{prev(c, 4)}{r['DEC_P']}/300)" if qn(c) == "4" else ""
line("WAGE", "Средняя номинальная зарплата", "факт; дальше тот же квартал прошлого года × (1 + рост); 4 кв. × смена премии / 3",
     lambda c: f"=ANCHORS!{ANCH[COLS.index(c)]}20" if COLS.index(c) < FACT else round(NOW["value"], 1) if c == NOW_C else
     f"={prev(c, 4)}{len(rows) + 1}*(1+({c}{r['NW_F']}+{c}{r['ADJ']})/100){dec_adj(c)}",
     "грн в месяц; идёт в ANCHORS, строка 20. Декабрь — треть 4 кв., поэтому премия двигает квартал на треть"
     + (f". {NOW['q']}: факт {', '.join(NOW['fact_months'])}; "
        + ", ".join(f"{m} = прошлый месяц × (1 + {num(v, 2)}%), медиана этого месяца" for m, v in NOW["filled"].items())
        if NOW_C else ""))
line("WAGE_G", "Рост номинальной зарплаты", "% г/г",
     lambda c: f"=({c}{r['WAGE']}/ANCHORS!{ANCH4[COLS.index(c)]}20-1)*100" if year(c) == "2025" else
     f"=({c}{r['WAGE']}/{prev(c, 4)}{r['WAGE']}-1)*100", "с учётом факта")
line("SEAS_W", "Сезонность зарплаты", "квартал / среднее за год",
     lambda c: f"={c}{r['WAGE']}/AVERAGE({COLS[COLS.index(c) // 4 * 4]}{r['WAGE']}:{COLS[COLS.index(c) // 4 * 4 + 3]}{r['WAGE']})",
     "1 кв. ниже, 4 кв. выше (декабрь); средняя 2011–2025 — COEFS SEAS_WAGE")
line("RW", "Рост реальной зарплаты", "% г/г", lambda c: f"=((1+{c}{r['WAGE_G']}/100)/(1+{c}{r['CPI']}/100)-1)*100")
add("")
add("4. Годовые итоги: в B2 (доходы), B3 (зарплата), B8 (занятость)")
add("Код", "Показатель", "Как считается", 2025, 2026, 2027, 2028, "Комментарий")
Y = ["D", "E", "F", "G"]
yq = lambda i, code: f"{COLS[4 * i]}{r[code]}:{COLS[4 * i + 3]}{r[code]}"
yline = lambda code, name, eq, f, comment="", first=0: add(code, name, eq, *[f(i) if i >= first else "" for i in range(4)], comment)
yline("Y_GDP", "Рост реального ВВП", "B1_REAL", lambda i: f"=B1_REAL!{Y[i]}29")
yline("Y_CPI", "ИПЦ, средний за год", "B3_PRICES", lambda i: f"=B3_PRICES!{Y[i]}20")
yline("Y_LF", "Рабочая сила", "среднее кварталов", lambda i: f"=AVERAGE({yq(i, 'LF')})", "тыс. человек")
yline("Y_UNEMP", "Уровень безработицы", "среднее кварталов", lambda i: f"=AVERAGE({yq(i, 'UNEMP')})", "%")
yline("Y_EMPL", "Занятые", "среднее кварталов", lambda i: f"=AVERAGE({yq(i, 'EMPL')})", "тыс. человек")
yline("Y_EMPL_G", "Рост занятости", "%", lambda i: f"=({Y[i]}{r['Y_EMPL']}/{Y[i - 1]}{r['Y_EMPL']}-1)*100", "идёт в B8", 1)
yline("Y_PROD", "Рост производительности труда", "ВВП / занятые",
      lambda i: f"=((1+{Y[i]}{r['Y_GDP']}/100)/(1+{Y[i]}{r['Y_EMPL_G']}/100)-1)*100", "", 1)
yline("Y_WAGE", "Средняя номинальная зарплата", "среднее кварталов", lambda i: f"=AVERAGE({yq(i, 'WAGE')})", "грн в месяц")
yline("Y_WAGE_G", "Рост номинальной зарплаты", "с учётом факта",
      lambda i: f"=({Y[i]}{r['Y_WAGE']}/AVERAGE(ANCHORS!AR20:AU20)-1)*100" if i == 0 else
      f"=({Y[i]}{r['Y_WAGE']}/{Y[i - 1]}{r['Y_WAGE']}-1)*100", "по отчётности (с детенизацией)")
yline("Y_RW", "Рост реальной зарплаты", "номинальная / ИПЦ",
      lambda i: f"=((1+{Y[i]}{r['Y_WAGE_G']}/100)/(1+{Y[i]}{r['Y_CPI']}/100)-1)*100", "по отчётности")
yline("Y_DESH", "Детенизация", "SCENARIOS строка 71", lambda i: f"=SCENARIOS!{'LMN'[i - 1]}71", "п.п.", 1)
yline("WAGE_ECON", "Рост зарплаты без детенизации", "рост − детенизация",
      lambda i: f"={Y[i]}{r['Y_WAGE_G']}-{Y[i]}{r['Y_DESH']}" if i else f"={Y[i]}{r['Y_WAGE_G']}", "идёт в B3")
yline("RW_ECON", "Рост реальной зарплаты без детенизации", "/ ИПЦ",
      lambda i: f"=((1+{Y[i]}{r['WAGE_ECON']}/100)/(1+{Y[i]}{r['Y_CPI']}/100)-1)*100")
yline("MIL_REAL", "Рост реального фонда довольствия военных", "фонд за год / прошлый год / ИПЦ",
      lambda i: f"=(SUM({yq(i, 'MIL_FUND')})/SUM({yq(i - 1, 'MIL_FUND')})/(1+{Y[i]}{r['Y_CPI']}/100)-1)*100",
      "численность × выплата: демобилизация и конец боевых снижают", 1)
yline("MIL_C", "Доходы военных для потребления", "(1 − сбережения) × (половина этого года + половина прошлого)",
      lambda i: f"=(1-{QC('MIL', 'SAVE')})*" + (f"{Y[i]}{r['MIL_REAL']}" if i == 1 else
                f"(0,5*{Y[i]}{r['MIL_REAL']}+0,5*{Y[i - 1]}{r['MIL_REAL']})"),
      "семьи сглаживают падение: сбережения военных (депозиты) и выплаты при демобилизации; COEFS MIL_SAVE", 1)
yline("CIV_BILL", "Рост реального гражданского фонда зарплат", "(1 + реальная зарплата) × (1 + рост рабочей силы) − 1",
      lambda i: f"=((1+{Y[i]}{r['RW_ECON']}/100)*{Y[i]}{r['Y_LF']}/{Y[i - 1]}{r['Y_LF']}-1)*100",
      "без детенизации; рабочая сила, а не занятость: занятость зависит от ВВП того же года (была бы циклическая ссылка через B2)", 1)
yline("INCOME", "Рост реальных трудовых доходов домохозяйств",
      f"(1 − {num(0.3, 1)}) × гражданский фонд + {num(0.3, 1)} × доходы военных для потребления",
      lambda i: f"=(1-{WC('MIL_HH')})*{Y[i]}{r['CIV_BILL']}+{WC('MIL_HH')}*{Y[i]}{r['MIL_C']}", "идёт в B2 (потребление)", 1)
add("")
add("5. Проверка логики: зарплата к прошлому кварталу против истории")
add(*H)
QQ_C = COLS[COLS.index(ADJ_C) if NOW_C else FACT:]  # forecast quarters, the nowcast included
line("QQ", "Зарплата к прошлому кварталу", "%", lambda c: f"=({c}{r['WAGE']}/{prev(c)}{r['WAGE']}-1)*100",
     "4 кв. — премии, 1 кв. — откат, 2 кв. — отпускные и квартальные премии", COLS[1:])
for k, name in [("LO", "Нижняя граница коридора"), ("HI", "Верхняя граница коридора")]:
    line(f"QQ_{k}", name, f"COEFS QQW_{k}: {'10' if k == 'LO' else '90'}-й процентиль 2011–2025",
         lambda c, k=k: f"={QC('QQW', f'{k}_Q{qn(c)}')}", "без 2022Q1–2023Q1")
line("QQ_CHK", "Статус", "в коридоре — OK",
     lambda c: f'=IF(AND({c}{r["QQ"]}>={c}{r["QQ_LO"]};{c}{r["QQ"]}<={c}{r["QQ_HI"]});"OK";"ВНИМАНИЕ")',
     "ВНИМАНИЕ — нужна причина: строка «Главная причина» и разложение ниже", QQ_C)
dq = COLS[COLS.index(QQ_C[0]) + 1:] if NOW_C else QQ_C  # quarters the equation computes
dec_yy = lambda c: f"((1+{c}{r['DEC_P']}/300)/(1+{prev(c, 4)}{r['DEC_P']}/300)-1)*100" if qn(c) == "4" else "0"
D = [("D_BASE", "база: тот же квартал прошлого года", "к прошлому кварталу год назад − медиана",
      lambda c: f"={prev(c, 4)}{r['QQ']}-{QC('QQW', f'MED_Q{qn(c)}')}"),
     ("D_CPI", "ИПЦ прошлых кварталов", "коэфф. × изменение за квартал",
      lambda c: f"={QC('WQ', 'CPI_L')}*({c}{r['CPI_L']}-{prev(c)}{r['CPI_L']})"),
     ("D_MINW", "минимальная зарплата", "коэфф. × изменение за квартал",
      lambda c: f"={QC('WQ', 'MINW')}*({c}{r['MINW_G']}-{prev(c)}{r['MINW_G']})"),
     ("D_PUB", "фонд госбюджета (военные, бюджетники)", "коэфф. × изменение за квартал",
      lambda c: f"={QC('WQ', 'PUB')}*({c}{r['PUB_G']}-{prev(c)}{r['PUB_G']})"),
     ("D_DU", "безработица", "коэфф. × изменение за квартал",
      lambda c: f"={QC('WQ', 'DU')}*({c}{r['DU_W']}-{prev(c)}{r['DU_W']})"),
     ("D_DESH", "детенизация", "изменение за квартал", lambda c: f"={c}{r['DESH']}-{prev(c)}{r['DESH']}"),
     ("D_ADJ", "поправка на ошибку уравнения", "изменение за квартал", lambda c: f"={c}{r['ADJ']}-{prev(c)}{r['ADJ']}"),
     ("D_DEC", "декабрьская премия", "изменение вклада в рост г/г", lambda c: f"={dec_yy(c)}-{dec_yy(prev(c))}")]
add("", "Разложение: к прошлому кварталу ≈ медиана квартала + сумма строк ниже, п.п.")
d0 = len(rows) + 1
for code, name, eq, f in D:
    line(code, name, eq, f, "", dq)
d1 = len(rows)
line("WHY", "Главная причина", "самая большая строка разложения по модулю",
     lambda c: (f'=IF({c}{r["QQ_CHK"]}="OK";"";"помесячный факт")' if c == NOW_C else
                f'=IF({c}{r["QQ_CHK"]}="OK";"";INDEX($B${d0}:$B${d1};MATCH(MAX(ARRAYFORMULA(ABS({c}{d0}:{c}{d1})));'
                f'ARRAYFORMULA(ABS({c}{d0}:{c}{d1}));0)))'),
     "Если причина — допущение сценария, это сознательный выбор; если база или поправка — артефакт расчёта", QQ_C)
ROWS = r
out[f"B4_LABOUR!A1:T{len(rows)}"] = rows
YC = {"2026": "O", "2027": "P", "2028": "Q"}  # CHECKS year columns
out["CHECKS!A33:Q35"] = [
    ["Логика динамики"],
    ["Зарплата: квартал к прошлому кварталу в коридоре истории", "Число кварталов вне коридора 10–90% (2011–2025), B4_LABOUR раздел 5; не выше порога", 0]
    + [""] * 11 + [f'=COUNTIF(B4_LABOUR!{yc[0]}{r["QQ_CHK"]}:{yc[-1]}{r["QQ_CHK"]};"ВНИМАНИЕ")' if yc else ""
                   for yc in ([c for c in QQ_C if year(c) == y] for y in ["2026", "2027", "2028"])],
    ["  статус", "", ""] + [""] * 11 + [f'=IF({YC[y]}34="";"нет данных";IF({YC[y]}34<=$C$34;"OK";"ВНИМАНИЕ"))' for y in ["2026", "2027", "2028"]],
]

# links: annual results to other blocks, quarters to ANCHORS
out["B2_DEMAND!E14:H14"] = [[f"=B4_LABOUR!{c}{r['INCOME']}" for c in "EFG"] + ["из B4_LABOUR: зарплата без детенизации и довольствие военных"]]
out["B3_PRICES!E12:H12"] = [[f"=B4_LABOUR!{c}{r['WAGE_ECON']}" for c in "EFG"] + ["из B4_LABOUR: с учётом факта, без детенизации"]]
out["B8_CAPACITY!E12:G12"] = [[f"=B4_LABOUR!{c}{r['Y_EMPL_G']}" for c in "EFG"]]
out["ANCHORS!AV18:BK19"] = [[f"=B4_LABOUR!{c}{r['EMPL']}" for c in COLS], [f"=B4_LABOUR!{c}{r['UNEMP']}" for c in COLS]]
out["ANCHORS!BB20:BK20"] = [[f"=B4_LABOUR!{c}{r['WAGE']}" for c in fc]]

# SCENARIOS: quarterly targets by scenario (written on a fresh frame only)
QL = [f"={c}38" for c in "CDEFGHIJKL"]
qyear = dict(zip("CDEFGHIJKL", ["2026"] * 2 + ["2027"] * 4 + ["2028"] * 4))
ANN = {"Base": dict(zip(["2026", "2027", "2028"], "CDE")), "Pess": dict(zip(["2026", "2027", "2028"], "FGH")),
       "Opt": dict(zip(["2026", "2027", "2028"], "IJK"))}
choose = lambda p: [f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{c}{SROW[p]};{c}{SROW[p] + 1};{c}{SROW[p] + 2})" for c in "CDEFGHIJKL"]
minw = [8647, 8647] + [9546] * 4 + [10377] * 4
q4 = lambda a, b, c: ["", a, "", "", "", b, "", "", "", c]  # 2026Q4, 2027Q4, 2028Q4
spec = {
    "MINW": ("Минимальная зарплата", "грн в месяц, средняя за квартал", [minw, minw, minw],
             "Закон о госбюджете 2026 (8647 с 1 января); 2027–2028 — Бюджетная декларация 2027–2029, с 1 января. "
             "Повышение с середины квартала — средняя за квартал"),
    "MIL": ("Повышение довольствия военных", "% к прошлому кварталу",
            [[0, 0, 5, 0, 0, 0, 5, 0, 0, 0], [0, 0, 15, 0, 0, 0, 10, 0, 0, 0], [0] * 10],
            "Оценка Claude (годовые 2027–2028: база 5/5, пессим. 15/10, оптим. 0/0); в 2026 ставки без изменений. Рост фонда от численности не моделируется — строки 98–101 только для рабочей силы"),
    "CIV": ("Повышение оплаты гражданских бюджетников", "% к прошлому кварталу",
            [[3, 5, 5, 0, 0, 0, 8, 0, 0, 0], [3, 5, 0, 0, 0, 0, 5, 0, 0, 0], [3, 5, 6, 0, 0, 0, 10, 0, 0, 0]],
            "2026: учителя +20% с 1 сентября (МОН, сверено 25.10.2026; +3 в 3 кв. и +5 в 4 кв. при доле учителей около 40% фонда гражданских — оценка Claude); дальше индексация с 1 января, оценка Claude"),
    "MIGR": ("Чистая миграция украинцев", "тыс. человек за квартал", None, "По умолчанию годовая (строка 22) / 4; можно задать числом"),
    "MOB": ("Мобилизация (чистый отток)", "тыс. человек за квартал", None, "По умолчанию годовая (строка 23) / 4; можно задать числом"),
    "GUEST": ("Чистый приток иностранных рабочих", "тыс. человек за квартал", None, "По умолчанию годовая (строка 31) / 4"),
    "DEC": ("Декабрьская премия", "% к тренду ноябрь–январь, только 4 кв.",
            [q4(12.4, 12.4, 12.4), q4(12.0, 11.0, 11.0), q4(12.4, 14.0, 15.5)],
            f"История (COEFS DEC_): {num(DEC['pre'], 1)} в 2006–2015, {num(DEC['mid'], 1)} в 2016–2021, "
            f"{num(DEC['war'], 1)} в 2024–2025. База — уровень войны; пессим. — меньше прибыли; "
            f"оптим. — возврат к довоенным 16 по мере восстановления. Оценка Claude"),
    "MILN": ("Численность военных", "тыс. человек, среднее за квартал",
             [[1000, 1000, 950, 900, 850, 800, 800, 800, 800, 800],
              [1000, 1025, 1050, 1075, 1100, 1100, 1075, 1050, 1025, 1000],
              [1000, 975, 900, 850, 800, 800, 800, 800, 800, 800]],
             "Оценка Claude: сейчас около 1 млн (ЗСУ 880–990 тыс., Military Balance; плюс НГУ и ГПСУ); мирный уровень около "
             "800 тыс. (потолок ЗСУ в обсуждаемом мирном плане). Сокращение — демобилизация, люди возвращаются в рабочую силу. "
             "Прекращение огня — строка 16"),
    "MILINT": ("Боевые выплаты", "доля от уровня войны, 0–1",
               [[1, 1, 0.5, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4],
                [1, 1, 1, 1, 1, 1, 0.6, 0.5, 0.4, 0.4],
                [1, 0.6, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]],
               "Оценка Claude: 1 — выплаты как во время боёв; после прекращения огня часть надбавок остаётся (охрана линии, ротации)"),
}
annual_row = {"MIGR": 22, "MOB": 23, "GUEST": 31}
srows = [["Рынок труда по кварталам: бюджетные ориентиры и потоки людей (B4_LABOUR)"],
         ["Параметр", "Единицы"] + QL + ["", "", "Источник"]]
for p in PARAMS:
    name, unit, vals, src = spec[p]
    for k, (sc, label) in enumerate([("Base", "База"), ("Pess", "Пессимистичный"), ("Opt", "Оптимистичный")]):
        v = vals[k] if vals else [f"={ANN[sc][qyear[c]]}{annual_row[p]}/4" for c in "CDEFGHIJKL"]
        srows.append([f"{name} — {label}", unit] + v + ["", "", src if k == 0 else ""])
    srows.append([f"{name} — активный", unit] + choose(p))
srows.append(["Как считается: B4_LABOUR сравнивает квартал с тем же кварталом прошлого года. Повышение — % к уровню прошлого "
              "квартала в среднем за квартал (повышение с 1 сентября даёт треть в 3 кв., остальное в 4 кв.). "
              "Декабрьская премия меняет 4 кв. на треть своего изменения. Фонд военных = численность × выплата; сокращение "
              "численности — демобилизация, которая возвращает людей в рабочую силу. Годовые строки 68–70 не используются с 2026-10-25."])
out[f"SCENARIOS!A{SQ_FIRST}:O{SQ_FIRST + len(srows) - 1}"] = srows
if "--coefs" in sys.argv:
    out = {k: v for k, v in out.items() if not k.startswith("SCENARIOS")}
json.dump(out, sys.stdout, ensure_ascii=False)
