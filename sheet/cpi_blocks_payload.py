"""Build the quarterly CPI-by-blocks section of B3_PRICES (rows 30-51), its COEFS rows, the Brent
row in SCENARIOS and the ANCHORS CPI link (macromodel.blocks.cpi_blocks).

Quarter columns D:O of B3 are 2026Q1..2028Q4 (ANCHORS AZ:BK). 2026Q1-Q2 are facts from the
history, 2026Q3 from the NBU press release for September (until the quarterly file has it).
Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). --coefs: COEFS rows only.
"""
import json
import sys

from macromodel import scenario_layout as SL
from macromodel.blocks import cpi_blocks as B
from macromodel.blocks.shocks import FUEL_QOQ, SHOCK_ROW, TARIFF_ROW

QUARTERS = [f"{y}Q{q}" for y in (2026, 2027, 2028) for q in (1, 2, 3, 4)]
COLS = "DEFGHIJKLMNO"
FACT = 3  # 2026Q1, Q2, Q3 are facts
ANCH = ["AZ", "BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK"]
ANCH4 = ["AV", "AW", "AX", "AY"] + ANCH[:8]  # same quarter last year
SCQ = {c: s for c, s in zip(COLS[2:], "CDEFGHIJKL")}  # SCENARIOS quarter columns (2026Q3..2028Q4)
YEAR_COL = {"2026": "E", "2027": "F", "2028": "G"}  # B3 annual columns
SC_YEAR = {"2026": "L", "2027": "M", "2028": "N"}  # SCENARIOS active annual columns
PRESS_2026Q3 = {"CORE": 8.8, "RAW": 6.7, "ADM": 13.6, "FUEL": 46.2}  # NBU, September 2026 y/y
BRENT_2025 = [75.8, 68.0, 69.0, 63.6]
from sheet.scenarios_quarterly_payload import ROW as QROW  # main quarterly block of SCENARIOS (D:M = 2026Q3..2028Q4)
BRENT_Y = SL.BRENT  # Brent: one value a year in the annual table, active columns L:N (quarterly rows removed 2026-11-03)
MAIN_Q = {c: s for c, s in zip(COLS[2:], "DEFGHIJKLM")}

# section 6: fuel input q/q (SCENARIOS, one row) -> y/y of the fuel block (row 45); moved here from SCENARIOS 2026-10-29
FU = {"HEAD": 54, "IN": 56, "LAG": 57, "YY": 58, "QQ": 59}
# section 7: tariffs rise only after martial law is lifted (rule of 2026-10-30): hikes entered for earlier quarters
# are deferred to the first quarter without martial law; martial law is assumed lifted the quarter after the ceasefire.
# From then on the backlog rises gradually, at most TARIFF_MAX % a year in equal quarterly steps (Andrey, 30.10)
TA = {"HEAD": 61, "END": 63, "IN": 64, "MAX": 65, "BACK": 66, "EFF": 67}
TARIFF_MAX = 25  # % a year: middle of the 20-30% a year NBU-style path; NBU admin prices 11-14% y/y in 2026-2028
CEASE = "IFERROR(INDEX(SCENARIOS!$L$16:$N$16;MATCH(\"2*\";SCENARIOS!$L$16:$N$16;0));\"нет\")"

rows_c = B.coef_rows()
CROW = {(r["eq"], r["var"]): B.COEF_FIRST + i for i, r in enumerate(rows_c)}
C = lambda k, v: f"COEFS!$E${CROW[(f'CPIB_{k}', v)]}"
num = lambda v: f"{v:.2f}".replace(".", ",").replace("-", "−")
kv = lambda k, v: num(next(r["coef"] for r in rows_c if (r["eq"], r["var"]) == (f"CPIB_{k}", v)))

out = {}
coefs = []
for r in rows_c:
    v = r["coef"]
    if r["var"] == "TARIFF":
        v = f"=COEFS!$E${SHOCK_ROW['TARIFF_W']}/{C('W', 'ADM')}"
    coefs.append([f"{r['eq']}_{r['var']}", "B3", r["eq"], r["var"], v if isinstance(v, str) else round(v, 3),
                  "" if r["se"] is None else round(r["se"], 3), "" if r["se"] is None else round(r["coef"] / r["se"], 1),
                  r["period"], r["method"], "" if r["r2"] is None else round(r["r2"], 2), "2026-10-24", r["note"]])
