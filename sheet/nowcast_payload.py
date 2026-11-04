"""NOWCAST sheet (04.11.2026): the current quarter from Gosstat monthly indices, fading into the model equations.

1. Monthly indices as Gosstat prints them (% of the same month a year ago); an empty cell = not out yet,
   a month can be typed in by hand and the sheet picks it up.
2. Quarterly index, % y/y: mean of the months; months of the quarter not out yet = the last month (PPI: the
   last month of the quarter, as ANCHORS keeps it).
3. Bridges sector GVA y/y = a + b x index (OLS 2016-2025 without 2022) and the backtest with 1, 2, 3 months.
4. By sector: nowcast, model equation (annual growth + quarter correction of B1 section 8), level deviation
   (fades by rho a quarter), add-factor that B1_REAL section 3 adds to the quarter growth, result in B1.
5. Gosstat flash GDP as a top-down check (ВНИМАНИЕ above 1 pp).
6. PPI by quarter for ANCHORS row 11: fact of the quarter, then the B3 annual growth + deviation x rho.

Output: JSON {range: 2D list}; --coefs is accepted (scripts/recalc.py) and changes nothing.
"""
import json
import sys

import pandas as pd

from macromodel import nowcast as N
from sheet.nowcast_layout import (AF_ROW, B1_ANNUAL, B1_CORR, B1_ROW, B_HDR, B_ROW, COEF_ROW, F_HDR, F_ROW, FC, FIRST_FC,
                                  INDS, M_HDR, M_ROW, MCOL, MONTHS, N_HDR, N_ROW, P_HDR, P_ROW, Q_HDR, Q_ROW, QCOL,
                                  QUARTERS, SECTORS, col)

TODAY = "2026-11-04"
FLASH = {"2026Q3": -0.7}       # Gosstat flash estimate of real GDP, % y/y (published 2026-11)
YEAR_GAP = 5   # pp: annual equation vs fact + nowcast of the year so far
HOLD = {"B"}   # sectors that keep the last nowcast y/y until the ceasefire, then fade by rho
PEACE_FLAG_ROW = 53   # B2_DEMAND PEACE_Q: 1 from the ceasefire quarter of the active scenario (sheet/b2_payload.py FLAG)
SECTOR_NAME = {"A": "Сельское хозяйство", "B": "Добыча", "C": "Переработка", "D": "Энергетика", "F": "Строительство",
               "G": "Торговля", "H": "Транспорт"}
SRC = {"AGRO": "Госстат, индекс сельхозпродукции", "IND_B": "Госстат, индекс промпроизводства",
       "IND_C": "Госстат, индекс промпроизводства", "IND_D": "Госстат, индекс промпроизводства",
       "IND_BCD": "Госстат, индекс промпроизводства (проверка)", "CONSTR": "Госстат, индекс строительной продукции",
       "RETAIL": "Госстат, оборот розничной торговли", "FREIGHT": "Госстат, грузооборот (наш расчёт г/г)",
       "PPI": "Госстат, ИЦП промышленности"}

Q0 = pd.Period("2015Q1", freq="Q")
b1c = lambda q: col(7 + (pd.Period(q, freq="Q") - Q0).n)       # B1_REAL / ANCHORS: H = 2015Q1
q4 = lambda q: str(pd.Period(q, freq="Q") - 4)
qprev = lambda q: str(pd.Period(q, freq="Q") - 1)
E = lambda key: f"COEFS!$E${COEF_ROW[key]}"
num = lambda x: f"{x:.2f}".replace(".", ",").replace("-", "−")

br = N.bridges()
bt = N.backtest()
rho_ppi = N.ppi_rho()
mt = N.monthly_table(MONTHS[0], MONTHS[-1])

out = {}
# COEFS
coefs = []
for s in SECTORS:
    r = br[s]
    for v, val, note in (("a", r["a"], "константа моста"), ("b", r["b"], f"наклон моста к индексу {r['ind']}"),
                         ("rho", r["rho"], "затухание отклонения от уравнения за квартал: AR(1) роста г/г отрасли, "
                                           "пары кварталов без 2022, в пределах 0,3–0,9")):
        coefs.append([f"NC_{s}_{v}", "NOWCAST", f"GVA_{s}", v, round(val, 3), "", "", r["sample"] if v != "rho" else "2016–2025",
                      "МНК, квартальные г/г" if v != "rho" else "AR(1)", round(r["r2"], 2) if v != "rho" else "", TODAY,
                      f"Наукаст: {note}"])
