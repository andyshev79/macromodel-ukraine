"""B8_CAPACITY section 3: recovery after the ceasefire, slowed by long downtime and by destroyed capacity (2026-10-29).

Andrey: a long stop costs markets, so the longer an industry stood the slower it comes back; a physically destroyed
large plant (Zaporizhstal, the Kremenchuk refinery, chemical plants) needs years to rebuild. Exports come back through
agro and ore, not metals.

For metallurgy and ports the SCENARIOS quarterly path is now the upper bound (what the scenario allows). After the
ceasefire the model takes the lowest of three:
- the scenario path;
- markets: from the war level W to the target in T quarters, T = T0 + H × quarters stood (below half the
  first-half-2026 level, up to the first peaceful quarter);
- destruction: full capacity × (1 − destroyed share × part not yet rebuilt); rebuilding starts R0 quarters after
  the ceasefire and takes R1 quarters.
Refining and chemicals have no downtime path: their level is 100 − destroyed share from the quarter of destruction,
rebuilt the same way; they move the "other manufacturing" block of B1 (COEFS REC_CHEM_SH).
Ore: domestic mills take less, but after the ceasefire part of the idle mills' ore is exported as the ports open.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys

from macromodel import scenario_layout as SL
from sheet.recovery_layout import ACT, ACT0, HDR, IND, LAST, QN, R0, chem_row, ind_row, sc_row
from sheet.scenarios_quarterly_payload import QCOLS, QLAB, ROW as SQ_ROW

COEF0 = 241
COEFS = [  # code, value, unit, note
    ("REC_MET_T0", 2, "кварталов", "Металлургия: срок выхода на целевой уровень без простоя (запуск печей, логистика). Оценка Claude"),
    ("REC_MET_H", 1, "квартала за квартал простоя", "Металлургия: каждый квартал простоя добавляет квартал к восстановлению — покупатели "
     "ушли к Турции и Индии, контракты и квоты ЕС надо возвращать. Оценка Claude"),
    ("REC_PORTS_T0", 2, "кварталов", "Порты: разминирование, страховка, возврат линий. Оценка Claude; в 2023–2024 коридор вышел на "
     "довоенный объём за 3–4 квартала"),
    ("REC_PORTS_H", 0.25, "квартала за квартал простоя", "Порты теряют рынки меньше: грузы те же, меняется только маршрут. Оценка Claude"),
    ("REC_STOP_SH", 0.5, "доля уровня 1 пол. 2026", "Квартал считается простоем, если уровень ниже этой доли от 1 пол. 2026"),
    ("REC_R0", 4, "кварталов после прекращения огня", "Начало отстройки разрушенного: оценка ущерба, деньги, проект. Оценка Claude"),
    ("REC_R1", 8, "кварталов", "Строительство крупного завода (доменная печь, НПЗ, азотный комплекс) — около двух лет. Оценка Claude"),
    ("REC_PORTS_FULL", 160, "млн т в год", "Довоенная пропускная способность морских портов (2021)"),
    ("REC_ORE_X", 0.6, "доля", "Часть руды, которую не берут свои заводы, уходящая на экспорт при открытых портах. Оценка Claude"),
    ("REC_ORE_XEXP", 0.03, "п.п. экспорта на пункт", "Руда своих заводов в экспорте: ~20 млн т × ~75 USD/т ≈ 3% экспорта 2025 на 100 пунктов. Оценка Claude"),
    ("REC_CHEM_SH", 0.2, "доля", "Химия и НПЗ (КВЭД 19–20) в блоке «другое» переработки B1. Оценка Claude по структуре 2024"),
]
CR = {c[0]: COEF0 + i for i, c in enumerate(COEFS)}
K = lambda code: f"COEFS!$E${CR[code]}"
SC_ROW0 = SL.DESTROYED  # SCENARIOS: destroyed capacity
SROW = {"MET": SC_ROW0 + 2, "PORTS": SC_ROW0 + 3, "CHEM": SC_ROW0 + 4, "CHEM_Q": SC_ROW0 + 5}
SC_NAMES = ("База", "Пессимистичный", "Оптимистичный")
CF_COLS = ("C$16:$E$16", "F$16:$H$16", "I$16:$K$16")
QC = list(QCOLS)  # D..M
ALLC = ["C"] + QC
num = lambda x: str(x).replace(".", ",")
FULL = {"MET": "100", "PORTS": K("REC_PORTS_FULL")}
unbuilt = lambda c, k: f"MIN(1;MAX(0;({K('REC_R0')}+{K('REC_R1')}-{c}{k})/{K('REC_R1')}))"
choose = lambda c, rows: f"=CHOOSE(MATCH(SCENARIOS!$C$3;SCENARIOS!$A$8:$A$10;0);{c}{rows[0]};{c}{rows[1]};{c}{rows[2]})"
avg = lambda r: [f"=(2*C{r}+D{r}+E{r})/4", f"=AVERAGE(F{r}:I{r})", f"=AVERAGE(J{r}:M{r})"]


def scenario_block(s: int) -> dict:
    out = {}
    k = sc_row(s)
    cf = f"IFERROR(INDEX(SCENARIOS!${CF_COLS[s]};MATCH(\"2*\";SCENARIOS!${CF_COLS[s]};0));\"нет\")"
    out[k] = [f"K_{s}", f"Кварталов после прекращения огня — {SC_NAMES[s]}",
              f"=IFERROR(VALUE(LEFT({cf};4))*4+VALUE(RIGHT({cf};1));\"\")"] + \
             [f"=IF($C{k}=\"\";0;MAX(0;{c}${QN}-$C{k}+1))" for c in QC]
    for ind in IND:
        r = {p: ind_row(s, ind, p) for p in ("PAR", "IN", "BOUND", "CEIL", "EFF", "BIND")}
        name = {"MET": "Металлургия", "PORTS": "Порты"}[ind]
        t0, h = K(f"REC_{ind}_T0"), K(f"REC_{ind}_H")
        first = f"MATCH(1;$D{k}:$M{k};0)"
        out[r["PAR"]] = [f"{ind}_PAR_{s}", f"{name}: кварталов простоя | срок восстановления, кв. | уровень войны | цель | разрушено, %",
                         f"=COUNTIFS($D{r['IN']}:$M{r['IN']};\"<\"&{K('REC_STOP_SH')}*$C{r['IN']};$D{k}:$M{k};\"<=1\")",
                         f"={t0}+{h}*C{r['PAR']}",
                         f"=MIN(IFERROR(INDEX($C{r['IN']}:$M{r['IN']};{first});$C{r['IN']});IFERROR(INDEX($D{r['IN']}:$M{r['IN']};{first});$C{r['IN']}))",
                         f"=MAXIFS($D{r['IN']}:$M{r['IN']};$D{k}:$M{k};\">0\")",
                         f"=SCENARIOS!${'CDE'[s]}${SROW[ind]}"]
        out[r["IN"]] = [f"{ind}_IN_{s}", f"{name}: путь сценария (верхняя граница)"] + \
                       [f"=SCENARIOS!{c}{SQ_ROW[ind] + s}" for c in ALLC]
        out[r["BOUND"]] = [f"{ind}_BOUND_{s}", f"{name}: предел по разрушениям", ""] + \
                          [f"={FULL[ind]}*(1-$G{r['PAR']}/100*{unbuilt(c, k)})" for c in QC]
        out[r["CEIL"]] = [f"{ind}_CEIL_{s}", f"{name}: предел по рынкам (возврат от уровня войны к цели)", ""] + \
                         [f"=IF({c}{k}=0;\"\";$E{r['PAR']}+($F{r['PAR']}-$E{r['PAR']})*MIN(1;{c}{k}/$D{r['PAR']}))" for c in QC]
        out[r["EFF"]] = [f"{ind}_EFF_{s}", f"{name}: в модели (наименьшее из трёх после прекращения огня)", f"=C{r['IN']}"] + \
                        [f"=IF({c}{k}=0;{c}{r['IN']};MIN({c}{r['IN']};{c}{r['CEIL']};{c}{r['BOUND']}))" for c in QC]
        out[r["BIND"]] = [f"{ind}_BIND_{s}", f"{name}: что ограничивает", ""] + \
                         [f"=IF({c}{k}=0;\"война\";IF({c}{r['EFF']}>={c}{r['IN']}-0,05;\"сценарий\";"
                          f"IF({c}{r['EFF']}>={c}{r['BOUND']}-0,05;\"разрушения\";\"рынки\")))" for c in QC]
    ch = chem_row(s)
    out[ch] = [f"CHEM_EFF_{s}", "Химия и НПЗ: доступная мощность, % от 2025", 100] + \
              [f"=IF({c}${HDR}<SCENARIOS!${'CDE'[s]}${SROW['CHEM_Q']};100;100-SCENARIOS!${'CDE'[s]}${SROW['CHEM']}"
               f"*IF({c}{k}=0;1;{unbuilt(c, k)}))" for c in QC]
    return out


def build() -> dict:
    out = {}
    rows = {R0: ["3. Восстановление после простоя и разрушений, по кварталам"],
            R0 + 1: [f"Как читать: путь SCENARIOS (строки {SQ_ROW['PORTS']}–{SQ_ROW['PORTS'] + 3} порты, {SQ_ROW['MET']}–{SQ_ROW['MET'] + 3} металлургия, из индекса к прошлому кварталу) — верхняя граница. После прекращения "
                     "огня в модель идёт наименьшее из трёх: путь сценария; возврат рынков — от уровня войны к цели за T кварталов, "
                     "T растёт с длиной простоя (COEFS REC_); отстройка разрушенного — начинается через R0 кварталов и идёт R1 "
                     f"кварталов (SCENARIOS строки {SROW['MET']}–{SROW['CHEM_Q']}). Руда: после прекращения огня часть руды, которую не берут свои заводы, "
                     "уходит на экспорт через порты."],
            HDR: ["Код", "Показатель", "1 пол. 2026"] + QLAB + [2025, 2026, 2027, 2028, "Комментарий"],
            QN: ["QN", "Номер квартала (год × 4 + квартал)", ""] + [f"=VALUE(LEFT({c}${HDR};4))*4+VALUE(RIGHT({c}${HDR};1))" for c in QC]}
    for s in range(3):
        rows |= scenario_block(s)
    a = ACT
    act = lambda code, src: [code, src, choose("C", [ind_row(s, code, "EFF") for s in range(3)])] + \
                            [choose(c, [ind_row(s, code, "EFF") for s in range(3)]) for c in QC]
    rows[ACT0] = ["Активный сценарий (SCENARIOS C3)"]
    rows[a["K"]] = ["K", "Кварталов после прекращения огня", ""] + [choose(c, [sc_row(s) for s in range(3)]) for c in QC]
    rows[a["MET"]] = act("MET", "Металлургия: загрузка, % от 2025") + [100] + avg(a["MET"]) + [f"идёт в SCENARIOS строки {SL.MET_Y} и {SQ_ROW['MET'] + 3}"]
    rows[a["PORTS"]] = act("PORTS", "Порты: млн т в год") + ["=B1_REAL!$D$12"] + avg(a["PORTS"]) + [f"идёт в SCENARIOS строки {SL.Y["PORTS"]} и {SQ_ROW['PORTS'] + 3}"]
    rows[a["CHEM"]] = ["CHEM", "Химия и НПЗ: доступная мощность, % от 2025", choose("C", [chem_row(s) for s in range(3)])] + \
                      [choose(c, [chem_row(s) for s in range(3)]) for c in QC] + [100] + avg(a["CHEM"]) + \
                      ["идёт в B1_REAL: «другое» в переработке"]
    rows[a["ORE"]] = ["ORE", "Спрос на руду: свои заводы + экспорт после прекращения огня, % от 2025", f"=C{a['MET']}"] + \
                     [f"={c}{a['MET']}+IF({c}{a['K']}=0;0;(100-{c}{a['MET']})*{K('REC_ORE_X')}*MIN(1;{c}{a['PORTS']}/$N{a['PORTS']}))"
                      for c in QC] + [100] + avg(a["ORE"]) + ["идёт в B1_REAL: добыча"]
    prev4 = {c: ("100" if i < 2 else f"$C{a['ORE']}" if i < 4 else f"{QC[i - 4]}{a['ORE']}") for i, c in enumerate(QC)}
    rows[a["ORE_D"]] = ["ORE_D", "Руда: изменение квартала г/г, пунктов", ""] + [f"={c}{a['ORE']}-{prev4[c]}" for c in QC]
    ycol = {c: ("O", "N") if i < 2 else ("P", "O") if i < 6 else ("Q", "P") for i, c in enumerate(QC)}
    rows[a["ORE_DY"]] = ["ORE_DY", "Руда: изменение среднего за год, пунктов", ""] + \
                        [f"=${ycol[c][0]}{a['ORE']}-${ycol[c][1]}{a['ORE']}" for c in QC]
    rows[a["ORE_XTRA"]] = ["ORE_XTRA", "Руда на экспорт сверх своих заводов, пунктов (руда − металлургия)", ""] + [""] * 10 + \
                          [f"={c}{a['ORE']}-{c}{a['MET']}" for c in "NOPQ"] + ["идёт в B2_DEMAND: экспорт"]
    rows[LAST] = ["Металлургия и руда расходятся после прекращения огня: заводы возвращаются медленно, руда идёт на экспорт, "
                  "как только открываются порты (Андрей, 29.10)."]
    for r in range(R0, LAST + 1):
        line = rows.get(r, [""])
        out[f"B8_CAPACITY!A{r}:R{r}"] = [line + [""] * (18 - len(line))]
    out[f"COEFS!A{COEF0}:L{COEF0 + len(COEFS) - 1}"] = [
        [c, "B8", "REC", c[4:], v, "", "", "2026", "оценка", "", "2026-10-29", f"{n} ({u})"] for c, v, u, n in COEFS]
    out[f"SCENARIOS!A{SC_ROW0}:G{SC_ROW0 + 5}"] = [
        ["Разрушенные мощности: что придётся отстраивать (B8_CAPACITY раздел 3)", "", "", "", "", "", ""],
        ["Параметр", "Единицы", "База", "Пессимистичный", "Оптимистичный", "Активный", "Комментарий"],
        ["Металлургия: разрушено", "% мощности 2025", 30, 45, 20, choose_sc(SROW["MET"]),
         "Оценка Claude: Запорожсталь и другие заводы под ударами; уточнить у Андрея"],
        ["Порты: разрушено", "% довоенной мощности", 0, 0, 0, choose_sc(SROW["PORTS"]),
         "Причалы чинят за месяцы; порты ограничивает доступ к морю, не разрушения"],
        ["Химия и НПЗ: разрушено", "% мощности 2025", 0, 0, 0, choose_sc(SROW["CHEM"]),
         "Кременчугский НПЗ, азотные заводы: ждёт данных Андрея (какие объекты и с какого квартала)"],
        ["Химия и НПЗ: разрушено с квартала", "ГГГГQн", "2026Q3", "2026Q3", "2026Q3", choose_sc(SROW["CHEM_Q"]), ""],
    ]
    return out


def choose_sc(r: int) -> str:
    return f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);C{r};D{r};E{r})"


if __name__ == "__main__":
    json.dump(build(), sys.stdout, ensure_ascii=False)
