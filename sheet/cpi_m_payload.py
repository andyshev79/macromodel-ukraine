"""CPI_M sheet (12.11.2026): monthly CPI by the NBU's blocks, the 6-month nowcast, the benchmark and the accuracy log.

Sections:
1. Summary of the six forecast months (nowcast, benchmark, naive, Andrey's MacroStat forecast).
2. Quarter anchors: end-of-quarter y/y of the blocks for the two quarters the nowcast covers; B3_PRICES
   columns G:H (2026Q4, 2027Q1) read them. Raw food and administered prices move from the last NBU value by
   the change of the rebuilt block (the rebuilt level differs from the NBU's, its changes track them).
3. Block equations (month intercepts, inertia, FX) and the headline weights.
4. Benchmark coefficients by horizon.
5. Checks (ВНИМАНИЕ / OK).
6. Backtest accuracy by horizon and the forecast log.
7. Monthly table: history (values) and the six forecast months (formulas over sections 3-4; yellow = inputs:
   FX m/m, utilities m/m; fuel follows the SCENARIOS fuel input row).

Run after `python -m macromodel.cpi_monthly` (or with --refresh to download first). Output: JSON {range: 2D list},
formulas in ru_RU syntax. `--log` also appends the current forecasts to data/cpi_m/forecast_log.csv.
"""
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

from macromodel import cpi_monthly as C
from macromodel import scenario_layout as SL
from sheet import cpi_m_layout as L

h = C.build_history(refresh="--refresh" in sys.argv)
O = pd.Period(L.ORIGIN, "M")
assert h["CPI_MM"].dropna().index[-1] == O, f"last Gosstat month {h['CPI_MM'].dropna().index[-1]} != layout ORIGIN {O}"
MONTHS = list(pd.period_range(O + 1, O + C.H, freq="M"))
gw, bw, wr2 = C.weights()
est = C.estimate_blocks(h)
bmc = C.benchmark_coefs(h)
bt = pd.read_csv(C.OUT / "backtest.csv") if (C.OUT / "backtest.csv").exists() else C.backtest(h)
acc_all, acc_rec = C.accuracy(bt), C.accuracy(bt, "2023-04")
R = L.month_row
c = L.COLS
s = lambda m: f"'{m}"          # month as text, not a date
r2 = lambda v, n=3: None if v is None or pd.isna(v) else round(float(v), n)
WX = sum(gw[g] for g in ("02", "07_3", "08"))
WU = gw["04"]
DAILY = pd.read_csv(C.RAW_DIR / "usd_daily.csv", index_col=0, parse_dates=True).iloc[:, 0]
MTD = DAILY.loc[str(O + 1)] if str(O + 1) in DAILY.index.strftime("%Y-%m") else pd.Series(dtype=float)
FX_IN = {MONTHS[0]: round((MTD.mean() / h.loc[O, "FX"] - 1) * 100, 2) if len(MTD) else 0.0}
EXP_USED = h["EXP_HH"].loc[:O].dropna()
NBU_IR = {"CPI": (12.5, 11.7), "CORE": (10.9, 10.7), "RAW": (11.3, 10.5), "ADM": (14.0, 13.9), "FUEL": (53.6, 28.7)}
BEFORE = {"CPI": (12.3, 12.1), "CORE": (8.26, 7.83), "RAW": (15.28, 22.49), "ADM": (13.04, 12.67), "FUEL": (65.48, 53.48)}
ANDREY = {}
ms = pd.read_csv(C.OUT / "macrostat_cpi.csv")
for _, x in ms[ms.kind == "forecast"].iterrows():
    ANDREY[x.month] = round(x.CPI_YY - 100, 1)
msf = ms[ms.kind == "fact"].set_index("month")
MS_DIFF = max(abs(msf.loc[m, k] - 100 - h.loc[pd.Period(m, "M"), k]) for m in msf.index for k in ["CPI_YY", "CPI_MM", "CORE_YY", "CORE_MM"])