coefs.append(["NC_PPI_rho", "NOWCAST", "PPI_YOY", "rho", round(rho_ppi, 3), "", "", "2016–2025", "AR(1)", "", TODAY,
              "Затухание отклонения ИЦП г/г от годового прогноза B3 за квартал: AR(1) ИЦП г/г (конец квартала), без 2022"])
out[f"COEFS!A{COEF_ROW[('A', 'a')]}:L{COEF_ROW[('PPI', 'rho')]}"] = coefs

# title
out["NOWCAST!A1:B2"] = [["NOWCAST — текущий квартал по месячным данным Госстата", ""],
                        ["Квартал без ВВП Госстата берёт отрасли из месячных индексов (мосты, раздел 3); отклонение от уравнения "
                         "модели затухает с ρ за квартал (раздел 4) и идёт в B1_REAL поправкой роста. Новые месяцы: команда "
                         "«обнови месячные» или вписать индекс вручную в раздел 1. Флеш-оценка ВВП — проверка сверху (раздел 5).", ""]]

# 1. monthly
last = len(MONTHS) + 3
sec1 = [["1. Месячные индексы, % к тому же месяцу прошлого года (как публикует Госстат; пустая клетка — месяц не вышел, "
         "можно вписать вручную)"],
        ["Код", "Показатель", "Источник"] + [m.replace("-", " · ") for m in MONTHS] + ["Последний месяц"]]
for n in INDS:
    r = M_ROW[n]
    vals = ["" if pd.isna(v) else round(float(v) + 100, 1) for v in mt.loc[n]]
    sec1.append([n, N.NAMES[n].replace(", % г/г", ""), SRC[n]] + vals +
                [f'=IFERROR(INDEX($D${M_HDR}:${col(last - 1)}${M_HDR};MAX(ARRAYFORMULA(($D{r}:${col(last - 1)}{r}<>"")*'
                 f'(COLUMN($D{r}:${col(last - 1)}{r})-3))));"")'])
out[f"NOWCAST!A{M_HDR - 1}:{col(last)}{M_HDR + len(INDS)}"] = sec1

# 2. quarterly
sec2 = [["2. Квартальный индекс, % г/г: среднее месяцев квартала; не вышедшие месяцы = последний вышедший "
         "(ИЦП — последний месяц квартала, как в ANCHORS)"], ["Код", "Показатель", ""] + QUARTERS]
for n in INDS:
    r, line = M_ROW[n], [n, N.NAMES[n], ""]
    # one formula for every quarter (copies right): the quarter's three months sit 3 columns apart in section 1
    m = lambda j: f"OFFSET($D{r};0;3*(COLUMN()-4)+{j})"
    for q in QUARTERS:
        if n == "PPI":
            line.append(f'=LET(mon_a;{m(0)};mon_b;{m(1)};mon_c;{m(2)};IF(mon_a="";"";IF(mon_c<>"";mon_c;IF(mon_b<>"";mon_b;mon_a))-100))')
        else:
            line.append(f'=LET(mon_a;{m(0)};mon_b;{m(1)};mon_c;{m(2)};IF(mon_a="";"";AVERAGE(mon_a;IF(mon_b="";mon_a;mon_b);IF(mon_c="";IF(mon_b="";mon_a;mon_b);mon_c))-100))')
    sec2.append(line)
out[f"NOWCAST!A{Q_HDR - 1}:{QCOL[QUARTERS[-1]]}{Q_HDR + len(INDS)}"] = sec2

# 3. bridges and backtest
sec3 = [["3. Мосты: рост ВДС отрасли, % г/г = a + b × квартальный индекс; бэктест — ошибка (RMSE, п.п.) при 1, 2, 3 вышедших "
         "месяцах против наивного прогноза (рост прошлого квартала)"],
        ["Код", "Отрасль", "Индекс", "a", "b", "R²", "n", "Период", "RMSE 1 мес.", "RMSE 2 мес.", "RMSE 3 мес.",
         "RMSE наивный", "ρ"]]
for s in SECTORS:
    r, t = br[s], bt.loc[s]
    sec3.append([f"GVA_{s}", SECTOR_NAME[s], N.NAMES[r["ind"]], f"={E((s, 'a'))}", f"={E((s, 'b'))}", round(r["r2"], 2), r["n"],
                 r["sample"], round(t["m1"], 1), round(t["m2"], 1), round(t["m3"], 1), round(t["naive"], 1), f"={E((s, 'rho'))}"])
