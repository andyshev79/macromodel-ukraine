"""Build the cell contents of B1_REAL and COEFS (block B1) for the Google Sheet.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys
from pathlib import Path

import pandas as pd

from macromodel.blocks.real_sector import SECTORS, annual_growth, coef_table, real_levels_q
from macromodel.blocks.shocks import SHOCK_ROW, SHOCKS, estimated

QUARTERS = [f"{y}Q{q}" for y in range(2015, 2029) for q in range(1, 5)]


def col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


QCOL = {q: col(7 + i) for i, q in enumerate(QUARTERS)}  # 2015Q1 -> H, same as ANCHORS
LAST = "2026Q2"
CODES = list(SECTORS) + ["OTHER"]
NAMES = dict(SECTORS, OTHER="Прочие отрасли и чистые налоги")

coefs = coef_table()
crow = {(r["eq"], r["var"]): 5 + i for i, r in enumerate(coefs)}


def C(s, v):
    return f"COEFS!$E${crow[(f'GVA_{s}', v)]}"


cval = {(r["eq"], r["var"]): r["coef"] for r in coefs}
num = lambda v: f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")
kv = lambda s, v: num(cval[(f"GVA_{s}", v)])
met = {k: num(estimated()[k][0]) if k in estimated() else num(SHOCKS[k][0]) for k in ("MET_B", "MET_C")}


out = {}
out["COEFS!A5:L22"] = [[f"GVA_{r['eq'][4:]}_{r['var']}", "B1", r["eq"], r["var"], float(r["coef"]),
                        None if r["se"] is None else float(r["se"]),
                        None if r["se"] in (None, 0) else round(float(r["coef"]) / float(r["se"]), 1),
                        r.get("period", "2016–2025") if r["n"] else "", r["method"],
                        None if r["r2"] is None else float(r["r2"]), "2026-10-23" if r.get("period") else "2026-10-21", r["note"]] for r in coefs]

text = [
    ["1. Реальный сектор"],
    [""],
    ["Что считает", "Реальная ВДС по 9 отраслям и прочим, сумма = ВВП по производству (GDP_REAL_P)"],
    ["Берёт", "SCENARIOS (урожай, порты, мощность энергосистемы, ВВП еврозоны, оборона), COEFS"],
    ["Пишет в ANCHORS", "GDP_REAL_P (и GDP_REAL на прогнозе, пока нет B2)"],
    ["Статус", "в работе: версия 1"],
    ["Как читать", "Годовой рост отрасли (раздел 2) применяется к тому же кварталу прошлого года (раздел 3), сезонность сохраняется. Синие ячейки — факт."],
    [""],
    ["1. Сценарные драйверы (активный сценарий)"],
    ["Код", "Показатель", "Единицы", 2025, 2026, 2027, 2028, "Источник 2025"],
]
drv = [
    ("HARVEST", "Урожай зерновых и масличных", "млн т", 80, 24, "УЗА"),
    ("PORTS", "Пропускная способность портов", "млн т в год", 82.2, 19, "USPA"),
    ("CAP", "Доступная мощность энергосистемы в пик", "ГВт", 15, 18, "DiXi: перед зимой 2024/25 больше 15 ГВт"),
    ("EA_GDP", "Рост ВВП еврозоны", "%", 1.4, 28, "Eurostat, приблизительно"),
    ("DEF", "Расходы на оборону", "% ВВП", 34.4, 21, "Казначейство (функция 0200) / ВВП"),
]
for code, name, unit, v25, srow, src in drv:
    text.append([code, name, unit, v25] + [f"=SCENARIOS!{c}{srow}" for c in "LMN"] + [src])
out["B1_REAL!A1:H15"] = text
# metallurgy utilisation (sheet.shocks_payload). The shock is elasticity × change in utilisation in points
# of 2025 output: a restart from a low base (15 -> 50) adds 35% of the 2025 output, not +233%
out["B1_REAL!A16:H16"] = [["MET", "Металлургия: загрузка мощностей", "% от 2025", 100,
                           "=SCENARIOS!L63", "=SCENARIOS!M63", "=SCENARIOS!N63", "SCENARIOS (отраслевые шоки)"]]
MET = lambda s, c, p: f"+COEFS!$E${SHOCK_ROW['MET_' + s]}*({c}$16-{p}$16)"

g = annual_growth(real_levels_q())
F_REC_ROW = 171  # after B2 peace rows 168-170
ACT = dict(zip("EFG", "LMN"))  # active-scenario columns in SCENARIOS
out[f"COEFS!A{F_REC_ROW}:L{F_REC_ROW}"] = [["GVA_F_REC", "B1", "GVA_F", "REC", 1.0, "", "", "", "калибровка", "", "2026-10-25",
    "Восстановление: строительство растёт на те же п.п., что ВНОК (SCENARIOS строка 124). Строительство — около "
    "половины ВНОК; машины и оборудование в основном импорт. Оценка Claude"]]
O_CODES = ["MIL_NY", "ADM_N", "DEF_G", "ADM_G", "DEF_NOM_G", "ADM_NOM_G", "DEF_SH", "GVA_O", "O_CHK"]
O_ROW = {k: 61 + i for i, k in enumerate(O_CODES)}
eq = {
    "A": ("−1,68 + 0,66 × рост урожая", lambda c, p: f"={C('A','const')}+{C('A','HARVEST')}*({c}$11/{p}$11-1)*100"),
    "B": (f"{kv('B','const')} + {kv('B','PORTS')} × рост портов + {kv('B','CAP')} × рост мощности + {met['MET_B']} × изменение загрузки металлургии",
          lambda c, p: f"={C('B','const')}+{C('B','PORTS')}*({c}$12/{p}$12-1)*100+{C('B','CAP')}*({c}$13/{p}$13-1)*100{MET('B', c, p)}"),
    "C": (f"{kv('C','const')} + {kv('C','HH')} × рост потребления домохозяйств (B2) + {kv('C','CAP')} × рост мощности "
          f"+ {met['MET_C']} × изменение загрузки металлургии",
          lambda c, p: f"={C('C','const')}+{C('C','HH')}*B2_DEMAND!{c}$20+{C('C','CAP')}*({c}$13/{p}$13-1)*100{MET('C', c, p)}"),
    "D": ("рост мощности (эластичность 1)", lambda c, p: f"={C('D','const')}+{C('D','CAP')}*({c}$13/{p}$13-1)*100"),
    "F": ("тренд 2024–2025 + влияние ставки (B7) + восстановление после войны (SCENARIOS строка 124)",
          lambda c, p: f"={C('F','const')}+B7_MONETARY!{c}41+COEFS!$E${F_REC_ROW}*SCENARIOS!{ACT[c]}124"),
    "G": ("константа (до связки с потреблением B2)", lambda c, p: f"={C('G','const')}"),
    "H": ("−0,55 + 0,22 × рост портов", lambda c, p: f"={C('H','const')}+{C('H','PORTS')}*({c}$12/{p}$12-1)*100"),
    "J": ("тренд 2024–2025", lambda c, p: f"={C('J','const')}"),
    "O": ("доля обороны × рост численности военных + доля госуправления × рост штата (раздел 5)",
          lambda c, p: f"={c}{O_ROW['GVA_O']}"),
    "OTHER": ("−2,68 + 0,77 × рост потребления домохозяйств (B2)",
              lambda c, p: f"={C('OTHER','const')}+COEFS!$E$35*B2_DEMAND!{c}$20"),
}
rows = [["2. Рост реальной ВДС, % г/г"], ["Код", "Отрасль", "Уравнение", 2025, 2026, 2027, 2028]]
for s in CODES:
    txt, f = eq[s]
    rows.append([f"GVA_{s}", NAMES[s], txt, round(float(g.loc["2025", s]), 1)] + [f(c, p) for c, p in zip("EFG", "DEF")])
sumif = lambda c, yr: f"SUMIF($H$31:$BK$31;{yr};$H$43:$BK$43)"
rows.append(["GDP_REAL_P", "ВВП по производству", "сумма отраслей"] +
            [f"={sumif(c, c + '$18')}/{sumif(c, c + '$18-1')}*100-100" for c in "DEFG"])
out["B1_REAL!A17:G29"] = rows

lv = real_levels_q()
hdr = [["3. Реальная ВДС по кварталам, млн грн в ценах 2021"],
       ["", "", "", "", "", "", "Год"] + [f"=ANCHORS!{QCOL[q]}2" for q in QUARTERS],
       ["Код", "Отрасль", "", "", "", "", ""] + [f"=ANCHORS!{QCOL[q]}4" for q in QUARTERS]]
body = []
for k, s in enumerate(CODES):
    r = 33 + k
    line = [f"GVA_{s}", NAMES[s], "", "", "", "", ""]
    for i, q in enumerate(QUARTERS):
        if q <= LAST:
            line.append(round(float(lv.loc[q, s]), 1))
        else:
            c, p = QCOL[q], QCOL[QUARTERS[i - 4]]
            line.append(f"={p}{r}*(1+INDEX($E${19 + k}:$G${19 + k};MATCH({c}$31;$E$18:$G$18;0))/100)")
    body.append(line)
body.append(["GDP_REAL_P", "ВВП по производству", "", "", "", "", ""] + [f"=SUM({QCOL[q]}33:{QCOL[q]}42)" for q in QUARTERS])
out["B1_REAL!A30:BK43"] = [r for r in hdr] + body

contrib = [["4. Вклад отраслей в рост ВВП, п.п. г/г"], ["Код", "Отрасль", "", "", "", "", ""] + [f"={QCOL[q]}32" for q in QUARTERS]]
for k, s in enumerate(CODES + ["GDP"]):
    r = 33 + k
    line = [f"GVA_{s}" if s != "GDP" else "GDP_REAL_P", NAMES.get(s, "Рост ВВП, % г/г"), "", "", "", "", ""]
    for i, q in enumerate(QUARTERS):
        if i < 4:
            line.append("")
        else:
            c, p = QCOL[q], QCOL[QUARTERS[i - 4]]
            line.append(f"=IFERROR(({c}{r}-{p}{r})/{p}$43*100;\"\")")
    contrib.append(line)
out["B1_REAL!A45:BK57"] = contrib

# 5. Section O split (input method for non-market output): real defence GVA follows military headcount
# (B4 MIL_N), real public administration follows civilian staff; nominal GVA = pay fund (+ ESV).
staff = pd.read_csv(Path(__file__).resolve().parents[1] / "data" / "external" / "sector_labour_m.csv")
staff = staff[staff.code == "STAFF_O"].assign(y=lambda d: d.month.str[:4]).groupby("y").value
adm = {y: round(float(v), 1) for y, v in staff.mean().items()}
adm_months = staff.count()
hist_o = g["O"].drop("2022").loc["2016":"2025"]
lo, hi = round(float(hist_o.min()), 1), round(float(hist_o.max()), 1)
r = O_ROW
LO = num(lo).replace('−', '-')
B4Q = {"D": ("D", "G"), "E": ("H", "K"), "F": ("L", "O"), "G": ("P", "S")}  # B4 quarter columns of each year
q4 = lambda c, row, f="SUM": f"{f}(B4_LABOUR!{B4Q[c][0]}{row}:{B4Q[c][1]}{row})"
pc = dict(zip("EFG", "DEF"))
ADM_LAST = max(y for y in adm if adm_months[y] >= 6)
sec = [["5. Госуправление и оборона (раздел O): оборона и гражданское управление отдельно"],
       ["Код", "Показатель", "Уравнение / единицы", 2025, 2026, 2027, 2028, "Комментарий"],
       ["MIL_NY", "Численность военных, среднее за год", "тыс. человек, B4_LABOUR строка 17"] +
       [f"={q4(c, 17, 'AVERAGE')}" for c in "DEFG"] +
       ["сценарий SCENARIOS 110–113; история — оценка (1 млн), Госстат численность не публикует"],
       ["ADM_N", "Гражданские работники госуправления", "тыс. человек, среднеучётная (Госстат, раздел O)"] +
       [adm["2025"]] + [adm[y] if y <= ADM_LAST else f"={pc[c]}{r['ADM_N']}*(1+{C('O','ADM_G')}/100)"
                        for c, y in zip("EFG", ["2026", "2027", "2028"])] +
       [f"2026 — среднее за {adm_months['2026']} мес.; дальше COEFS GVA_O_ADM_G"],
       ["DEF_G", "Оборона: реальный рост", "рост численности военных, % г/г", ""] +
       [f"=({c}{r['MIL_NY']}/{pc[c]}{r['MIL_NY']}-1)*100" for c in "EFG"] +
       ["нерыночный выпуск по затратам: в постоянных ценах растёт вместе с занятыми"],
       ["ADM_G", "Госуправление: реальный рост", "рост штата, % г/г",
        round((adm["2025"] / adm["2024"] - 1) * 100, 1)] +
       [f"=({c}{r['ADM_N']}/{pc[c]}{r['ADM_N']}-1)*100" for c in "EFG"] + ["традиционно, через занятых и зарплаты"],
       ["DEF_NOM_G", "Оборона: номинальный рост", "рост фонда довольствия (B4 строка 47), % г/г", ""] +
       [f"=({q4(c, 47)}/{q4(pc[c], 47)}-1)*100" for c in "EFG"] + ["численность × выплата на одного (с боевыми)"],
       ["ADM_NOM_G", "Госуправление: номинальный рост", "(1 + штат) × (1 + оплата гражданских бюджетников, B4 строка 43) − 1", ""] +
       [f"=((1+{c}{r['ADM_G']}/100)*{q4(c, 43)}/{q4(pc[c], 43)}-1)*100" for c in "EFG"] + [""],
       ["DEF_SH", "Доля обороны в номинальной ВДС раздела O", "2025 — COEFS; дальше по номинальному росту частей",
        f"={C('O','DEF_SH')}"] +
       [f"={pc[c]}{r['DEF_SH']}*(1+{c}{r['DEF_NOM_G']}/100)/({pc[c]}{r['DEF_SH']}*(1+{c}{r['DEF_NOM_G']}/100)"
        f"+(1-{pc[c]}{r['DEF_SH']})*(1+{c}{r['ADM_NOM_G']}/100))" for c in "EFG"] +
       ["веса прошлого года: с концом войны доля обороны падает"],
       ["GVA_O", "Раздел O: реальный рост", "доля обороны прошлого года × оборона + остальное × госуправление",
        round(float(g.loc["2025", "O"]), 1)] +
       [f"={pc[c]}{r['DEF_SH']}*{c}{r['DEF_G']}+(1-{pc[c]}{r['DEF_SH']})*{c}{r['ADM_G']}" for c in "EFG"] +
       ["идёт в строку 27; 2025 — факт Госстата"],
       ["O_CHK", "Проверка логики", f"история 2016–2025 без 2022: от {num(lo)} до {num(hi)}%", ""] +
       [f"=IF(AND({c}{r['GVA_O']}>={LO};{c}{r['GVA_O']}<={num(hi)});\"OK\";IF(AND({c}{r['ADM_G']}>={LO};"
        f"{c}{r['ADM_G']}<={num(hi)});\"OK: численность военных (сценарий)\";\"ВНИМАНИЕ: штат госуправления\"))" for c in "EFG"] +
       ["выход за коридор, объяснённый численностью военных из сценария (демобилизация, мобилизация), — OK; "
        "ВНИМАНИЕ, только если вне коридора и госуправление"]]
assert len(sec) == O_ROW["O_CHK"] - 58
out[f"B1_REAL!A59:H{O_ROW['O_CHK']}"] = sec

json.dump(out, sys.stdout, ensure_ascii=False)
