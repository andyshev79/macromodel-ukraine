"""Build the cell contents of B5_EXTERNAL, its COEFS rows and ANCHORS forecast links (block B5).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
The exchange rate rule uses last year's reserves, so B2-B5 have no circular reference.
"""
import json
import sys

from macromodel.blocks import external as X
from macromodel.blocks.external import annual, coef_table
from macromodel.blocks.real_sector import quarterly

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
# --- quarter grid (sections 4-6): B5 columns D:S = 2025Q1..2028Q4 = ANCHORS AV:BK
col = lambda i: chr(ord("A") + i) if i < 26 else chr(ord("A") + i // 26 - 1) + chr(ord("A") + i % 26)
QS = [f"{y}Q{q}" for y in (2025, 2026, 2027, 2028) for q in (1, 2, 3, 4)]
QC = [col(3 + i) for i in range(16)]  # D..S
AC = {q: col(47 + i) for i, q in enumerate(QS)}  # ANCHORS AV..BK
YC = {"2025": "D", "2026": "E", "2027": "F", "2028": "G"}  # annual columns of this sheet and of B6
PY = {"2026": "D", "2027": "E", "2028": "F"}
Q0 = {"2025": 0, "2026": 4, "2027": 8, "2028": 12}
LAYOUT = [("T4", 43), ("H4", 44), ("FXQ_RULE", 45), ("FXQ_AVG", 46), ("FXQ_EOP", 47), ("EURUSD", 48), ("EURUSD_G", 49), ("EURUAH", 50),
          ("T5", 52), ("H5", 53), ("SEAS_EXP", 54), ("SEAS_IMP", 55), ("EXPQ", 56), ("IMPQ", 57), ("TBQ", 58), ("EXPQ_UAH", 59),
          ("IMPQ_UAH", 60), ("TB_FX", 61), ("REMQ_G", 62), ("REMQ", 63), ("REMQ_OFF", 64), ("REMQ_INF", 65), ("FDIQ", 66),
          ("OTHERQ", 67), ("FINQ", 68), ("NEEDQ", 69), ("GAPQ", 70), ("RES_REVAL", 71), ("RESQ", 72), ("RESQ_M", 73),
          ("RES_CHK", 74), ("REM_CHK", 75), ("T6", 77), ("H6", 78), ("DEBT_START", 79), ("DEBT_REVAL_USD", 80),
          ("DEBT_REVAL_UAH", 81), ("DEBT_REVAL_GDP", 82), ("NOTE6", 83)]
QROW = dict(LAYOUT)
q4 = lambda c, code, last=False: (f"{QC[Q0[YR[c]] + 3]}{QROW[code]}" if last else f"{QC[Q0[YR[c]]]}{QROW[code]}:{QC[Q0[YR[c]] + 3]}{QROW[code]}")
YR = {v: k for k, v in YC.items()}
hq = quarterly()
dq = X.dollar_q()
rem_y = dq["REM_TOT"].groupby(dq.index.str[:4]).sum(min_count=4)
other_2025 = float(a["RES"] - annual().loc["2024", "RES"] - (a["TRADE_BAL"] + rem_y["2025"] + a["FDI_L_USD"] + a["FIN_RECEIVED_USD"]))
pairs = list(zip("EFG", "DEF"))
EFG = lambda f: [f(c, p) for c, p in pairs]
rows = [
    ["5. Внешний сектор"],
    [""],
    ["Что считает", "Экспорт и импорт в USD, платёжный баланс, потребность во внешнем финансировании, резервы, курс"],
    ["Берёт", "B2_DEMAND (реальный экспорт и импорт), B3_PRICES (газ, инфляция), SCENARIOS (пшеница, сталь, финансирование), COEFS"],
    ["Пишет в ANCHORS", "EXP_USD, IMP_USD, RES_USD, FIN_NEED_USD, FIN_RECEIVED_USD; курс 2027–2028 отдаёт в B3"],
    ["Статус", "версия 2 (2026-10-26): кварталы — курс USD и EUR, торговля, переводы, резервы, переоценки"],
    ["Как читать", "Разделы 1–3 — годовые итоги, млн USD (их берут B2, B3, B6, B7). Разделы 4–6 — те же расчёты по кварталам 2025Q1–2028Q4: "
     "курс, торговля и переводы, резервы, курсовые переоценки. Разрыв > 0 покрывается резервами; ниже 3 месяцев импорта — ВНИМАНИЕ."],
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
    ["REMIT", "Частные переводы (оплата труда + трансферты)", "сумма кварталов (раздел 5)", round(float(rem_y["2025"]))]
    + [f"=SUM({q4(c, 'REMQ')})" for c in "EFG"] + ["лист Dollar (НБУ); до 2026-10-26 здесь были только трансферты"],
    ["FDI", "Прямые инвестиции (чистые обязательства)", "на уровне 2025", round(float(a["FDI_L_USD"]))] + EFG(lambda c, p: f"={p}29"),
    ["OTHER", "Прочие потоки", "сумма кварталов: средний остаток 2022–2025 / 4", round(other_2025)]
    + [f"=SUM({q4(c, 'OTHERQ')})" for c in "EFG"] + ["доходы, погашения долга, частный отток; 2026 3 кв.: транш — остаток по факту резервов"],
    ["FIN_NEED", "Потребность во внешнем финансировании", "−(сальдо + переводы + ПИИ + прочие)"] + [f"=-({c}27+{c}28+{c}29+{c}30)" for c in "DEFG"],
    ["FIN_RECEIVED", "Получено внешнего финансирования", "из драйверов"] + [f"={c}17" for c in "DEFG"],
    ["FIN_GAP", "Разрыв (потребность − получено)", "> 0: покрывается резервами"] + [f"={c}31-{c}32" for c in "DEFG"],
    ["RES", "Международные резервы, конец года", "4 кв. раздела 5: прошлый квартал − разрыв + переоценка евро", round(float(a["RES"]))]
    + [f"={q4(c, 'RESQ', last=True)}" for c in "EFG"],
    ["RES_M", "Резервы, месяцев импорта", "резервы / импорт × 12"] + [f"={c}34/{c}26*12" for c in "DEFG"] + ["проверка на листе CHECKS"],
    ["RES_SHORT", "Не хватает до 3 месяцев импорта", "дополнительное финансирование"] + [f"=MAX(0;3*{c}26/12-{c}34)" for c in "DEFG"],
    [""],
    ["3. Курс"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["FX_DEP", "Девальвация гривны (средний курс)", "ИПЦ прошлого года − инфляция еврозоны + 3 п.п. × нехватка резервов ниже 5 месяцев",
     "=B3_PRICES!D11", "=B3_PRICES!E11"]
    + [f"={c}41/{p}41*100-100" for c, p in pairs[1:]] + ["из квартального курса (раздел 4): ИПЦ прошлого года − инфляция еврозоны + давление резервов"],
    ["FX_AVG", "Курс UAH/USD, средний", "грн за 1 USD"] + [f"=AVERAGE(ANCHORS!{r})" for r in ["AV12:AY12", "AZ12:BC12", "BD12:BG12", "BH12:BK12"]],
]
out[f"B5_EXTERNAL!A1:H{len(rows)}"] = rows

# --- sections 4-6: quarters
qc = X.Q_CALIBRATED
fit, vol, seas = X.remit_fit(), X.fx_volume_fit(), X.seasonal_shares()
qcoefs = ([{"eq": "REMQ", "var": v, "coef": round(float(fit["coef"][v]), 2), "se": round(float(fit["se"][v]), 2), "r2": round(fit["r2"], 2),
            "period": fit["period"], "method": "МНК квартальные г/г, без константы, без 2022Q1–2023Q1",
            "note": "Частные переводы г/г: инерция прошлого квартала + рост EUR/USD (деньги идут из еврозоны)" if v == "REM_L" else ""}
           for v in ("REM_L", "EUR")]
          + [{"eq": eq, "var": v, "coef": c, "se": None, "r2": None, "period": "", "method": "калибровка", "note": note}
             for (eq, v), (c, note) in qc.items()]
          + [{"eq": f"FXVOL_{k}", "var": v, "coef": round(float(vol[k]["coef"][v]), 2), "se": round(float(vol[k]["se"][v]), 2),
              "r2": round(float(vol[k]["r2"]), 2), "period": "2016–2025", "method": "МНК квартальные, Newey–West, без 2022Q1–2023Q1",
              "note": ("Реальная девальвация (с лагом 2 кв.) на реальный " + {"EXP": "экспорт", "IMP": "импорт"}[k] +
                       ": незначима — объёмы задают урожай, порты и война; курс меняет гривневую стоимость. Не используется в формулах")
              if v == "RDEP" else ""}
             for k in ("EXP", "IMP") for v in vol[k]["coef"] if v != "const"])
Q_FIRST = 217  # after B1 section 7a (204-216)
qrow = {(r["eq"], r["var"]): Q_FIRST + i for i, r in enumerate(qcoefs)}
QK = lambda eq, v: f"COEFS!$E${qrow[(eq, v)]}"
out[f"COEFS!A{Q_FIRST}:L{Q_FIRST + len(qcoefs) - 1}"] = [
    [f"{r['eq']}_{r['var']}", "B5", r["eq"], r["var"], r["coef"], "" if r["se"] is None else r["se"],
     "" if not r["se"] else round(r["coef"] / r["se"], 1), r["period"], r["method"], "" if r["r2"] is None else r["r2"],
     "2026-10-26", r["note"]] for r in qcoefs]

EUR_SC = 199  # SCENARIOS: EUR/USD by scenario, active columns L:N
R = QROW
year = lambda i: QS[i][:4]
pc = lambda i, k=1: QC[i - k]
FACT_TRADE, FACT_FX = 5, 6  # last quarter with facts: trade, FDI, financing 2026Q2; rate and reserves 2026Q3
rem_part = dq.loc["2026Q3"]
rem_q3 = round(float(rem_part["REM_TOT_PART"]) * 3 / int(rem_part["REM_MONTHS"]))
rem_g = dq["REM_TOT"] / dq["REM_TOT"].shift(4) * 100 - 100
hist_g = rem_g.loc["2019Q1":"2026Q2"].dropna()
off_sh = float(dq.loc["2025Q3":"2026Q2", "REM_OFF"].sum() / dq.loc["2025Q3":"2026Q2", "REM_TOT"].sum())
res_prev = {q: float(hq["RES_USD"].shift().loc[q]) for q in QS[:6]}
flows = lambda q: float(hq.loc[q, "EXP_USD"] - hq.loc[q, "IMP_USD"] + dq.loc[q, "REM_TOT"] + hq.loc[q, "FDI_L_USD"] + hq.loc[q, "FIN_RECEIVED_USD"])
other_hist = {q: round(float(hq.loc[q, "RES_USD"]) - res_prev[q] - flows(q)) for q in QS[:6]}
nm = lambda v, d=2: f"{v:.{d}f}".replace(".", ",").replace("-", "−")


def line(code, name, eq, f, note=""):
    return [code, name, eq] + [f(i, c) for i, c in enumerate(QC)] + [note]


fxdep = hq["FX_AVG"] / hq["FX_AVG"].shift() * 100 - 100
hdr = lambda: ["Код", "Показатель", "Уравнение / единицы"] + QS + ["Комментарий"]
sec = [[] for _ in range(R["NOTE6"] - 42)]
put = lambda code, row: sec.__setitem__(R[code] - 43, row)
put("T4", ["4. Курс по кварталам (UAH/USD и EUR/USD)"])
put("H4", hdr())
put("FXQ_RULE", line("FXQ_RULE", "Девальвация гривны по правилу", "% к прошлому кварталу: ((1 + ИПЦ прошлого года − инфляция еврозоны "
                     "+ 3 × нехватка резервов ниже 5 мес.)^(1/4) − 1)",
                     lambda i, c: round(float(fxdep.loc[QS[i]]), 2) if i <= FACT_FX else (
                     f"=((1+({PY[year(i)]}$19-{YC[year(i)]}$18+{C('FX','RES')}*MAX(0;{C('FX','MONTHS')}-{PY[year(i)]}$35))/100)^(1/4)-1)*100"),
                     "до 2026Q3 — факт; дальше правило, как в годовом разделе 3: инфляция и резервы с лагом в год"))
put("FXQ_AVG", line("FXQ_AVG", "Курс UAH/USD, средний", "грн за 1 USD; ANCHORS строка 12", lambda i, c: f"=ANCHORS!{AC[QS[i]]}12",
                    "прогноз в ANCHORS = ориентир SCENARIOS строка 52, иначе прошлый квартал × (1 + правило)"))
put("FXQ_EOP", line("FXQ_EOP", "Курс UAH/USD, конец квартала", "средний × (средний / прошлый средний)^0,5",
                    lambda i, c: f"=ANCHORS!{AC[QS[i]]}13" if i <= 7 else f"={c}{R['FXQ_AVG']}*({c}{R['FXQ_AVG']}/{pc(i)}{R['FXQ_AVG']})^0,5",
                    "до 2026Q4 — ANCHORS (факт и введённое значение); дальше идёт в ANCHORS строка 13"))
put("EURUSD", line("EURUSD", "Курс EUR/USD, средний", f"факт — лист Dollar; прогноз — SCENARIOS строка {EUR_SC}",
                   lambda i, c: round(float(dq.loc[QS[i], "EURUSD"]), 4) if i <= FACT_FX else f"=SCENARIOS!{dict(zip('EFG', 'LMN'))[YC[year(i)]]}{EUR_SC}",
                   "месячные курсы НБУ на конец месяца"))
put("EURUSD_G", line("EURUSD_G", "Рост EUR/USD", "% г/г", lambda i, c: "" if i < 4 else f"=({c}{R['EURUSD']}/{pc(i, 4)}{R['EURUSD']}-1)*100"))
put("EURUAH", line("EURUAH", "Курс UAH/EUR, средний", "UAH/USD × EUR/USD", lambda i, c: f"={c}{R['FXQ_AVG']}*{c}{R['EURUSD']}"))
put("T5", ["5. Торговля, переводы и резервы по кварталам, млн USD"])
put("H5", hdr())
put("SEAS_EXP", line("SEAS_EXP", "Доля квартала в экспорте года", "среднее 2023–2025", lambda i, c: round(float(seas.loc[QS[i][-1], "EXP_USD"]), 3)))
put("SEAS_IMP", line("SEAS_IMP", "Доля квартала в импорте года", "среднее 2023–2025", lambda i, c: round(float(seas.loc[QS[i][-1], "IMP_USD"]), 3)))
for code, src, arow, name in (("EXPQ", "EXP_USD", 24, "Экспорт товаров и услуг"), ("IMPQ", "IMP_USD", 26, "Импорт товаров и услуг")):
    sh = R["SEAS_EXP"] if code == "EXPQ" else R["SEAS_IMP"]
    put(code, line(code, name, "факт; дальше год (раздел 2) × доля квартала; 2026 — остаток года после 1 полугодия",
                   lambda i, c, src=src, arow=arow, sh=sh: round(float(hq.loc[QS[i], src])) if i <= FACT_TRADE else
                   (f"=($E${arow}-SUM($H${R[code]}:$I${R[code]}))*{c}{sh}/($J${sh}+$K${sh})" if year(i) == "2026" else f"={YC[year(i)]}${arow}*{c}{sh}"),
                   "идёт в ANCHORS"))
put("TBQ", line("TBQ", "Сальдо торговли", "экспорт − импорт", lambda i, c: f"={c}{R['EXPQ']}-{c}{R['IMPQ']}"))
put("EXPQ_UAH", line("EXPQ_UAH", "Экспорт в гривне", "млрд грн: USD × средний курс", lambda i, c: f"={c}{R['EXPQ']}*{c}{R['FXQ_AVG']}/1000"))
put("IMPQ_UAH", line("IMPQ_UAH", "Импорт в гривне", "млрд грн: USD × средний курс", lambda i, c: f"={c}{R['IMPQ']}*{c}{R['FXQ_AVG']}/1000",
                     "база НДС и пошлин на импорт"))
put("TB_FX", line("TB_FX", "Курсовой эффект в сальдо", "млрд грн: сальдо в USD × изменение курса за год",
                  lambda i, c: "" if i < 4 else f"={c}{R['TBQ']}*({c}{R['FXQ_AVG']}-{pc(i, 4)}{R['FXQ_AVG']})/1000",
                  "объёмы от курса не зависят (COEFS FXVOL_, t < 1,5): девальвация меняет гривневую стоимость торговли"))
# migration shifts the level once: it is added back to last quarter's growth before the AR term, so it does not compound
mig = lambda c0, c1: f"{QK('REMQ','MIGR')}*SUM(B4_LABOUR!{c0}14:{c1}14)/{QK('REMQ','STOCK')}*100"
put("REMQ_G", line("REMQ_G", "Рост частных переводов", f"% г/г: {nm(fit['coef']['REM_L'])} × прошлый квартал + {nm(fit['coef']['EUR'])} × рост EUR/USD "
                   "− возврат мигрантов за 4 квартала / украинцы за границей",
                   lambda i, c: round(float(rem_g.loc[QS[i]]), 1) if i < 4 else (f"=({c}{R['REMQ']}/{pc(i, 4)}{R['REMQ']}-1)*100" if i <= FACT_FX else
                   f"={QK('REMQ','REM_L')}*({pc(i)}{R['REMQ_G']}+{mig(pc(i, 4), pc(i))})+{QK('REMQ','EUR')}*{c}{R['EURUSD_G']}"
                   f"-{mig(pc(i, 3), c)}"),
                   f"R² {nm(fit['r2'])}; миграция — B4_LABOUR строка 14 (+ = возврат)"))
put("REMQ", line("REMQ", "Частные переводы в Украину", "оплата труда + трансферты; прошлый год × (1 + рост)",
                 lambda i, c: round(float(dq.loc[QS[i], "REM_TOT"])) if i <= FACT_TRADE else (rem_q3 if i == 6 else
                 f"={pc(i, 4)}{R['REMQ']}*(1+{c}{R['REMQ_G']}/100)"),
                 f"лист Dollar; 2026Q3 — {int(rem_part['REM_MONTHS'])} месяца факта × 3 / {int(rem_part['REM_MONTHS'])}"))
put("REMQ_OFF", line("REMQ_OFF", "  через официальные каналы", f"доля 2025Q3–2026Q2: {nm(off_sh * 100, 1)}%",
                     lambda i, c: round(float(dq.loc[QS[i], "REM_OFF"])) if i <= FACT_TRADE else f"={c}{R['REMQ']}*{nm(off_sh, 3).replace('−', '-')}",
                     "банки и платёжные системы"))
put("REMQ_INF", line("REMQ_INF", "  через неформальные каналы", "переводы − официальные",
                     lambda i, c: round(float(dq.loc[QS[i], "REM_INF"])) if i <= FACT_TRADE else f"={c}{R['REMQ']}-{c}{R['REMQ_OFF']}",
                     "оценка НБУ (наличные через границу и т. п.)"))
put("FDIQ", line("FDIQ", "Прямые инвестиции (чистые обязательства)", "год (раздел 2) / 4; 2026 — остаток после 1 полугодия",
                 lambda i, c: round(float(hq.loc[QS[i], "FDI_L_USD"])) if i <= FACT_TRADE else
                 ("=($E$29-SUM($H${0}:$I${0}))/2".format(R["FDIQ"]) if year(i) == "2026" else f"={YC[year(i)]}$29/4")))
put("OTHERQ", line("OTHERQ", "Прочие потоки", f"COEFS BOP_OTHER / 4 ({nm(-9000 / 4, 0)}); факт — остаток по изменению резервов",
                   lambda i, c: other_hist[QS[i]] if i <= FACT_TRADE else
                   f"={C('BOP','OTHER')}/4",
                   "2026Q3: резервы известны, потоки ещё нет — неизвестным считается транш (ANCHORS строка 29)"))
put("FINQ", line("FINQ", "Получено внешнего финансирования", "ANCHORS строка 29 (транши SCENARIOS строки 40–46)",
                 lambda i, c: f"=ANCHORS!{AC[QS[i]]}29"))
put("NEEDQ", line("NEEDQ", "Потребность во внешнем финансировании", "−(сальдо + переводы + ПИИ + прочие)",
                  lambda i, c: f"=-({c}{R['TBQ']}+{c}{R['REMQ']}+{c}{R['FDIQ']}+{c}{R['OTHERQ']})", "идёт в ANCHORS строка 28"))
put("GAPQ", line("GAPQ", "Разрыв (потребность − получено)", "> 0: покрывается резервами", lambda i, c: f"={c}{R['NEEDQ']}-{c}{R['FINQ']}"))
put("RES_REVAL", line("RES_REVAL", "Переоценка резервов (евро)", "резервы прошлого квартала × доля евро × изменение EUR/USD",
                      lambda i, c: "" if i == 0 else f"={pc(i)}{R['RESQ']}*{QK('RESQ','EUR_SH')}*({c}{R['EURUSD']}/{pc(i)}{R['EURUSD']}-1)",
                      "COEFS RESQ_EUR_SH — оценка"))
put("RESQ", line("RESQ", "Международные резервы, конец квартала", "прошлый квартал − разрыв + переоценка",
                 lambda i, c: f"=ANCHORS!{AC[QS[i]]}24" if i <= FACT_FX else f"={pc(i)}{R['RESQ']}-{c}{R['GAPQ']}+{c}{R['RES_REVAL']}",
                 "до 2026Q3 — факт; идёт в ANCHORS строка 24"))
put("RESQ_M", line("RESQ_M", "Резервы, месяцев импорта", "резервы / импорт 4 кварталов × 12",
                   lambda i, c: "" if i < 3 else f"={c}{R['RESQ']}/SUM({pc(i, 3)}{R['IMPQ']}:{c}{R['IMPQ']})*12"))
put("RES_CHK", line("RES_CHK", "Проверка: резервы", "не ниже 3 месяцев импорта",
                    lambda i, c: "" if i < FACT_FX else f"=IF({c}{R['RESQ_M']}<3;\"ВНИМАНИЕ: резервы ниже 3 месяцев импорта\";\"OK\")"))
lo, hi = round(float(hist_g.min()), 1), round(float(hist_g.max()), 1)
put("REM_CHK", line("REM_CHK", "Проверка: переводы против истории", f"рост г/г 2019–2026 от {nm(lo, 1)} до {nm(hi, 1)}%",
                    lambda i, c: "" if i <= FACT_FX else f"=IF(OR({c}{R['REMQ_G']}<{nm(lo, 1).replace('−', '-')};{c}{R['REMQ_G']}>{nm(hi, 1)});"
                    f"\"ВНИМАНИЕ: переводы вне истории\";\"OK\")"))
put("T6", ["6. Курсовые переоценки валютного госдолга"])
put("H6", hdr())
B6Y = {"2026": "D", "2027": "E", "2028": "F"}
put("DEBT_START", line("DEBT_START", "Валютный госдолг на начало года", "млрд USD, B6_FISCAL строка 43 прошлого года",
                       lambda i, c: "" if i < 4 else f"=B6_FISCAL!{B6Y[year(i)]}43"))
put("DEBT_REVAL_USD", line("DEBT_REVAL_USD", "Переоценка долга в USD (евро)", "млрд USD: долг × доля евро × изменение EUR/USD",
                           lambda i, c: "" if i < 4 else f"={c}{R['DEBT_START']}*{QK('DEBTQ','EUR_SH')}*({c}{R['EURUSD']}/{pc(i)}{R['EURUSD']}-1)",
                           "сумма за год идёт в B6_FISCAL строка 43"))
put("DEBT_REVAL_UAH", line("DEBT_REVAL_UAH", "Переоценка долга в гривне", "млрд грн: долг × изменение курса конца квартала + евро × курс",
                           lambda i, c: "" if i < 4 else f"={c}{R['DEBT_START']}*({c}{R['FXQ_EOP']}-{pc(i)}{R['FXQ_EOP']})+{c}{R['DEBT_REVAL_USD']}*{c}{R['FXQ_EOP']}",
                           "рост долга без новых займов"))
put("DEBT_REVAL_GDP", line("DEBT_REVAL_GDP", "Переоценка долга, % ВВП года", "переоценка / номинальный ВВП года",
                           lambda i, c: "" if i < 4 else f"={c}{R['DEBT_REVAL_UAH']}*1000/SUM(ANCHORS!{AC[year(i) + 'Q1']}8:{AC[year(i) + 'Q4']}8)*100"))
put("NOTE6", ["Как читать: девальвация на 1 грн за доллар увеличивает валютный долг в гривне на величину долга в млрд USD (в млрд грн). Рост евро к доллару "
              "увеличивает долг в долларах (кредиты ЕС в евро) и резервы (часть резервов в евро). Доли евро — оценки Claude в COEFS."])
out[f"B5_EXTERNAL!A43:T{R['NOTE6']}"] = sec

# EUR/USD by scenario (SCENARIOS rows 196-199): written only without --coefs
EUR = {"Base": [1.15, 1.15, 1.15], "Pess": [1.15, 1.10, 1.08], "Opt": [1.15, 1.18, 1.20]}
out[f"SCENARIOS!A{EUR_SC - 3}:O{EUR_SC}"] = [
    ["Курс EUR/USD (B5_EXTERNAL раздел 4)"],
    ["Параметр", "Единицы", "База", "", "", "Пессимистичный", "", "", "Оптимистичный", "", "", "Активный", "", "", "Источник"],
    ["", "", 2026, 2027, 2028, 2026, 2027, 2028, 2026, 2027, 2028, 2026, 2027, 2028],
    ["EUR/USD, средний за год", "долларов за 1 евро"] + EUR["Base"] + EUR["Pess"] + EUR["Opt"] +
    [f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{a}{EUR_SC};{b}{EUR_SC};{d}{EUR_SC})" for a, b, d in zip("CDE", "FGH", "IJK")] +
    ["2026 — для 4 кв. (3 кв. факт 1,149). Оценка Claude: пессимистичный — доллар крепнет (бегство от риска), "
     "оптимистичный — евро растёт с восстановлением Европы"]]

# ANCHORS forecast links (columns BB:BK = B5 J:S)
fq = {q: QC[i] for i, q in enumerate(QS)}
out["ANCHORS!BD13:BK13"] = [[f"=B5_EXTERNAL!{fq[q]}{R['FXQ_EOP']}" for q in QS[8:]]]
out["ANCHORS!BB21:BK21"] = [[f"=B5_EXTERNAL!{fq[q]}{R['EXPQ']}" for q in QS[6:]]]
out["ANCHORS!BB22:BK22"] = [[f"=B5_EXTERNAL!{fq[q]}{R['IMPQ']}" for q in QS[6:]]]
out["ANCHORS!BC24:BK24"] = [[f"=B5_EXTERNAL!{fq[q]}{R['RESQ']}" for q in QS[7:]]]
out["ANCHORS!AV28:BK28"] = [[f"=B5_EXTERNAL!{fq[q]}{R['NEEDQ']}" for q in QS]]
if "--coefs" in sys.argv:
    out = {k: v for k, v in out.items() if not k.startswith("SCENARIOS")}

look = lambda c, r: f"INDEX(B5_EXTERNAL!$E${r}:$G${r};MATCH({c}$2;B5_EXTERNAL!$E$10:$G$10;0))"
gr = lambda c, r: f"INDEX(B5_EXTERNAL!$E${r}:$G${r};MATCH({c}$2;B5_EXTERNAL!$E$10:$G$10;0))/INDEX(B5_EXTERNAL!$D${r}:$F${r};MATCH({c}$2;B5_EXTERNAL!$E$10:$G$10;0))"
out["ANCHORS!BD29"] = [[f"={look('BD', 32)}/4"]]
out["B3_PRICES!F11:G11"] = [["=B5_EXTERNAL!F40", "=B5_EXTERNAL!G40"]]
out["B3_PRICES!H11"] = [["2026: курс из ANCHORS. 2027–2028 — из B5_EXTERNAL (инфляционный разрыв и резервы)"]]
out["CHECKS!A23:C24"] = [["Резервы, месяцев импорта", "Резервы / импорт × 12; не ниже порога", 3], ["  статус"]]
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