sec3.append(["Как читать: уже 1 месяц квартала даёт ошибку меньше наивного прогноза во всех отраслях; 3 месяца — лучшее, что "
             "есть до ВВП Госстата. Слабые мосты: сельское хозяйство (месячный индекс почти не видит урожай до осени) и "
             "транспорт (т·км ж/д и авто не покрывают трубопроводы, склады, почту, пассажиров)."])
out[f"NOWCAST!A{B_HDR - 1}:M{B_HDR + len(SECTORS) + 1}"] = sec3

# 4. nowcast and fade
fc0 = QCOL[FC[0]]
sec4 = [["4. Наукаст и затухание: квартал с месячными данными растёт как наукаст; дальше отклонение роста от уравнения × ρ за квартал. "
         "Поправка идёт в B1_REAL раздел 3 (рост квартала = годовой рост + поправка квартала + поправка наукаста)"],
        ["Код", "Показатель", "Единицы"] + QUARTERS + ["Проверка года"]]
ytd_q = [q for q in QUARTERS if q[:4] == FIRST_FC[:4] and q <= FIRST_FC]
for s in SECTORS:
    R, ind = N_ROW[s], br[s]["ind"]
    nc = [f"NC_{s}", f"{SECTOR_NAME[s]}: наукаст по мосту", "% г/г"]
    eq = [f"EQ_{s}", f"{SECTOR_NAME[s]}: уравнение модели (год + поправка квартала)", "% г/г"]
    dv = [f"DEV_{s}", f"{SECTOR_NAME[s]}: доля отклонения, что ещё осталась (×ρ за квартал)", "доля"]
    af = [f"AF_{s}", f"{SECTOR_NAME[s]}: поправка наукаста в B1_REAL", "п.п. к росту г/г"]
    rs = [f"RES_{s}", f"{SECTOR_NAME[s]}: итог в B1_REAL", "% г/г"]
    for q in QUARTERS:
        c = QCOL[q]
        rs.append(f"=B1_REAL!{b1c(q)}{B1_ROW[s]}/B1_REAL!{b1c(q4(q))}{B1_ROW[s]}*100-100")
        if q < FIRST_FC:
            nc.append(""), eq.append(""), dv.append(""), af.append("")
            continue
        nc.append(f'=IF({c}{Q_ROW[ind]}="";"";{E((s, "a"))}+{E((s, "b"))}*{c}{Q_ROW[ind]})')
        corr = f"+B1_REAL!{b1c(q)}{B1_CORR[s]}" if s in B1_CORR else ""
        eq.append(f"=INDEX(B1_REAL!$E${B1_ANNUAL[s]}:$G${B1_ANNUAL[s]};MATCH(VALUE(LEFT({c}${N_HDR};4));B1_REAL!$E$18:$G$18;0)){corr}")
        # growth gap fades: the equation sets growth rates, the fact sets the level of the nowcast quarter
        nc_, af_ = f"{c}{R['NC']}", f"{c}{R['AF']}"
        if q == FIRST_FC:
            dv.append(f'=IF({nc_}<>"";1;0)')
            af.append(f'=IF({nc_}<>"";{nc_}-{c}{R["EQ"]};0)')
        elif s in HOLD:
            # while the war lasts (B2_DEMAND PEACE_Q = 0) the sector keeps the y/y of the last quarter with data, after the
            # ceasefire the gap to the equation fades by rho (Andrey 04.11.2026: mining mixes energy and non-energy
            # extraction, a split or a strike input is not worth it)
            p, war = QCOL[qprev(q)], f"B2_DEMAND!{b1c(q)}{PEACE_FLAG_ROW}=0"
            dv.append(f'=IF({nc_}<>"";1;IF({war};{p}{R["DEV"]};{p}{R["DEV"]}*{E((s, "rho"))}))')
            af.append(f'=IF({nc_}<>"";{nc_}-{c}{R["EQ"]};IF({war};{p}{R["EQ"]}+{p}{R["AF"]}-{c}{R["EQ"]};{p}{R["AF"]}*{E((s, "rho"))}))')
        else:
            p = QCOL[qprev(q)]
            dv.append(f'=IF({nc_}<>"";1;{p}{R["DEV"]}*{E((s, "rho"))})')
            af.append(f'=IF({nc_}<>"";{nc_}-{c}{R["EQ"]};{p}{R["AF"]}*{E((s, "rho"))})')
    ytd = (f"(SUM(B1_REAL!{b1c(ytd_q[0])}{B1_ROW[s]}:{b1c(ytd_q[-1])}{B1_ROW[s]})/"
           f"SUM(B1_REAL!{b1c(q4(ytd_q[0]))}{B1_ROW[s]}:{b1c(q4(ytd_q[-1]))}{B1_ROW[s]})*100-100)")
    eqy = f"B1_REAL!E{B1_ANNUAL[s]}"
    nc.append(f'=IF(ABS({ytd}-{eqy})>{YEAR_GAP};"ВНИМАНИЕ: уравнение {FIRST_FC[:4]} "&FIXED({eqy};1)&"%, факт и наукаст '
              f'{len(ytd_q) * 3} мес. "&FIXED({ytd};1)&"%: годовой драйвер расходится с данными";"OK: уравнение {FIRST_FC[:4]} '
              f'"&FIXED({eqy};1)&"%, факт и наукаст {len(ytd_q) * 3} мес. "&FIXED({ytd};1)&"%")')
    sec4 += [nc, eq, dv, af, rs, [""]]