out = {}
TODAY = date.today().isoformat()
out[f"{L.SHEET}!A1:A3"] = [
    ["ИПЦ помесячно: история по блокам НБУ, nowcast на 6 месяцев, эталон и журнал точности"],
    [f"Факт по {L.ORIGIN} (Госстат, совпадает с MacroStat). Пересчёт {TODAY}: python -m macromodel.cpi_monthly, "
     f"затем sheet/cpi_m_payload.py. Жёлтые ячейки раздела 7 — ввод (курс, ЖКУ); топливо берётся из SCENARIOS строка {SL.FUEL_QQ}."],
    ["Первые 6 месяцев — помесячно; конец 2026Q4 и 2027Q1 идёт в B3_PRICES (колонки G:H), дальше квартальные уравнения B3 стартуют от этой точки."],
]

# ---------- section 7: monthly table ----------
first_fc = R(str(MONTHS[0]))
hdr7 = ["Месяц", "Тип", "ИПЦ м/м", "ИПЦ г/г", "Базовая м/м", "Базовая г/г", "Сырые м/м", "Сырые г/г",
        "Админ без ЖКУ м/м", "ЖКУ м/м", "Админ м/м", "Админ г/г", "Топливо м/м", "Топливо г/г", "Курс UAH/USD, средний",
        "Курс м/м", "Курс г/г", "ИПЦ из блоков м/м (проверка весов)", "НБУ: сырые г/г", "НБУ: админ г/г", "НБУ: топливо г/г",
        "Ожидания: домохозяйства", "Ожидания: аналитики", "Ожидания: банки", "Ожидания: бизнес", "Флаг"]
rows7 = [["7. История и прогноз по месяцам (% м/м и % г/г; м/м — к прошлому месяцу)"], hdr7]
hist = h.loc[L.HIST_FIRST:str(O)]
for m, x in hist.iterrows():
    reb = None if pd.isna(x["REB_MM"]) else round(float(x["REB_MM"]), 3)
    rows7.append([s(str(m)), "факт", r2(x.CPI_MM, 2), r2(x.CPI_YY, 2), r2(x.CORE_MM, 2), r2(x.CORE_YY, 2), r2(x.RAW_MM),
                  r2(x.RAW_YY), r2(x.ADMX_MM), r2(x.UTIL_MM, 2), r2(x.ADM_MM), r2(x.ADM_YY), r2(x.FUEL_MM), r2(x.FUEL_YY),
                  r2(x.FX, 4), r2(x.FX_MM), r2(x.FX_YY), reb, r2(x.NBU_RAW_YY, 1), r2(x.NBU_ADM_YY, 1), r2(x.NBU_FUEL_YY, 1),
                  r2(x.EXP_HH, 2), r2(x.EXP_ANALYSTS, 2), r2(x.EXP_BANKS, 2), r2(x.EXP_BUSINESS, 2), ""])
rows7 = [[("" if v is None else v) for v in row] for row in rows7]
W = L.W_ROW


def yy(col_mm: str, col_yy: str, r: int) -> str:
    return f"=((1+{col_yy}{r - 1}/100)*(1+{col_mm}{r}/100)/(1+{col_mm}{r - 12}/100)-1)*100"


for m in MONTHS:
    r = R(str(m))
    k = m.month
    e = L.EQ_ROW
    mi = lambda row: f"INDEX($B${row}:$M${row};{k})"
    q = str(m.asfreq("Q"))
    sc = {"2026Q4": "D", "2027Q1": "E", "2027Q2": "F", "2027Q3": "G"}[q]
    q_start = m.asfreq("Q").asfreq("M", "start")
    earlier = [R(str(p)) for p in pd.period_range(q_start, m - 1, freq="M")] if m > q_start else []
    prod = "*".join(f"(1+M{x}/100)" for x in earlier) or "1"
    left = 3 - len(earlier)
    fuel = (f"=IF(SCENARIOS!{sc}{SL.FUEL_QQ}=\"\";M{r - 12};(((1+SCENARIOS!{sc}{SL.FUEL_QQ}/100)/({prod}))^(1/{left})-1)*100)")
    rows7.append([
        s(str(m)), "прогноз",
        f"=$B${W}+$C${W}*E{r}+$D${W}*G{r}+$E${W}*K{r}+$F${W}*M{r}", yy("C", "D", r),
        f"={mi(e['CORE'])}+$N${e['CORE']}*E{r - 1}+$O${e['CORE']}*P{r - 1}", yy("E", "F", r),
        f"={mi(e['RAW'])}+$N${e['RAW']}*G{r - 1}+$O${e['RAW']}*P{r - 1}", yy("G", "H", r),
        f"={mi(e['ADMX'])}+$N${e['ADMX']}*I{r - 1}", f"=$B${L.UTIL_ROW}",
        f"=($I${W}*I{r}+$J${W}*J{r})/($I${W}+$J${W})", yy("K", "L", r),
        fuel, yy("M", "N", r),
        f"=O{r - 1}*(1+P{r}/100)", FX_IN.get(m, 0), f"=(O{r}/O{r - 12}-1)*100", "", "", "", "", "", "", "", "",
        f"=IF(OR(C{r}<INDEX($B${L.SEAS_MIN}:$M${L.SEAS_MIN};{k});C{r}>INDEX($B${L.SEAS_MAX}:$M${L.SEAS_MAX};{k}));"
        f"\"ВНИМАНИЕ: ИПЦ м/м вне диапазона этого месяца в 2017–2025\";\"OK\")",
    ])