out[f"COEFS!A{B.COEF_FIRST}:L{B.COEF_FIRST + len(coefs) - 1}"] = coefs

x = B.data()
fact = lambda code, i: round(float(x.loc[QUARTERS[i], code]), 1) if i < 2 else PRESS_2026Q3[code]
year = lambda c: QUARTERS[COLS.index(c)][:4]
prev = lambda c: COLS[COLS.index(c) - 1]
fc = COLS[FACT:]  # forecast columns G..O


B10_YEAR = {"2026": "E", "2027": "F", "2028": "G"}


def harv(c):
    """Harvest growth that shows in quarter c: Q3-Q4 of a year and Q1-Q2 of the next."""
    q = QUARTERS[COLS.index(c)]
    y = int(q[:4]) if q[-1] in "34" else int(q[:4]) - 1
    if y == 2025:
        return round(float(B.harvest_growth()["2025"]), 1)
    return f"=B10_AGRO!{B10_YEAR[str(y)]}26"  # harvest growth of the six crops (B10_AGRO counts them since 2026-10-25)


def tariffs(c):
    """Tariff hikes in effect (section 7, row TA['EFF']) in this quarter and the three before it."""
    i = COLS.index(c)
    return f"SUM({COLS[max(0, i - 3)]}{TA['EFF']}:{c}{TA['EFF']})"