sec4.pop()
out[f"NOWCAST!A{N_HDR - 1}:T{N_ROW[SECTORS[-1]]['RES']}"] = sec4

# 5. flash GDP
mdl = ["GDP_REAL_P", "ВВП модели (B1_REAL, по производству)", "% г/г"]
fl = ["GDP_FLASH", "Экспресс-оценка Госстата", "% г/г, ввод"]
df = ["GDP_DIFF", "Модель − экспресс-оценка", "п.п."]
fg = ["GDP_FLAG", "Проверка: разница не больше 1 п.п.", ""]
for q in QUARTERS:
    c = QCOL[q]
    mdl.append(f"=B1_REAL!{b1c(q)}47/B1_REAL!{b1c(q4(q))}47*100-100")
    fl.append(FLASH.get(q, ""))
    df.append(f'=IF({c}{F_ROW["FLASH"]}="";"";{c}{F_ROW["MODEL"]}-{c}{F_ROW["FLASH"]})')
    fg.append(f'=IF({c}{F_ROW["FLASH"]}="";"";IF(ABS({c}{F_ROW["DIFF"]})>1;"ВНИМАНИЕ";"OK"))')
out[f"NOWCAST!A{F_HDR - 1}:{QCOL[QUARTERS[-1]]}{F_ROW['FLAG']}"] = [
    ["5. Флеш-оценка ВВП Госстата — проверка сверху (в модель не идёт: отрасли собираются снизу)"],
    ["Код", "Показатель", "Единицы"] + QUARTERS, mdl, fl, df, fg]

# 6. PPI by quarter
fa = ["PPI_FACT", "ИЦП, факт (последний вышедший месяц квартала)", "% г/г"]
b3 = ["PPI_B3", "ИЦП, годовой прогноз B3_PRICES", "% г/г"]
us = ["PPI_YOY", "ИЦП в ANCHORS строка 11", "% г/г"]
for q in QUARTERS:
    c = QCOL[q]
    fa.append(f"={c}{Q_ROW['PPI']}")
    if q < FIRST_FC:
        b3.append(""), us.append(f"=ANCHORS!{b1c(q)}11")
        continue
    b3.append(f"=INDEX(B3_PRICES!$E$21:$G$21;MATCH(VALUE(LEFT({c}${P_HDR};4));B3_PRICES!$E$10:$G$10;0))")
    p = QCOL[qprev(q)]
    base = f"{p}{P_ROW['USED']}" if q == FIRST_FC else f"({p}{P_ROW['USED']}-{p}{P_ROW['B3']})"
    dev = f"({base}-{c}{P_ROW['B3']})" if q == FIRST_FC else base
    us.append(f'=IF({c}{P_ROW["FACT"]}<>"";{c}{P_ROW["FACT"]};{c}{P_ROW["B3"]}+{dev}*{E(("PPI", "rho"))})')
out[f"NOWCAST!A{P_HDR - 1}:{QCOL[QUARTERS[-1]]}{P_ROW['USED']}"] = [
    ["6. ИЦП по кварталам: факт квартала, дальше годовой прогноз B3 + отклонение × ρ за квартал"],
    ["Код", "Показатель", "Единицы"] + QUARTERS, fa, b3, us]
out[f"ANCHORS!{b1c(FC[0])}11:{b1c(FC[-1])}11"] = [[f"=NOWCAST!{QCOL[q]}{P_ROW['USED']}" for q in FC]]

if __name__ == "__main__":
    json.dump(out, sys.stdout, ensure_ascii=False)