last_row = L.T_FIRST + len(rows7) - 3
out[f"{L.SHEET}!A{L.S7_HDR}:Z{last_row}"] = rows7
assert R(str(MONTHS[-1])) == last_row

# ---------- section 1: summary ----------
ro = R(str(O))
rows1 = [["1. Nowcast на 6 месяцев: ИПЦ и блоки, % г/г на конец месяца (подробно — раздел 7)"],
         ["Месяц", "ИПЦ м/м", "ИПЦ г/г", "Базовая", "Сырые", "Админ", "Топливо", "Эталон", "Наивный (г/г как сейчас)",
          "Прогноз Андрея (MacroStat)", "Nowcast − эталон", "Сезонность м/м"]]
for i, m in enumerate(MONTHS, start=1):
    r = R(str(m))
    b = L.BM_ROW[i]
    rows1.append([s(str(m)), f"=C{r}", f"=D{r}", f"=F{r}", f"=H{r}", f"=L{r}", f"=N{r}",
                  f"=$D${ro}+B{b}+C{b}*$Q${ro}+D{b}*($B${L.BM_EXP}-$D${ro})+E{b}*($D${ro}-$D${ro - 3})",
                  f"=$D${ro}", ANDREY.get(str(m), ""), f"=C{L.S1_FIRST + i - 1}-H{L.S1_FIRST + i - 1}", f"=Z{r}"])
out[f"{L.SHEET}!A{L.S1_HDR - 1}:L{L.S1_FIRST + len(MONTHS) - 1}"] = rows1

# ---------- section 2: quarter anchors ----------
def qend(q: str) -> int:
    return R(str(pd.Period(q, "Q").asfreq("M", "end")))


rsep = R(str(pd.Period("2026Q3", "Q").asfreq("M", "end")))
b3 = {"CORE": 42, "RAW": 38, "ADM": 41, "FUEL": 37, "CPI": 44}
ycol = {"CPI": "D", "CORE": "F", "RAW": "H", "ADM": "L", "FUEL": "N"}
how = {"CPI": "ИПЦ Госстата на конец квартала (nowcast)", "CORE": "базовая Госстата на конец квартала (nowcast)",
       "RAW": "НБУ сентябрь + изменение восстановленного блока с сентября",
       "ADM": "НБУ сентябрь + изменение восстановленного блока с сентября",
       "FUEL": "справочно: B3 считает топливо сам из ввода SCENARIOS строка 100"}
rows2 = [["2. Привязка кварталов модели: конец квартала, % г/г. Идёт в B3_PRICES (G:H) — сырые, админ, базовая и ИПЦ"],
         ["Код", "Показатель", "2026Q3 факт (B3)", "2026Q4 (декабрь)", "2027Q1 (март)", "Как считается",
          "НБУ, прогноз окт. 2026: Q4", "НБУ: Q1 2027", "Модель до nowcast: Q4", "Модель до nowcast: Q1", "Расхождение с НБУ"]]