rows = [
    [""],
    ["4. ИПЦ по блокам НБУ: кварталы, % г/г на конец квартала. Итог (строка 44) идёт в ANCHORS, строка 10"],
    ["Код", "Показатель", "Уравнение"] + QUARTERS + ["Комментарий"],
    ["FX_Q", "Девальвация гривны", "средний курс к тому же кварталу прошлого года"]
    + [f"=(ANCHORS!{a}12/ANCHORS!{b}12-1)*100" for a, b in zip(ANCH, ANCH4)] + ["из ANCHORS, строка 12"],
    ["WAGE_Q", "Рост номинальной зарплаты", "к тому же кварталу прошлого года"]
    + [f"=(ANCHORS!{a}20/ANCHORS!{b}20-1)*100" for a, b in zip(ANCH, ANCH4)] + ["из ANCHORS, строка 20 (B4)"],
    ["BRENT", "Нефть Brent", "USD/барр., средняя за квартал"]
    + [round(float(x_), 1) for x_ in B.Q.long_quarterly()["PX_BRENT_USD"].loc["2026Q1":"2026Q3"]]
    + [f"=INDEX(SCENARIOS!$L${BRENT_Y}:$N${BRENT_Y};{int(QUARTERS[COLS.index(c)][:4]) - 2025})" for c in fc]
    + [f"факт EIA; прогноз — SCENARIOS строка {BRENT_Y}, активный сценарий: среднее года во всех кварталах года"],
    ["BRENT_G", "Рост цены нефти", "% г/г"]
    + [f"=({c}34/{b}-1)*100".replace(",", ".").replace(".", ",") for c, b in zip(COLS[:4], BRENT_2025)]
    + [f"=({c}34/{COLS[COLS.index(c) - 4]}34-1)*100" for c in COLS[4:]],
    ["HARV", "Рост урожая зерновых и масличных", "урожай года действует с 3 кв. по 2 кв. следующего"]
    + [harv(c) for c in COLS] + ["B10_AGRO строка 26 (урожай шести культур)"],
    ["FUEL", B.NAMES["FUEL"], f"{kv('FUEL', 'const')} + {kv('FUEL', 'BRENT')} × нефть + {kv('FUEL', 'FX')} × девальвация"]
    + [fact("FUEL", i) for i in range(FACT)]
    + [f"=IF({c}{FU['YY']}<>\"\";{c}{FU['YY']};"
       f"{C('FUEL', 'const')}+{C('FUEL', 'BRENT')}*{c}35+{C('FUEL', 'FX')}*{c}32)" for c in fc]
    + [f"задано в SCENARIOS (ввод кв/кв строка {SL.FUEL_QQ}, г/г — строка {FU['YY']}) — берётся оно, иначе уравнение"],
    ["RAW", B.NAMES["RAW"], f"{kv('RAW', 'const')} + {kv('RAW', 'RAW_L1')} × прошлый квартал + {kv('RAW', 'FUEL_L1')} × топливо прошлого квартала "
                            f"{kv('RAW', 'HARV')} × рост урожая"]
    + [fact("RAW", i) for i in range(FACT)]
    + [f"={C('RAW', 'const')}+{C('RAW', 'RAW_L1')}*{prev(c)}38+{C('RAW', 'FUEL_L1')}*{prev(c)}37+{C('RAW', 'HARV')}*{c}36" for c in fc]
    + ["овощи, фрукты, мясо, яйца, молоко"],
    ["ADM_X", "Админцены без тарифов ЖКУ", f"{kv('ADM', 'const')} + {kv('ADM', 'ADM_L1')} × прошлый квартал"]
    + [fact("ADM", i) for i in range(FACT)]
    + [f"={C('ADM', 'const')}+{C('ADM', 'ADM_L1')}*{prev(c)}39" for c in fc] + ["акцизы на табак и алкоголь, проезд, связь"],
    ["ADM_T", "Вклад повышения тарифов ЖКУ", "доля ЖКУ в админценах × повышения за 4 квартала", 0, 0]
    + [f"={C('ADM', 'TARIFF')}*{tariffs(c)}" for c in COLS[2:]]
    + [f"SCENARIOS строка {TARIFF_ROW}, только после отмены военного положения (строка {TA['EFF']})"],
    ["ADM", B.NAMES["ADM"], "строка 39 + строка 40"] + [fact("ADM", i) for i in range(FACT)]
    + [f"={c}39+{c}40" for c in fc],
    ["CORE", B.NAMES["CORE"], f"{kv('CORE', 'const')} + {kv('CORE', 'FX')} × девальвация + {kv('CORE', 'WAGE')} × зарплата "
                              f"+ {kv('CORE', 'CORE_L1')} × прошлый квартал"]
    + [fact("CORE", i) for i in range(FACT)]
    + [f"={C('CORE', 'const')}+{C('CORE', 'FX')}*{c}32+{C('CORE', 'WAGE')}*{c}33+{C('CORE', 'CORE_L1')}*{prev(c)}42" for c in fc]
    + ["обработанные продукты, непродовольственные товары, услуги"],
    ["CPI_B", "ИПЦ из блоков", f"{kv('W', 'const')} + {kv('W', 'CORE')}×базовая + {kv('W', 'RAW')}×сырые + {kv('W', 'ADM')}×админ "
                              f"+ {kv('W', 'FUEL')}×топливо + влияние ставки (B7)"]
    + [f"={C('W', 'const')}+{C('W', 'CORE')}*{c}42+{C('W', 'RAW')}*{c}38+{C('W', 'ADM')}*{c}41+{C('W', 'FUEL')}*{c}37"
       + ("" if c in COLS[:FACT] else f"+B7_MONETARY!${YEAR_COL[year(c)]}$42") for c in COLS]
    + ["2026Q1–Q3: проверка весов на факте"],
    ["CPI_Q", "ИПЦ в модели", f"факт; задано в SCENARIOS строка {SL.CPI_Q}; иначе строка 43 этого листа", "=ANCHORS!AZ10", "=ANCHORS!BA10"]
    + [f"=IF(SCENARIOS!{SCQ[c]}{SL.CPI_Q}<>\"\";SCENARIOS!{SCQ[c]}{SL.CPI_Q};{c}43)" for c in COLS[2:]] + ["идёт в ANCHORS, строка 10"],
    [""],
    ["5. Вклады блоков в ИПЦ, п.п."],
    ["Код", "Блок", ""] + QUARTERS,
] + [[f"CPI_{k}", B.NAMES[k], f"вес × блок (строка {r})"] + [f"={C('W', k)}*{c}{r}" for c in COLS]
     for k, r in [("CORE", 42), ("RAW", 38), ("ADM", 41), ("FUEL", 37)]] + [
    ["CPI_OTHER", "Константа и ставка НБУ", ""] + [f"={c}43-SUM({c}48:{c}51)" for c in COLS],
]
pc = lambda c: COLS[COLS.index(c) - 1]
fuel_rows = [
    ["6. Топливо: ввод SCENARIOS (кв/кв) → г/г для блока «топливо» (строка 37)"],
    ["Код", "Показатель", "Как считается"] + QUARTERS + ["Комментарий"],
    ["FUEL_IN", "Ввод: прирост цен топлива к прошлому кварталу", f"SCENARIOS строка {SL.FUEL_QQ}, % кв/кв", "", ""]
    + [f"=IF(SCENARIOS!{SCQ[c]}{SL.FUEL_QQ}=\"\";\"\";SCENARIOS!{SCQ[c]}{SL.FUEL_QQ})" for c in COLS[2:]]
    + ["пусто — ввода нет, работает уравнение строки 37"],
    ["FUEL_LAG", "Тот же квартал год назад, кв/кв", "сезонность: кв/кв четыре квартала назад", "", "",
     FUEL_QOQ["2025Q3"], FUEL_QOQ["2025Q4"]] + [f"={COLS[COLS.index(c) - 4]}{FU['QQ']}" for c in COLS[4:]]
    + ["2025Q3–Q4 — MacroStat, ИПЦ «топливо и масла»"],
    ["FUEL_YY", "Топливо из ввода, г/г", "(1 + г/г прошлого квартала) × (1 + ввод) / (1 + кв/кв год назад) − 1", "", ""]
    + [f"=IF({c}{FU['IN']}=\"\";\"\";(1+{pc(c)}37/100)*(1+{c}{FU['IN']}/100)/(1+{c}{FU['LAG']}/100)*100-100)" for c in COLS[2:]]
    + ["идёт в строку 37 (2026Q3 — проверка: факт НБУ 46,2)"],
    ["FUEL_QQ", "Топливо: итог кв/кв (ввод или уравнение)", "ввод, иначе из г/г строки 37", FUEL_QOQ["2026Q1"], FUEL_QOQ["2026Q2"]]
    + [f"=IF({c}{FU['IN']}<>\"\";{c}{FU['IN']};(1+{c}37/100)/(1+{pc(c)}37/100)*(1+{c}{FU['LAG']}/100)*100-100)" for c in COLS[2:]]
    + ["показывает, какой кв/кв даёт уравнение"],
]
rows += [[""]] + fuel_rows
assert 29 + len(rows) - 1 == FU["QQ"]
tariff_rows = [
    ["7. Тарифы ЖКУ: повышение только после отмены военного положения"],
    ["Код", "Показатель", "Как считается"] + QUARTERS + ["Комментарий"],
    ["ML_END", "Первый квартал без военного положения", "квартал после прекращения огня (SCENARIOS строка 16, активный сценарий)",
     f"=LET(q;{CEASE};IF(q=\"нет\";\"нет\";IF(RIGHT(q;1)=\"4\";(LEFT(q;4)+1)&\"Q1\";LEFT(q;5)&(RIGHT(q;1)+1))))"]
    + [""] * 11 + ["«нет» — военное положение до конца горизонта, тарифы не повышаются"],
    ["TARIFF_IN", "Ввод: повышение тарифов", f"SCENARIOS строка {TARIFF_ROW}, % в квартал повышения", 0, 0]
    + [f"=N(SCENARIOS!{SCQ[c]}{TARIFF_ROW})" for c in COLS[2:]] + [""],
    ["TARIFF_MAX", "Предел повышения тарифов", "% в год, равными шагами по кварталам", TARIFF_MAX]
    + [""] * 11 + ["ориентир НБУ: тарифы 20–30% в год, админцены 11–14% г/г в 2026–2028"],
    ["TARIFF_BACK", "Накоплено к повышению", "остаток прошлого квартала + ввод квартала", f"=D{TA['IN']}"]
    + [f"={COLS[i - 1]}{TA['BACK']}-{COLS[i - 1]}{TA['EFF']}+{c}{TA['IN']}" for i, c in enumerate(COLS) if i]
    + ["повышения, введённые на время военного положения, ждут здесь"],
    ["TARIFF_EFF", "Повышение тарифов с учётом военного положения", "0 до отмены; потом накопленное, но не больше предела / 4 за квартал"]
    + [f"=IF(OR($D${TA['END']}=\"нет\";{c}$31<$D${TA['END']});0;MIN({c}{TA['BACK']};$D${TA['MAX']}/4))" for c in COLS]
    + ["идёт в строку 40 (ADM_T)"],
]
rows += [[""]] + tariff_rows
assert 29 + len(rows) - 1 == TA["EFF"]
out[f"B3_PRICES!A29:P{29 + len(rows) - 1}"] = rows  # through section 7
out["ANCHORS!BB10"] = [["=INDEX(B3_PRICES!$D$44:$O$44;MATCH(BB$4;B3_PRICES!$D$31:$O$31;0))"]]
if "--coefs" in sys.argv:
    out = {k: v for k, v in out.items() if k.startswith("COEFS")}
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
