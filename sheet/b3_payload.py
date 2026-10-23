"""Build the cell contents of B3_PRICES, its COEFS rows and ANCHORS forecast links (block B3).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
ANCHORS forecast formulas are written once per row and copied right in the sheet.
"""
import json
import sys

from macromodel.blocks.prices import annual, coef_table

COEF_FIRST = 36  # B1 uses COEFS rows 5-22, B2 rows 23-35
coefs = coef_table()
crow = {(r["eq"], r["var"]): COEF_FIRST + i for i, r in enumerate(coefs)}


def C(eq, v):
    return f"COEFS!$E${crow[(eq, v)]}"


def k(eq, v):
    return f"{next(r['coef'] for r in coefs if (r['eq'], r['var']) == (eq, v)):.2f}".replace(".", ",")


out = {}
end = COEF_FIRST + len(coefs) - 1
out[f"COEFS!A{COEF_FIRST}:L{end}"] = [
    [f"{r['eq']}_{r['var']}", "B3", r["eq"], r["var"], r["coef"], r["se"], round(r["coef"] / r["se"], 1),
     "2016–2025", r["method"], r["r2"], "2026-10-21", r["note"]] for r in coefs]

a = annual().loc["2025"]


def col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# Explicit quarter ranges per year (H = 2015Q1): a whole-row SUMIF would make a
# circular reference, because next year's ANCHORS cells depend on this year's result.
YEAR = {c: 2024 + i for i, c in enumerate("CDEFG")}
span = lambda c, r: f"ANCHORS!{col(7 + 4 * (YEAR[c] - 2015))}{r}:{col(10 + 4 * (YEAR[c] - 2015))}{r}"
avg = lambda c, r: f"AVERAGE({span(c, r)})"
sm = lambda c, r: f"SUM({span(c, r)})"
top = [
    ["3. Цены"],
    [""],
    ["Что считает", "Средний за год рост ИПЦ, ИЦП и дефлятора ВВП; номинальный ВВП"],
    ["Берёт", "B2_DEMAND (реальная зарплата), SCENARIOS (газ TTF, инфляция еврозоны), ANCHORS (курс, реальный ВВП), COEFS"],
    ["Пишет в ANCHORS", "CPI_YOY, PPI_YOY, GDP_NOM"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Модель даёт рост за год. В ANCHORS им заполняются кварталы без факта; строка «с учётом факта» — среднее за год по ANCHORS."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Как считается"],
    ["FX", "Девальвация гривны (средний курс)", "%", round(float(a["FX"]), 1),
     f"={avg('E', 12)}/{avg('D', 12)}*100-100", "=B5_EXTERNAL!F40", "=B5_EXTERNAL!G40",
     "2026: курс из ANCHORS. 2027–2028 — из B5_EXTERNAL (инфляционный разрыв и резервы)"],
    ["WAGE", "Рост номинальной зарплаты", "%", round(float(a["WAGE"]), 1), "=B4_LABOUR!E30", "=B4_LABOUR!F30", "=B4_LABOUR!G30",
     "из B4_LABOUR (с учётом факта)"],
    ["TTF", "Цена газа TTF", "EUR/МВт·ч", 36.5, "=SCENARIOS!L27", "=SCENARIOS!M27", "=SCENARIOS!N27", "из SCENARIOS"],
    ["TTF_G", "Рост цены газа TTF", "%", round(float(a["TTF"]), 1), "=(E13/D13-1)*100", "=(F13/E13-1)*100", "=(G13/F13-1)*100", "из строки выше"],
    ["HICP", "Инфляция еврозоны", "%", float(a["HICP"]), "=SCENARIOS!L29", "=SCENARIOS!M29", "=SCENARIOS!N29", "из SCENARIOS"],
    [""],
    ["2. Цены, средний рост за год, %"],
    ["Код", "Показатель", "Уравнение", 2025, 2026, 2027, 2028, "Комментарий"],
    ["CPI_M", "ИПЦ, модель", f"{k('CPI','const')} + {k('CPI','WAGE')} × рост зарплаты + {k('CPI','FX')} × девальвация + влияние ставки (B7)", round(float(a["CPI"]), 1)]
    + [f"={C('CPI','const')}+{C('CPI','FX')}*{c}11+{C('CPI','WAGE')}*{c}12+B7_MONETARY!{c}42" for c in "EFG"]
    + ["Оценка по кварталам (R² 0,44, без 2022Q1–2023Q1); качество — лист MODEL_QUALITY"],
    ["CPI_YOY", "ИПЦ с учётом факта", "среднее кварталов ANCHORS"] + [f"={avg(c, 10)}" for c in "DEFG"],
    ["PPI_M", "ИЦП, модель", f"{k('PPI','CPI')} × ИПЦ + {k('PPI','TTF')} × рост цены газа", round(float(a["PPI"]), 1)]
    + [f"={C('PPI','const')}+{C('PPI','CPI')}*{c}20+{C('PPI','TTF')}*{c}14" for c in "EFG"] + ["R² 0,89"],
    ["PPI_YOY", "ИЦП с учётом факта", "среднее кварталов ANCHORS"] + [f"={avg(c, 11)}" for c in "DEFG"],
    ["DEFL_M", "Дефлятор ВВП, модель", f"{k('DEFL','const')} + {k('DEFL','CPI')} × ИПЦ + {k('DEFL','PPI')} × ИЦП", round(float(a["DEFL"]), 1)]
    + [f"={C('DEFL','const')}+{C('DEFL','CPI')}*{c}20+{C('DEFL','PPI')}*{c}22" for c in "EFG"] + ["R² 0,92"],
    ["DEFL", "Дефлятор ВВП с учётом факта", "номинальный / реальный ВВП за год"]
    + [f"=({sm(c, 8)}/{sm(c, 5)})/({sm(p, 8)}/{sm(p, 5)})*100-100" for c, p in zip("DEFG", "CDEF")],
    ["GDP_NOM_G", "Рост номинального ВВП", "%"] + [f"={sm(c, 8)}/{sm(p, 8)}*100-100" for c, p in zip("DEFG", "CDEF")],
    ["GDP_NOM", "Номинальный ВВП", "млрд грн"] + [f"={sm(c, 8)}/1000" for c in "DEFG"],
    ["CPI_GAP", "ИПЦ − цель НБУ (5%)", "п.п., проверка на листе CHECKS"] + [f"={c}20-5" for c in "DEFG"],
    [""],
    ["3. Вклады в ИПЦ по модели, п.п."],
    ["Код", "Фактор", "", 2025, 2026, 2027, 2028],
    ["CPI_WAGE", "Зарплаты", "", ""] + [f"={C('CPI','WAGE')}*{c}12" for c in "EFG"],
    ["CPI_FX", "Курс", "", ""] + [f"={C('CPI','FX')}*{c}11" for c in "EFG"],
    ["CPI_CONST", "Константа", "", ""] + [f"={C('CPI','const')}" for c in "EFG"],
    ["CPI_RATE", "Ставка НБУ прошлого года", "", ""] + [f"=B7_MONETARY!{c}42" for c in "EFG"],
    ["CPI_M", "ИПЦ, модель", "", ""] + [f"=SUM({c}31:{c}34)" for c in "EFG"],
]
out[f"B3_PRICES!A1:H{len(top)}"] = top

# ANCHORS: masters for the first forecast cell of each row; copied right to BK
look = lambda c, r: f"INDEX(B3_PRICES!$E${r}:$G${r};MATCH({c}$2;B3_PRICES!$E$10:$G$10;0))"
out["ANCHORS!BB8"] = [[f"=BB5*AX9/100*(1+{look('BB', 23)}/100)"]]
out["ANCHORS!BC10"] = [[f"={look('BC', 19)}"]]
out["ANCHORS!BB11"] = [[f"={look('BB', 21)}"]]
out["ANCHORS!BD12"] = [[f"=AZ12*(1+{look('BD', 11)}/100)"]]

out["CHECKS!A20:C22"] = [["Цены"], ["Инфляция против цели НБУ", "Средний ИПЦ за год − 5%; не выше порога", 1.0], ["  статус"]]
json.dump(out, sys.stdout, ensure_ascii=False)