for k in ["CPI", "CORE", "RAW", "ADM", "FUEL"]:
    rr = L.S2_ROW[k]
    yc = ycol[k]
    if k in ("CPI", "CORE"):
        q4, q1 = f"={yc}{qend('2026Q4')}", f"={yc}{qend('2027Q1')}"
    else:
        q4 = f"=$C{rr}+({yc}{qend('2026Q4')}-{yc}{rsep})"
        q1 = f"=$C{rr}+({yc}{qend('2027Q1')}-{yc}{rsep})"
    flag = (f"=IF(MAX(ABS(D{rr}-G{rr});ABS(E{rr}-H{rr}))>1,5;\"ВНИМАНИЕ: больше 1,5 п.п.\";\"OK\")"
            if k == "CPI" else f"=IF(MAX(ABS(D{rr}-G{rr});ABS(E{rr}-H{rr}))>3;\"ВНИМАНИЕ: больше 3 п.п.\";\"OK\")")
    rows2.append([k, C.NAMES[k], f"=B3_PRICES!{L.B3_FACT_COL}{b3[k]}", q4, q1, how[k], *NBU_IR[k], *BEFORE[k], flag])
out[f"{L.SHEET}!A{L.S2_HDR - 1}:K{L.S2_ROW['FUEL']}"] = rows2

# ---------- section 3: equations and weights ----------
mon = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
rows3 = [["3. Уравнения блоков, % м/м: константа месяца + инерция × м/м прошлого месяца + курс × м/м курса прошлого месяца "
          "(МНК 2017–2026 без 2022)"],
         ["Блок"] + mon + ["Инерция", "Курс (прошлый месяц)", "R²", "n", "σ остатка"]]
for b, nm in (("CORE", "Базовая инфляция"), ("RAW", "Сырые продукты"), ("ADMX", "Админцены без ЖКУ")):
    cf = est[b]["coef"]
    rows3.append([nm] + [r2(cf[f"M{i:02d}"], 4) for i in range(1, 13)] + [r2(cf["L1"], 4), r2(cf.get("FX_L1", 0), 4),
                                                                          r2(est[b]["r2"], 2), est[b]["n"], r2(est[b]["sigma"], 3)])
hs = h["CPI_MM"].loc["2017-01":"2025-12"]
hs = hs[~C._war_mask(hs.index)]
g = hs.groupby(hs.index.month)
rows3.append(["ИПЦ м/м, минимум месяца 2017–2025 (без 2022)"] + [r2(v, 2) for v in g.min()])
rows3.append(["ИПЦ м/м, максимум месяца 2017–2025 (без 2022)"] + [r2(v, 2) for v in g.max()])
rows3.append(["ЖКУ м/м без решений о тарифах", r2(C.util_drift(h), 2),
              "медиана м/м с 2023 без месяцев повышения (>3%); тарифы растут только после отмены военного положения (правило 30.10)"])
wc = est["W"]["coef"]
rows3.append(["Веса ИПЦ из блоков (МНК 2017–2026, м/м)", "Константа", "Базовая", "Сырые", "Админ", "Топливо", "Сумма весов",
              "R²", "Админ без ЖКУ: вес групп", "ЖКУ: вес групп"])
rows3.append(["", r2(wc["const"], 4), r2(wc["CORE_MM"], 4), r2(wc["RAW_MM"], 4), r2(wc["ADM_MM"], 4), r2(wc["FUEL_MM"], 4),
              f"=SUM(C{W}:F{W})", r2(est["W"]["r2"], 3), r2(WX, 4), r2(WU, 4)])
grp = "; ".join(f"{nm.lower()} {gw[gc]:.3f}".replace(".", ",") for b, gs in C.GROUPS.items() for gc, nm in gs.items())
rows3.append([f"Группы Госстата в блоках (вес в ИПЦ, НМНК, R² {wr2:.3f}): базовая {gw['_Z']:.3f}; {grp}".replace(".", ",")
              .replace("R² 0,", "R² 0,")])
out[f"{L.SHEET}!A{L.S3_HDR - 1}:R{W + 1}"] = rows3

# ---------- section 4: benchmark ----------
rows4 = [["4. Эталон: изменение ИПЦ г/г за h месяцев = константа + курс г/г + (ожидания домохозяйств − инфляция) "
          "+ ускорение г/г за 3 месяца (МНК 2016–2026 без 2022)"],
         ["h, мес.", "Константа", "Курс г/г", "Ожидания − инфляция", "Ускорение за 3 мес.", "R²", "n"]]
for k in range(1, C.H + 1):
    cf = bmc[k]["coef"]
    rows4.append([k, r2(cf["const"], 4), r2(cf["FXY"], 4), r2(cf["GAP"], 4), r2(cf["D3"], 4), r2(bmc[k]["r2"], 2), bmc[k]["n"]])
