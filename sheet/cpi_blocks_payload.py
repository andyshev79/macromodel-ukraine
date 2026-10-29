"""Build the quarterly CPI-by-blocks section of B3_PRICES (rows 38-59), its COEFS rows, the Brent
row in SCENARIOS and the ANCHORS CPI link (macromodel.blocks.cpi_blocks).

Quarter columns D:O of B3 are 2026Q1..2028Q4 (ANCHORS AZ:BK). 2026Q1-Q2 are facts from the
history, 2026Q3 from the NBU press release for September (until the quarterly file has it).
Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). --coefs: COEFS rows only.
"""
import json
import sys

from macromodel import scenario_layout as SL
from macromodel.blocks import cpi_blocks as B
from macromodel.blocks.shocks import FUEL_ROW, SHOCK_ROW, TARIFF_ROW

QUARTERS = [f"{y}Q{q}" for y in (2026, 2027, 2028) for q in (1, 2, 3, 4)]
COLS = "DEFGHIJKLMNO"
FACT = 3  # 2026Q1, Q2, Q3 are facts
ANCH = ["AZ", "BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BK"]
ANCH4 = ["AV", "AW", "AX", "AY"] + ANCH[:8]  # same quarter last year
SCQ = {c: s for c, s in zip(COLS[2:], "CDEFGHIJKL")}  # SCENARIOS quarter columns (2026Q3..2028Q4)
YEAR_COL = {"2026": "E", "2027": "F", "2028": "G"}  # B3 annual columns
SC_YEAR = {"2026": "L", "2027": "M", "2028": "N"}  # SCENARIOS active annual columns
BRENT_ROW = SL.BRENT
PRESS_2026Q3 = {"CORE": 8.8, "RAW": 6.7, "ADM": 13.6, "FUEL": 46.2}  # NBU, September 2026 y/y
BRENT_2025 = [75.8, 68.0, 69.0, 63.6]

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
    """Tariff hikes of this quarter and the three before it (SCENARIOS row TARIFF_ROW: C = 2026Q3 = B3 column F)."""
    i = COLS.index(c)
    cols = [SCQ[COLS[j]] for j in range(max(2, i - 3), i + 1)]
    return f"SUM(SCENARIOS!{cols[0]}{TARIFF_ROW}:{cols[-1]}{TARIFF_ROW})"


