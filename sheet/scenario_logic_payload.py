"""Logic checks of the scenario inputs and boundary values (bottom of SCENARIOS, 2026-10-25).

Andrey asked for checks inside SCENARIOS so that scenarios do not contradict each other or the data,
and for boundary values (total port capacity, total generation and similar). Three kinds of checks:
limits (a scenario value above a physical boundary), ordering (pessimistic <= base <= optimistic for
2027-2028, reversed for "bad" parameters) and consistency with the ceasefire quarter (row 16) and the
2026 facts. Every rule gives OK or ВНИМАНИЕ with the years and values that break it.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys

from macromodel import scenario_layout as SL

FIRST = SL.LIMITS
Y = SL.Y
SCEN = {"База": "CDE", "Пессимистичный": "FGH", "Оптимистичный": "IJK"}
YEARS = {"База": "C$15:E$15", "Пессимистичный": "F$15:H$15", "Оптимистичный": "I$15:K$15"}

# boundary values: code, name, unit, value, source
LIMITS = [
    ("LIM_PORTS", "Предельная пропускная способность всех морских портов", "млн т в год", 160,
     "Рекорд 2019 года — 160 млн т (USPA), все порты до 2022 года. Выше не было никогда"),
    ("LIM_PORTS_WAR", "Порты во время войны: Одесский кластер и Дунай", "млн т в год", 110,
     "Оценка Claude: без портов Николаева, Херсона и оккупированных; рекорд коридора около 9–10 млн т в месяц"),
    ("LIM_CAP", "Предельная доступная мощность энергосистемы в пик", "ГВт", 24,
     "Пиковое потребление до войны — около 24 ГВт (2021); выработка 2021 — около 156 ТВт·ч (по памяти). ЗАЭС (6 ГВт) недоступна"),
    ("LIM_CAP_G", "Предельный прирост мощности за год", "ГВт в год", 3,
     "Оценка Claude: ремонт блоков ТЭС/ГЭС, распределённая генерация и импорт добавляли 2–3 ГВт в год (2024–2025)"),
    ("LIM_MET", "Предельная загрузка металлургии", "% от уровня 2025", 150,
     "Оценка Claude: работающие комбинаты (Запорожсталь, АМКР, Каметсталь) на полной загрузке; Мариуполь потерян"),
    ("LIM_HARV", "Предельный урожай шести культур на подконтрольной территории", "млн т", 91,
     "Оценка Claude: средняя площадь 2023–2026 × рекордная урожайность 2021 (+15% к среднему). Рекорд 2021 со всей территорией — 106,5"),
    ("LIM_DEF", "Предельные расходы на оборону", "% ВВП", 40,
     "Максимум войны — около 37% ВВП (2023–2024, Казначейство); выше — только при монетизации"),
    ("LIM_MIL", "Предельная численность военных", "тыс. человек", 1200,
     "Оценка Claude: демография и бюджет; сейчас около 1 млн (общепринятая оценка)"),
    ("FACT_PORTS", "Порты 2026: факт 1 полугодия × 2", "млн т в год", 84.8,
     "42,4 млн т за 1 полугодие 2026 (GMK Center, 16.07.2026). Сценарий 2026 должен быть в пределах ±15%"),
    ("FACT_DEF", "Оборона 2026: факт 1 полугодия", "% ВВП", 35.7,
     "Казначейство, функция 0200, 1 пол. 2026. Сценарий 2026 должен быть в пределах ±5 п.п."),
]
L = {code: FIRST + 3 + i for i, (code, *_) in enumerate(LIMITS)}
lim = lambda code: f"$D${L[code]}"

# parameters checked for ordering: row, name, +1 if higher is better for the economy, -1 if worse
ORDER = [(Y["CAP"], "Мощность энергосистемы", 1), (Y["PORTS"], "Порты", 1), (Y["FIN"], "Внешнее финансирование бюджета", 1),
         (Y["DEF"], "Расходы на оборону", -1), (Y["MIGR"], "Чистая миграция (возврат +, отъезд −)", 1),
         (Y["MOB"], "Мобилизация", -1), (Y["EA_GDP"], "Рост ВВП еврозоны", 1), (Y["GUEST"], "Приток иностранных рабочих", 1),
         (SL.MET_Y, "Загрузка металлургии", 1), (SL.PEACE_C, "Эффект мира: потребление", 1),
         (SL.PEACE_I, "Эффект мира: восстановление", 1), (SL.RECON, "Деньги на восстановление", 1),
         (SL.WEATHER, "Погода для урожая", 1), (SL.AREA, "Посевная площадь", 1)]


def over(row, cols, years, limit, label=""):
    """Years where the scenario value is above the limit."""
    r = f"{cols[0]}{row}:{cols[2]}{row}"
    return (f"=ARRAYFORMULA(IF(MAX({r})<={limit};\"OK\";\"ВНИМАНИЕ: {label}\"&TEXTJOIN(\", \";TRUE;"
            f"IF({r}>{limit};{years}&\": \"&{r};\"\"))))")


def ceasefire(cols):
    """Year of the ceasefire in this scenario (row 16), 9999 if none."""
    r = f"{cols[0]}$16:{cols[2]}$16"
    return f"IFERROR(VALUE(LEFT(INDEX(FILTER({r};{r}<>\"нет\";{r}<>\"\");1);4));9999)"


checks = []
# 1. limits, per scenario
for code, row, label in [("LIM_PORTS", Y["PORTS"], ""), ("LIM_CAP", Y["CAP"], ""), ("LIM_MET", SL.MET_Y, ""), ("LIM_DEF", Y["DEF"], "")]:
    name = next(n for c, n, *_ in LIMITS if c == code)
    checks.append([code.replace("LIM_", "L_"), f"Не выше предела: {name[0].lower() + name[1:]}", f"строка {row} ≤ D{L[code]}"] +
                  [over(row, SCEN[s], YEARS[s], lim(code)) for s in SCEN])
P, CP, D = Y["PORTS"], Y["CAP"], Y["DEF"]
# ports during the war (years before the ceasefire year)
checks.append(["L_PORTS_WAR", "Порты до прекращения огня не выше Одесского кластера и Дуная", f"строка {P} ≤ D{L['LIM_PORTS_WAR']} до года строки 16"] +
              [f"=ARRAYFORMULA(IF(SUM(({YEARS[s]}<{ceasefire(c)})*({c[0]}{P}:{c[2]}{P}>{lim('LIM_PORTS_WAR')}))=0;\"OK\";"
               f"\"ВНИМАНИЕ: порты выше \"&{lim('LIM_PORTS_WAR')}&\" млн т во время войны\"))" for s, c in SCEN.items()])
# energy capacity growth per year, from 15 GW in 2025
checks.append(["L_CAP_G", "Мощность энергосистемы растёт не быстрее предела", f"прирост за год ≤ D{L['LIM_CAP_G']} ГВт (2025 — 15 ГВт)"] +
              [f"=ARRAYFORMULA(IF(MAX({c[0]}{CP}-15;{c[1]}{CP}-{c[0]}{CP};{c[2]}{CP}-{c[1]}{CP})<={lim('LIM_CAP_G')};\"OK\";"
               f"\"ВНИМАНИЕ: прирост \"&TEXTJOIN(\", \";TRUE;IF({{{c[0]}{CP}-15\\{c[1]}{CP}-{c[0]}{CP}\\{c[2]}{CP}-{c[1]}{CP}}}>{lim('LIM_CAP_G')};"
               f"{YEARS[s]}&\": +\"&{{{c[0]}{CP}-15\\{c[1]}{CP}-{c[0]}{CP}\\{c[2]}{CP}-{c[1]}{CP}}}&\" ГВт\";\"\"))))" for s, c in SCEN.items()])
# harvest implied by area and weather (SL.WEATHER, SL.AREA) against the boundary
A, W = SL.AREA, SL.WEATHER
checks.append(["L_HARV", "Урожай не выше предела подконтрольной территории",
               f"средний 2023–2026 (B10_AGRO I25) × площадь × погода ≤ D{L['LIM_HARV']}"] +
              [f"=ARRAYFORMULA(IF(MAX(B10_AGRO!$I$25*(1+{c[1]}{A}:{c[2]}{A}/100)*(1+{c[1]}{W}:{c[2]}{W}/100))<={lim('LIM_HARV')};\"OK\";"
               f"\"ВНИМАНИЕ: урожай до \"&ROUND(MAX(B10_AGRO!$I$25*(1+{c[1]}{A}:{c[2]}{A}/100)*(1+{c[1]}{W}:{c[2]}{W}/100));1)&\" млн т\"))"
               for s, c in SCEN.items()])
# military headcount, quarterly labour rows (C:L), Base / Pess / Opt
MIL = [SL.LAB["MILN"] + k for k in range(3)]  # military headcount by scenario, B4_LABOUR block
checks.append(["L_MIL", "Численность военных не выше предела", f"строки {MIL[0]}–{MIL[2]} ≤ D{L['LIM_MIL']}"] +
              [f"=IF(MAX(C{r}:L{r})<={lim('LIM_MIL')};\"OK\";\"ВНИМАНИЕ: до \"&MAX(C{r}:L{r})&\" тыс.\")" for r in MIL])
# indices and shares within 0..1
M, G = Y["SH_MIGR"], Y["SH_GUEST"]
checks.append(["L_SHARE", "Доли от 0 до 1", f"строки {M}, {G}"] +
              [f"=IF(AND(MIN({c[0]}{M}:{c[2]}{G})>=0;MAX({c[0]}{M}:{c[2]}{G})<=1);\"OK\";"
               f"\"ВНИМАНИЕ: значение вне 0–1\")" for s, c in SCEN.items()])
# 2. 2026 against the facts of the first half
checks.append(["F_PORTS", "Порты 2026 согласованы с фактом 1 полугодия", f"|строка {P} (2026) / D{L['FACT_PORTS']} − 1| ≤ 15%"] +
              [f"=IF(ABS({c[0]}{P}/{lim('FACT_PORTS')}-1)<=0,15;\"OK\";\"ВНИМАНИЕ: \"&{c[0]}{P}&\" при факте \"&{lim('FACT_PORTS')})"
               for s, c in SCEN.items()])
checks.append(["F_DEF", "Оборона 2026 согласована с фактом 1 полугодия", f"|строка {D} (2026) − D{L['FACT_DEF']}| ≤ 5 п.п."] +
              [f"=IF(ABS({c[0]}{D}-{lim('FACT_DEF')})<=5;\"OK\";\"ВНИМАНИЕ: \"&{c[0]}{D}&\"% при факте \"&{lim('FACT_DEF')}&\"%\")"
               for s, c in SCEN.items()])
# 3. consistency with the ceasefire quarter (row 16)
PC, PI = SL.PEACE_C, SL.PEACE_I
checks.append(["C_PEACE", "Эффект мира не раньше прекращения огня", f"строки {SL.PEACE_C}–{SL.PEACE_I} = 0 в годы до года строки 16"] +
              [f"=ARRAYFORMULA(IF(SUM(({YEARS[s]}<{ceasefire(c)})*(ABS({c[0]}{PC}:{c[2]}{PC})+ABS({c[0]}{PI}:{c[2]}{PI})))=0;\"OK\";"
               f"\"ВНИМАНИЕ: эффект мира в \"&TEXTJOIN(\", \";TRUE;IF(({YEARS[s]}<{ceasefire(c)})*(ABS({c[0]}{PC}:{c[2]}{PC})+ABS({c[0]}{PI}:{c[2]}{PI}))>0;"
               f"{YEARS[s]};\"\"))&\" до прекращения огня\"))" for s, c in SCEN.items()])
checks.append(["C_DEF", "После прекращения огня оборона не растёт", f"строка {D} в год после года строки 16 ≤ значения года прекращения"] +
              [f"=ARRAYFORMULA(IF(SUM(({c[1]}$15:{c[2]}$15>{ceasefire(c)})*({c[1]}{D}:{c[2]}{D}>{c[0]}{D}:{c[1]}{D}))=0;\"OK\";"
               f"\"ВНИМАНИЕ: оборона растёт после прекращения огня\"))" for s, c in SCEN.items()])
checks.append(["C_MIL", "Без прекращения огня нет демобилизации", f"численность военных (строки {MIL[0]}–{MIL[2]}) падает только при мире"] +
              [f"=ARRAYFORMULA(IF(OR({ceasefire(c)}<9999;MIN(D{r}:L{r}-C{r}:K{r})>=0);\"OK\";"
               f"\"ВНИМАНИЕ: численность падает без прекращения огня\"))" for (s, c), r in zip(SCEN.items(), MIL)])

# 4. ordering pessimistic <= base <= optimistic, 2027-2028
order = []
for row, name, sign in ORDER:
    b, p, o = f"D{row}:E{row}", f"G{row}:H{row}", f"J{row}:K{row}"
    lo, hi = (p, o) if sign > 0 else (o, p)
    rule = "пессимистичный ≤ база ≤ оптимистичный" if sign > 0 else "оптимистичный ≤ база ≤ пессимистичный"
    order.append([f"O_{row}", f"Порядок сценариев: {name[0].lower() + name[1:]}", f"строка {row}, 2027–2028: {rule}",
                  f"=ARRAYFORMULA(IF(SUM(({lo}>{b})+({b}>{hi}))=0;\"OK\";\"ВНИМАНИЕ: \"&TEXTJOIN(\", \";TRUE;IF(({lo}>{b})+({b}>{hi});"
                  f"D$15:E$15&\": пес. \"&{p}&\", база \"&{b}&\", опт. \"&{o};\"\"))))", "", ""])

head = FIRST + 3 + len(LIMITS) + 1  # blank row after the limits table
CHK_FIRST = head + 2
n = len(checks) + len(order)
rows = [
    ["Предельные величины и проверка логики сценариев"],
    ["Пределы — физические границы, выше которых сценарий невозможен. Проверки ниже сравнивают с ними все три сценария, "
     "порядок сценариев и согласованность с прекращением огня (строка 16) и фактом 2026 года."],
    ["Код", "Предел", "Единицы", "Значение", "Источник"],
] + [[c, n_, u, v, src] for c, n_, u, v, src in LIMITS] + [
    [""],
    ["Проверка логики сценариев", "", "Замечаний:",
     f"=COUNTIF(D{CHK_FIRST}:F{CHK_FIRST + n - 1};\"ВНИМАНИЕ*\")"],
    ["Код", "Проверка", "Правило", "База", "Пессимистичный", "Оптимистичный"],
] + checks + order + [
    [""],
    ["Как читать: ВНИМАНИЕ не запрещает сценарий, а показывает противоречие. Если оно сознательное (например, после мира "
     "мужчины уезжают за границу), объясните его в столбце O строки параметра; если нет — исправьте значение. "
     "Порядок сценариев проверяется для 2027–2028: 2026 у всех сценариев почти факт."],
]
out = {f"SCENARIOS!A{FIRST}:F{FIRST + len(rows) - 1}": rows}
json.dump(out, sys.stdout, ensure_ascii=False)