rows4.append(["Ожидания домохозяйств на момент прогноза", r2(EXP_USED.iloc[-1], 2),
              f"последний опрос НБУ: {EXP_USED.index[-1]} (за {L.ORIGIN} опроса домохозяйств ещё нет)"])
out[f"{L.SHEET}!A{L.S4_HDR - 1}:G{L.BM_EXP}"] = rows4

# ---------- section 6: accuracy ----------
def acc_rows(a: pd.DataFrame) -> list:
    out_ = []
    for _, x in a.iterrows():
        best = min(["NOWCAST_RW", "BENCH", "NAIVE"], key=lambda m: x[f"{m}_MAE"])
        out_.append([int(x.h), int(x.n), r2(x.NOWCAST_MAE, 2), r2(x.NOWCAST_RW_MAE, 2), r2(x.BENCH_MAE, 2), r2(x.NAIVE_MAE, 2),
                     r2(x.CORE_MAE, 2), r2(x.RAW_MAE, 2), r2(x.ADM_MAE, 2), r2(x.FUEL_MAE, 2),
                     {"NOWCAST_RW": "nowcast", "BENCH": "эталон", "NAIVE": "наивный"}[best]])
    return out_


acc_hdr = ["h, мес.", "n", "Nowcast (курс, топливо, ЖКУ известны)", "Nowcast (как в реальном времени)", "Эталон", "Наивный",
           "Базовая (nowcast)", "Сырые", "Админ", "Топливо", "Лучший в реальном времени"]
rows6 = [["6. Точность: бэктест с 2019 года (каждая точка оценивает уравнения только на прошлом), средняя абсолютная "
          "ошибка г/г, п.п.; 2022 исключён"], acc_hdr] + acc_rows(acc_all)
rows6 += [["С апреля 2023 (после военного шока)"], acc_hdr] + acc_rows(acc_rec)
out[f"{L.SHEET}!A{L.S6_HDR}:K{L.ACC_RECENT + len(acc_rec) - 1}"] = rows6

# forecast log: append this run, then show the CPI rows of the latest vintages
nc_py = C.nowcast(h, O, est, fuel_qq={"2026Q4": 15, "2027Q1": 10, "2027Q2": 2}, fx_path=FX_IN)
bm_py = C.benchmark(h, O)
if "--log" in sys.argv:
    C.append_log(O, nc_py, bm_py, TODAY)
lg = pd.read_csv(C.LOG_CSV, dtype={"origin": str, "target": str}) if C.LOG_CSV.exists() else pd.DataFrame()
lg = lg[lg.model.isin(["NOWCAST", "BENCH"])].sort_values(["origin", "target", "model"], ascending=[False, True, False])
lg = lg.head(L.LOG_ROWS)
rows_log = [["Журнал прогнозов ИПЦ г/г: каждый пересчёт дописывает строки (data/cpi_m/forecast_log.csv), ошибка появляется, "
             "когда выходит факт"],
            ["Прогноз от (факт по)", "Месяц", "Горизонт, мес.", "Модель", "Прогноз г/г", "Факт г/г", "Ошибка, п.п."]]
for i, x in enumerate(lg.itertuples()):
    r = L.LOG_FIRST + i
    fact = (f"=IFERROR(IF(INDEX($B${L.T_FIRST}:$B$400;MATCH(B{r};$A${L.T_FIRST}:$A$400;0))=\"факт\";"
            f"INDEX($D${L.T_FIRST}:$D$400;MATCH(B{r};$A${L.T_FIRST}:$A$400;0));\"\");\"\")")
    rows_log.append([s(x.origin), s(x.target), int(x.h), {"NOWCAST": "nowcast", "BENCH": "эталон"}[x.model],
                     round(x.forecast, 2), fact, f"=IF(F{r}=\"\";\"\";E{r}-F{r})"])
rows_log += [[""] * 7] * (L.LOG_ROWS - len(lg))
out[f"{L.SHEET}!A{L.LOG_HDR - 1}:G{L.LOG_FIRST + L.LOG_ROWS - 1}"] = rows_log