rows = [
    [""],
    ["4. ИПЦ по блокам НБУ: кварталы, % г/г на конец квартала. Итог (строка 52) идёт в ANCHORS, строка 10"],
    ["Код", "Показатель", "Уравнение"] + QUARTERS + ["Комментарий"],
    ["FX_Q", "Девальвация гривны", "средний курс к тому же кварталу прошлого года"]
    + [f"=(ANCHORS!{a}12/ANCHORS!{b}12-1)*100" for a, b in zip(ANCH, ANCH4)] + ["из ANCHORS, строка 12"],
    ["WAGE_Q", "Рост номинальной зарплаты", "к тому же кварталу прошлого года"]
    + [f"=(ANCHORS!{a}20/ANCHORS!{b}20-1)*100" for a, b in zip(ANCH, ANCH4)] + ["из ANCHORS, строка 20 (B4)"],
    ["BRENT", "Нефть Brent", "USD/барр., средняя за квартал"]
    + [round(float(x_), 1) for x_ in B.Q.long_quarterly()["PX_BRENT_USD"].loc["2026Q1":"2026Q3"]]
    + [f"=SCENARIOS!{SC_YEAR[year(c)]}{BRENT_ROW}" for c in fc] + [f"факт EIA; прогноз SCENARIOS, строка {BRENT_ROW}"],
    ["BRENT_G", "Рост цены нефти", "% г/г"]
    + [f"=({c}42/{b}-1)*100".replace(",", ".").replace(".", ",") for c, b in zip(COLS[:4], BRENT_2025)]
    + [f"=({c}42/{COLS[COLS.index(c) - 4]}42-1)*100" for c in COLS[4:]],
    ["HARV", "Рост урожая зерновых и масличных", "урожай года действует с 3 кв. по 2 кв. следующего"]
    + [harv(c) for c in COLS] + ["B10_AGRO строка 26 (урожай шести культур)"],
    ["FUEL", B.NAMES["FUEL"], f"{kv('FUEL', 'const')} + {kv('FUEL', 'BRENT')} × нефть + {kv('FUEL', 'FX')} × девальвация"]
    + [fact("FUEL", i) for i in range(FACT)]
    + [f"=IF(SCENARIOS!{SCQ[c]}{FUEL_ROW}<>\"\";SCENARIOS!{SCQ[c]}{FUEL_ROW};"
       f"{C('FUEL', 'const')}+{C('FUEL', 'BRENT')}*{c}43+{C('FUEL', 'FX')}*{c}40)" for c in fc]
    + [f"задано в SCENARIOS (ввод кв/кв строка {SL.FUEL_QQ}, итог г/г строка {FUEL_ROW}) — берётся оно, иначе уравнение"],
    ["RAW", B.NAMES["RAW"], f"{kv('RAW', 'const')} + {kv('RAW', 'RAW_L1')} × прошлый квартал + {kv('RAW', 'FUEL_L1')} × топливо прошлого квартала "
                            f"{kv('RAW', 'HARV')} × рост урожая"]
    + [fact("RAW", i) for i in range(FACT)]
    + [f"={C('RAW', 'const')}+{C('RAW', 'RAW_L1')}*{prev(c)}46+{C('RAW', 'FUEL_L1')}*{prev(c)}45+{C('RAW', 'HARV')}*{c}44" for c in fc]
    + ["овощи, фрукты, мясо, яйца, молоко"],
    ["ADM_X", "Админцены без тарифов ЖКУ", f"{kv('ADM', 'const')} + {kv('ADM', 'ADM_L1')} × прошлый квартал"]
    + [fact("ADM", i) for i in range(FACT)]
    + [f"={C('ADM', 'const')}+{C('ADM', 'ADM_L1')}*{prev(c)}47" for c in fc] + ["акцизы на табак и алкоголь, проезд, связь"],
    ["ADM_T", "Вклад повышения тарифов ЖКУ", "доля ЖКУ в админценах × повышения за 4 квартала", 0, 0]
    + [f"={C('ADM', 'TARIFF')}*{tariffs(c)}" for c in COLS[2:]] + [f"SCENARIOS, строка {TARIFF_ROW}"],
    ["ADM", B.NAMES["ADM"], "строка 47 + строка 48"] + [fact("ADM", i) for i in range(FACT)]
    + [f"={c}47+{c}48" for c in fc],
    ["CORE", B.NAMES["CORE"], f"{kv('CORE', 'const')} + {kv('CORE', 'FX')} × девальвация + {kv('CORE', 'WAGE')} × зарплата "
                              f"+ {kv('CORE', 'CORE_L1')} × прошлый квартал"]
    + [fact("CORE", i) for i in range(FACT)]
    + [f"={C('CORE', 'const')}+{C('CORE', 'FX')}*{c}40+{C('CORE', 'WAGE')}*{c}41+{C('CORE', 'CORE_L1')}*{prev(c)}50" for c in fc]
    + ["обработанные продукты, непродовольственные товары, услуги"],
    ["CPI_B", "ИПЦ из блоков", f"{kv('W', 'const')} + {kv('W', 'CORE')}×базовая + {kv('W', 'RAW')}×сырые + {kv('W', 'ADM')}×админ "
                              f"+ {kv('W', 'FUEL')}×топливо + влияние ставки (B7)"]
    + [f"={C('W', 'const')}+{C('W', 'CORE')}*{c}50+{C('W', 'RAW')}*{c}46+{C('W', 'ADM')}*{c}49+{C('W', 'FUEL')}*{c}45"
       + ("" if c in COLS[:FACT] else f"+${YEAR_COL[year(c)]}$34") for c in COLS]
    + ["2026Q1–Q3: проверка весов на факте"],
    ["CPI_Q", "ИПЦ в модели", f"факт; задано в SCENARIOS строка {SL.CPI_Q}; иначе строка 51 этого листа", "=ANCHORS!AZ10", "=ANCHORS!BA10"]
    + [f"=IF(SCENARIOS!{SCQ[c]}{SL.CPI_Q}<>\"\";SCENARIOS!{SCQ[c]}{SL.CPI_Q};{c}51)" for c in COLS[2:]] + ["идёт в ANCHORS, строка 10"],
    [""],
    ["5. Вклады блоков в ИПЦ, п.п."],
    ["Код", "Блок", ""] + QUARTERS,
] + [[f"CPI_{k}", B.NAMES[k], f"вес × блок (строка {r})"] + [f"={C('W', k)}*{c}{r}" for c in COLS]
     for k, r in [("CORE", 50), ("RAW", 46), ("ADM", 49), ("FUEL", 45)]] + [
    ["CPI_OTHER", "Константа и ставка НБУ", ""] + [f"={c}51-SUM({c}56:{c}59)" for c in COLS],
]
out[f"B3_PRICES!A37:P{37 + len(rows) - 1}"] = rows
out["ANCHORS!BB10"] = [["=INDEX(B3_PRICES!$D$52:$O$52;MATCH(BB$4;B3_PRICES!$D$39:$O$39;0))"]]
out[f"SCENARIOS!A{BRENT_ROW - 1}:O{BRENT_ROW}"] = [
    ["Нефть", "Единицы", "База", "", "", "Пессимистичный", "", "", "Оптимистичный", "", "", "Активный"],
    ["Цена нефти Brent (2026 — 4 кв., дальше средняя за год)", "USD/барр."] + [90, 80, 75, 95, 90, 85, 85, 72, 70]
    + [f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{a}{BRENT_ROW};{b}{BRENT_ROW};{c}{BRENT_ROW})" for a, b, c in ("CFI", "DGJ", "EHK")]
    + ["Факт 3 кв. 2026: 96 USD. Оценка Claude: снижение по мере ослабления шока; пессим. — дорогая нефть, оптим. — дешевле"],
]
if "--coefs" in sys.argv:
    out = {k: v for k, v in out.items() if k.startswith("COEFS")}
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