# ---------- section 5: checks ----------
lastn = lambda col: f"INDEX({col}{L.T_FIRST}:{col}{ro};{ro - L.T_FIRST + 1})"
last12 = f"{ro - 11}"
nbu_last = {k: h[f"NBU_{k}_YY"].dropna().index[-1] for k in ("RAW", "ADM", "FUEL")}
a = acc_all
checks = [
    ["Данные Госстата = MacroStat (ИПЦ и базовая, м/м и г/г, 2025-01…" + L.ORIGIN + ")", round(MS_DIFF, 3), "0", "OK" if MS_DIFF < 0.05 else "ВНИМАНИЕ",
     "наибольшее расхождение, п.п.; лист CPI файла MacroStat"],
    ["Подбор весов групп Госстата: R² ИПЦ м/м", round(wr2, 3), "≥ 0,95", "OK" if wr2 >= 0.95 else "ВНИМАНИЕ",
     "НМНК 2017–2026, группы → ИПЦ"],
    ["Сумма весов блоков в ИПЦ", f"=G{W}", "0,95–1,05", f"=IF(AND(B{L.CHK_FIRST + 2}>=0,95;B{L.CHK_FIRST + 2}<=1,05);\"OK\";\"ВНИМАНИЕ\")",
     "веса МНК по м/м 2017–2026"],
    ["ИПЦ из блоков против факта, м/м: средняя ошибка за 12 месяцев", f"=AVERAGE(ARRAYFORMULA(ABS(R{last12}:R{ro}-C{last12}:C{ro})))",
     "≤ 0,2", f"=IF(B{L.CHK_FIRST + 3}<=0,2;\"OK\";\"ВНИМАНИЕ\")", "веса групп воспроизводят индекс Госстата"],
]
for k, nm in (("RAW", "Сырые"), ("ADM", "Админ"), ("FUEL", "Топливо")):
    rr = R(str(nbu_last[k]))
    col = {"RAW": "H", "ADM": "L", "FUEL": "N"}[k]
    ncol = {"RAW": "S", "ADM": "T", "FUEL": "U"}[k]
    i = L.CHK_FIRST + len(checks)
    checks.append([f"{nm}: восстановленный блок против НБУ, г/г, {nbu_last[k]}", f"={col}{rr}-{ncol}{rr}", "± 3",
                   f"=IF(ABS(B{i})<=3;\"OK\";\"ВНИМАНИЕ\")",
                   "уровень в B3 берётся от НБУ, из восстановленного — только изменение" if k != "FUEL" else "совпадает с НБУ"])
i = L.CHK_FIRST + len(checks)
checks.append(["Сезонность: прогнозные м/м ИПЦ вне диапазона своего месяца 2017–2025", f"=COUNTIF(Z{first_fc}:Z{last_row};\"ВНИМ*\")",
               "0", f"=IF(B{i}=0;\"OK\";\"ВНИМАНИЕ\")", "правило: прогноз ведёт себя как история того же месяца, иначе нужно объяснение"])
beats_naive = bool((a.NOWCAST_RW_MAE < a.NAIVE_MAE).all())
beats_bench = bool((a.NOWCAST_RW_MAE < a.BENCH_MAE).all())
checks.append(["Бэктест: nowcast (реальное время) точнее наивного на всех горизонтах 1–6",
               f"{a.NOWCAST_RW_MAE.iloc[-1]:.2f} против {a.NAIVE_MAE.iloc[-1]:.2f}".replace(".", ",") + " на 6 мес.", "да",
               "OK" if beats_naive else "ВНИМАНИЕ", "раздел 6"])
checks.append(["Бэктест: nowcast точнее эталона на всех горизонтах 1–6",
               f"{a.NOWCAST_RW_MAE.iloc[-1]:.2f} против {a.BENCH_MAE.iloc[-1]:.2f}".replace(".", ",") + " на 6 мес.", "да",
               "OK" if beats_bench else "ВНИМАНИЕ", "если эталон начнёт выигрывать — детализация вредит"])
i = L.CHK_FIRST + len(checks)
checks.append(["Nowcast − эталон через 6 месяцев, п.п.", f"=K{L.S1_FIRST + C.H - 1}", "± 3",
               f"=IF(ABS(B{i})<=3;\"OK\";\"ВНИМАНИЕ: nowcast далеко от простого эталона\")", "разрыв надо объяснить"])
i = L.CHK_FIRST + len(checks)
checks.append(["Nowcast против прогноза НБУ (окт. 2026), ИПЦ Q4 / Q1", f"=MAX(ABS(D15-G15);ABS(E15-H15))", "≤ 1,5",
               f"=K{L.S2_ROW['CPI']}", "главная причина — ввод топлива SCENARIOS строка 100 (15% и 10% кв/кв против −0,6% у НБУ в Q1)"])
i = L.CHK_FIRST + len(checks)
checks.append(["B3: ИПЦ из блоков без влияния ставки (строка 43 − B7) против nowcast ИПЦ (строка 44), Q4 и Q1",
               "=MAX(ABS(B3_PRICES!G43-B7_MONETARY!$E$42-B3_PRICES!G44);ABS(B3_PRICES!H43-B7_MONETARY!$F$42-B3_PRICES!H44))", "≤ 1",
               f"=IF(B{i}<=1;\"OK\";\"ВНИМАНИЕ: веса блоков B3 и nowcast расходятся\")",
               "квартальные веса B3 против месячных; влияние ставки B7 в ближайшие 2 квартала уже сидит в месячной истории"])
i = L.CHK_FIRST + len(checks)
apr = R(str(MONTHS[-1]))
checks.append(["Стык: ИПЦ апреля 2027 (месячный) против 2027Q2 из уравнений B3, п.п.", f"=B3_PRICES!I44-D{apr}", "± 1,5",
               f"=IF(ABS(B{i})<=1,5;\"OK\";\"ВНИМАНИЕ: скачок на стыке месячной и квартальной частей\")",
               "после 2027Q1 квартальные уравнения стартуют от точки nowcast"])
i = L.CHK_FIRST + len(checks)
checks.append(["Ошибки формул на листе", f"=SUMPRODUCT(--ISERROR(A1:Z{L.S5_HDR - 2}))+SUMPRODUCT(--ISERROR(A{L.S6_HDR}:Z{last_row}))", "0",
               f"=IF(B{i}=0;\"OK\";\"ВНИМАНИЕ\")", "все разделы, кроме проверок"])
out[f"{L.SHEET}!A{L.S5_HDR - 1}:E{L.CHK_FIRST + len(checks) - 1}"] = (
    [["5. Проверки"], ["Проверка", "Значение", "Порог", "Флаг", "Пояснение"]] + checks)
assert L.CHK_FIRST + len(checks) - 1 < L.S6_HDR

# ---------- B3_PRICES: the two nowcast quarters read CPI_M ----------
for q, bc in L.B3_COL.items():
    cc = L.S2_COL[q]
    out[f"B3_PRICES!{bc}38"] = [[f"={L.SHEET}!{cc}{L.S2_ROW['RAW']}"]]
    out[f"B3_PRICES!{bc}39"] = [[f"={L.SHEET}!{cc}{L.S2_ROW['ADM']}-{bc}40"]]
    out[f"B3_PRICES!{bc}42"] = [[f"={L.SHEET}!{cc}{L.S2_ROW['CORE']}"]]
    out[f"B3_PRICES!{bc}44"] = [[f"=IF(SCENARIOS!{L.SCQ[q]}{SL.CPI_Q}<>\"\";SCENARIOS!{L.SCQ[q]}{SL.CPI_Q};{L.SHEET}!{cc}{L.S2_ROW['CPI']})"]]
out["B3_PRICES!P38"] = [["овощи, фрукты, мясо, яйца, молоко; 2026Q4–2027Q1 — nowcast CPI_M (раздел 2)"]]
out["B3_PRICES!P39"] = [["акцизы на табак и алкоголь, проезд, связь; 2026Q4–2027Q1 — nowcast CPI_M минус тарифы"]]
out["B3_PRICES!P42"] = [["обработанные продукты, непродовольственные товары, услуги; 2026Q4–2027Q1 — nowcast CPI_M"]]
out["B3_PRICES!P44"] = [["идёт в ANCHORS, строка 10; 2026Q4–2027Q1 — nowcast CPI_M, если в SCENARIOS строка 90 пусто"]]
out[f"SCENARIOS!B{SL.CPI_Q}"] = [["% г/г, конец квартала; пусто = nowcast CPI_M"]]

if "--print" in sys.argv:
    print(nc_py.round(2).to_string(), file=sys.stderr)
json.dump(out, sys.stdout, ensure_ascii=False)
