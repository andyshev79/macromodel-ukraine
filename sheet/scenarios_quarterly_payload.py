"""Scenario inputs by quarter (2026-10-28): the quarterly block of SCENARIOS is the main input.

Andrey asked to move all scenario assumptions to quarters; where only annual data exist the row holds one
value per year (the cells of the year are merged). The annual table (rows 16-33 and the annual rows below it)
becomes formulas over the quarters, so every annual block works as before:
- levels (capacity, ports, prices, shares): average of the quarters; 2026 = (2 x first half + Q3 + Q4) / 4;
- end-of-year values (Fed rate): the fourth quarter; Brent and EUR/USD in 2026: the fourth quarter (as before);
- flows (financing, migration, mobilisation, foreign workers): sum of the quarters; 2026 = fact or 2 x (Q3 + Q4).

New block layout (rows from FIRST): A name, B units, C first half 2026 (fact or estimate), D:M = 2026Q3..2028Q4,
N how the year is built, O comment. Four rows per parameter: Base, Pessimistic, Optimistic, active (CHOOSE by C3).
Parameters that already had quarterly rows (financing 40-42, strikes 43-45, people flows 94-105) stay where they are;
their annual rows become formulas over them.

--inputs FILE: also write the starting values (a JSON snapshot of the current sheet), filled by the logic of the
ceasefire quarter (row 16): before it the war level, from it the rest of the year so that the year averages
Andrey's annual value. Without --inputs only labels and formulas are written (safe to rerun).
--merges: print the batchUpdate requests that merge the year cells of the annual-only parameters.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys

FIRST = 202
QLAB = ["2026Q3", "2026Q4"] + [f"{y}Q{q}" for y in (2027, 2028) for q in (1, 2, 3, 4)]
QCOLS = "DEFGHIJKLM"  # 2026Q3..2028Q4 in the new block; C = first half 2026
YEARS = (2026, 2027, 2028)
YCOLS = {2026: ("C", "E"), 2027: ("F", "I"), 2028: ("J", "M")}  # first and last column of each year in the new block
SC_NAMES = ("База", "Пессимистичный", "Оптимистичный")
ANN = {"base": "CDE", "pess": "FGH", "opt": "IJK"}  # annual table columns per scenario
ANN_COLS = ["CDE", "FGH", "IJK"]
choose = lambda c, r: f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{c}{r};{c}{r + 1};{c}{r + 2})"

# code, annual row, name, units, aggregation, fill rule, comment
# rules: war_up / war_down follow the ceasefire quarter, flat = the annual value in every quarter,
# year = one value per year (annual-only data)
PARAMS = [
    ("CAP", 18, "Доступная мощность энергосистемы в пик", "ГВт", "avg", "war_up",
     "До квартала прекращения огня — уровень войны, дальше — восстановление; B1 считает энергетику, добычу, переработку и услуги по кварталам"),
    ("PORTS", 19, "Пропускная способность морских портов", "млн т в год (в годовом выражении)", "avg", "war_up",
     "1 пол. 2026 — факт 42,4 млн т × 2 (GMK Center); B1 считает транспорт и добычу по кварталам"),
    ("DEF", 21, "Расходы на оборону", "% ВВП", "avg", "war_down", "1 пол. 2026 — факт 35,7% (Казначейство, функция 0200)"),
    ("WHEAT", 25, "Цена пшеницы", "USD/т", "avg", "flat", "Всемирный банк, CMO (HRW)"),
    ("STEEL", 26, "Цена стали (заготовка)", "USD/т", "avg", "flat", "НБУ, прогноз заготовки FOB Украина"),
    ("TTF", 27, "Цена газа TTF", "EUR/МВт·ч", "avg", "flat", "ЕЦБ, прогноз сентябрь 2026"),
    ("EA_GDP", 28, "Рост ВВП еврозоны", "%", "avg", "flat", "ЕЦБ: годовые прогнозы, по кварталам — то же значение"),
    ("HICP", 29, "Инфляция еврозоны", "%", "avg", "flat", "ЕЦБ: годовые прогнозы"),
    ("FED", 30, "Ставка ФРС", "%, конец квартала", "end", "flat", "ФРС SEP; год = 4 кв."),
    ("SH_MIGR", 32, "Доля украинских мигрантов в рабочей силе", "доля 0–1", "year", "year", "Только годовая оценка"),
    ("SH_GUEST", 33, "Доля иностранных рабочих в рабочей силе", "доля 0–1", "year", "year", "Только годовая оценка"),
    ("MET", 63, "Металлургия: загрузка мощностей", "% от уровня 2025", "avg", "war_up",
     "1 пол. 2026 — факт: промпроизводство 24–25 на уровне 2025 (−2,4% и +4,9% г/г); B1 считает металлургию по кварталам"),
    ("DESHADOW", 71, "Детенизация зарплат", "п.п. к росту средней зарплаты", "year", "year", "Только годовая оценка"),
    ("BRENT", 78, "Цена нефти Brent", "USD/барр.", "q4", "flat", "2026 в годовой таблице — 4 кв. (как раньше)"),
    ("PEACE_C", 123, "Эффект мира: снижение нормы сбережений", "п.п. к росту потребления домохозяйств", "year", "year",
     "Годовая добавка в B2_DEMAND"),
    ("PEACE_I", 124, "Эффект мира: восстановление", "п.п. к росту инвестиций (ВНОК)", "year", "year", "Годовая добавка в B2_DEMAND"),
    ("RECON", 131, "Деньги на восстановление", "млрд USD в год", "year", "year", "Годовая сумма для B9_CONSTRUCTION"),
    ("SUNOIL", 137, "Цена подсолнечного масла FOB Чёрное море", "USD/т", "avg", "flat", "B10_AGRO"),
    ("WEATHER", 138, "Погода: отклонение урожайности от среднего", "%", "year", "year", "Урожай — один раз в год"),
    ("AREA", 139, "Посевная площадь к 2026", "%", "year", "year", "Урожай — один раз в год"),
    ("EDU", 194, "Фонд оплаты труда образования и здравоохранения", "% рост за год", "year", "year", "Годовой бюджет"),
    ("EURUSD", 199, "EUR/USD, средний", "долларов за 1 евро", "q4", "flat", "2026 в годовой таблице — 4 кв. (как раньше)"),
]
ROW = {p[0]: FIRST + 3 + 4 * i for i, p in enumerate(PARAMS)}  # first (Base) row of each parameter
LAST_ROW = FIRST + 3 + 4 * len(PARAMS) - 1
FACT_H1 = {"PORTS": 84.8, "DEF": 35.7, "MET": 100}  # first half 2026, fact
STOP_MONTH = {"PORTS": 8, "MET": 9}  # 2026: ports stopped in August, metallurgy in September (Andrey, 28.10)
# Quarter values set from facts, over the fill above (scenario index 0 Base, 1 Pess, 2 Opt -> {quarter: value}).
# Ports, mln t a year at the quarter's pace: Greater Odesa almost closed since the attacks of 22.07, the Danube carries
# ~1.25 mln t a month (August 2026: 1.67 mln t for all ports, Danube 1.24; Danube maximum ~1.3) -> ~20 mln t a year;
# 2026Q3 = July ~5.5 + August 1.67 + September ~1.7 mln t. Metallurgy stopped from September until the ceasefire (~5% left).
QOVR = {
    # after the ceasefire the ports come back over two quarters (demining, insurance, repairs), not at once
    "PORTS": {0: {"2026Q3": 35.5, "2026Q4": 20, "2027Q1": 20, "2027Q2": 20, "2027Q3": 60, "2027Q4": 85},
              1: {"2026Q3": 35.5, "2026Q4": 17, "2027Q1": 15, "2027Q2": 15, "2027Q3": 15, "2027Q4": 15,
                  "2028Q1": 55, "2028Q2": 75},
              2: {"2026Q3": 35.5, "2026Q4": 20, "2027Q1": 70, "2027Q2": 90}},
    "MET": {0: {"2026Q3": 68.3, "2026Q4": 5, "2027Q1": 5, "2027Q2": 5, "2027Q3": 25, "2027Q4": 35},
            1: {"2026Q3": 68.3, "2026Q4": 5, "2027Q1": 5, "2027Q2": 5, "2027Q3": 5, "2027Q4": 5},
            2: {"2026Q3": 68.3, "2026Q4": 5}},
}
AGG_TEXT = {"avg": "среднее кварталов; 2026 = (2 × 1 пол. + 3 кв. + 4 кв.) / 4", "end": "4 кв.",
            "q4": "2026 — 4 кв., дальше среднее кварталов", "year": "одно значение на год"}

# quarterly rows that already exist (columns C:L = 2026Q3..2028Q4): annual row -> (first scenario row, aggregation)
OLD_Q = {17: (43, "avg"), 20: (40, "fin"), 22: (94, "flow"), 23: (98, "flow"), 31: (102, "flow")}
OLD_YC = {2026: ("C", "D"), 2027: ("E", "H"), 2028: ("I", "L")}


def annual_formula(agg: str, r: int, y: int) -> str:
    c0, c1 = YCOLS[y]
    if agg == "year":
        return f"=IF({c0}{r}=\"\";\"\";{c0}{r})"
    if agg == "end" or (agg == "q4" and y == 2026):
        return f"={c1}{r}"
    if y == 2026:
        return f"=(2*C{r}+D{r}+E{r})/4"
    return f"=AVERAGE({c0}{r}:{c1}{r})"


def old_annual_formula(agg: str, r: int, y: int) -> str:
    c0, c1 = OLD_YC[y]
    if agg == "avg":
        return f"=AVERAGE({c0}{r}:{c1}{r})"
    if agg == "fin" and y == 2026:
        return f"=SUM(ANCHORS!$AZ$29:$BA$29)+{c0}{r}+{c1}{r}"
    if agg == "flow" and y == 2026:
        return f"=2*({c0}{r}+{c1}{r})"
    return f"=SUM({c0}{r}:{c1}{r})"


def build() -> dict:
    out = {}
    rows = [["Сценарные допущения по кварталам — основной ввод (с 28.10.2026)"],
            ["Вводите значения здесь, по кварталам. Годовая таблица вверху (строки 16–33) и годовые строки ниже теперь считаются "
             "из этих кварталов и меняются сами. Где есть только годовые данные, ячейки года объединены: одно значение на год. "
             "Столбец C — первое полугодие 2026 (факт, где он известен). Финансирование, удары и потоки людей вводятся в своих "
             "квартальных строках (40–45, 94–105)."],
            ["Параметр", "Единицы", "1 пол. 2026"] + QLAB + ["Как считается год", "Комментарий"]]
    for code, _, name, unit, agg, rule, note in PARAMS:
        r = ROW[code]
        for k, sc in enumerate(SC_NAMES):
            rows.append([f"{name} — {sc}", unit] + [""] * 11 + [AGG_TEXT[agg] if k == 0 else "", note if k == 0 else ""])
        cols = ["C", "F", "J"] if agg == "year" else ["C"] + list(QCOLS)
        act = {c: choose(c, r) for c in cols}
        rows.append([f"{name} — активный", unit] + [act.get(c, "") for c in "CDEFGHIJKLM"] + ["", ""])
    out[f"SCENARIOS!A{FIRST}:O{LAST_ROW}"] = rows
    # labels in the input rows are written above; values come only with --inputs, so blank them out of this range
    for code, *_ in PARAMS:
        r = ROW[code]
        for k in range(3):
            del rows[r - FIRST + k][2:13]
            rows[r - FIRST + k][2:2] = [None] * 11
    # the annual table: formulas over the quarters
    for code, ar, *_rest in PARAMS:
        agg, r = _rest[2], ROW[code]
        out[f"SCENARIOS!C{ar}:K{ar}"] = [[annual_formula(agg, r + k, y) for k in range(3) for y in YEARS]]
    for ar, (r, agg) in OLD_Q.items():
        out[f"SCENARIOS!C{ar}:K{ar}"] = [[old_annual_formula(agg, r + k, y) for k in range(3) for y in YEARS]]
    out["SCENARIOS!A13"] = [["Годовые значения считаются из квартальных строк (ввод — строки 202 и ниже, 40–45 и 94–105). "
                             "Колонки «Активный» выбирают значения сценария из C3."]]
    return out


# ---------- starting values (only with --inputs) ----------
def ceasefire(q: str) -> tuple:
    """'2027Q3' -> (2027, 3); 'нет' or '—' -> (None, None)."""
    q = str(q).strip()
    return (int(q[:4]), int(q[-1])) if len(q) == 6 and q[4] == "Q" else (None, None)


def fill_war(annual: list, cf: tuple, rule: str, h1, stop=None) -> list:
    """C (first half 2026) + 10 quarters for one scenario. annual = [2026, 2027, 2028].
    stop = month of 2026Q3 from which the war level applies (earlier months stay at the first-half level)."""
    a26, a27, a28 = annual
    h1 = a26 if h1 is None else h1
    q3 = a26 if stop is None else round(((stop - 7) * h1 + (10 - stop) * a26) / 3, 1)
    q = {"2026H1": h1, "2026Q3": q3, "2026Q4": a26}  # the annual 2026 value is read as the current (second half) level
    prev = a26
    for y, a in ((2027, a27), (2028, a28)):
        cy, cq = cf
        if cy == y and cq > 1:
            n_pre = cq - 1
            post = (4 * a - n_pre * prev) / (4 - n_pre)
            ok = post >= prev if rule == "war_up" else post <= prev
            vals = [prev] * n_pre + [round(post, 2)] * (4 - n_pre) if ok else [a] * 4
        else:
            vals = [a] * 4
        for i, v in enumerate(vals):
            q[f"{y}Q{i + 1}"] = v
        prev = vals[-1]
    return [q["2026H1"]] + [q[l] for l in QLAB]


def inputs(snap: dict) -> dict:
    ann = {int(k): v for k, v in snap["annual"].items()}
    qold = {int(k): v for k, v in snap["quarterly"].items()}
    cfs = [ceasefire(x) for x in snap["ceasefire"]]  # Base, Pess, Opt
    out = {}
    for code, ar, name, unit, agg, rule, note in PARAMS:
        r = ROW[code]
        vals = []
        for k in range(3):
            a = ann[ar][3 * k: 3 * k + 3]
            if rule == "year":
                line = [a[0], None, None, a[1], None, None, None, a[2], None, None, None]
            elif rule == "flat":
                line = [a[0], a[0], a[0]] + [a[1]] * 4 + [a[2]] * 4
            else:
                line = fill_war(a, cfs[k], rule, FACT_H1.get(code), STOP_MONTH.get(code))
                for q, v in QOVR.get(code, {}).get(k, {}).items():
                    line[1 + QLAB.index(q)] = v
            vals.append(["" if v is None else v for v in line])
        out[f"SCENARIOS!C{r}:M{r + 2}"] = vals
    # existing quarterly rows: people flows by the annual values and the ceasefire quarter; financing scaled to the annual sum
    for ar, (r0, agg) in OLD_Q.items():
        if agg == "avg":
            continue  # strikes: quarters are already Andrey's inputs
        for k in range(3):
            a = ann[ar][3 * k: 3 * k + 3]
            old = qold[r0 + k]
            if agg == "fin":
                line = old[:2] + [round(v * a[1] / sum(old[2:6]), 1) if sum(old[2:6]) else a[1] / 4 for v in old[2:6]] + \
                       [round(v * a[2] / sum(old[6:10]), 1) if sum(old[6:10]) else a[2] / 4 for v in old[6:10]]
            else:
                line = [a[0] / 4] * 2
                for y, ay in ((2027, a[1]), (2028, a[2])):
                    cy, cq = cfs[k]
                    if ar == 23 and cy == y and cq > 1 and ay >= 0:  # mobilisation stops with the ceasefire
                        line += [ay / (cq - 1)] * (cq - 1) + [0] * (5 - cq)
                    else:
                        line += [ay / 4] * 4
                line = [round(v, 2) for v in line]
            out[f"SCENARIOS!C{r0 + k}:L{r0 + k}"] = [line]
    return out


PROTECTED = {p[1] for p in PARAMS} | set(OLD_Q)  # annual rows whose C:K are formulas over the quarters


def protect(out: dict) -> dict:
    """Blank (None = skipped by the Sheets API) the annual C:K cells of PROTECTED rows in other payloads' SCENARIOS
    defaults, so a fresh-frame run of a block payload cannot overwrite the formulas over the quarters."""
    import re
    for rng, vals in out.items():
        m = re.fullmatch(r"SCENARIOS!([A-Z]+)(\d+)(?::[A-Z]+\d+)?", rng)
        if not m:
            continue
        c0, r0 = ord(m.group(1)) - 65, int(m.group(2))
        for i, row in enumerate(vals):
            if r0 + i in PROTECTED:
                for j in range(len(row)):
                    if 2 <= c0 + j <= 10:
                        row[j] = None
    return out


def merges(sheet_id: int = 2) -> list:
    req = []
    for code, *_rest in PARAMS:
        if _rest[3] != "year":
            continue
        r = ROW[code]
        for k in range(4):
            for c0, c1 in YCOLS.values():
                req.append({"mergeCells": {"mergeType": "MERGE_ALL", "range": {
                    "sheetId": sheet_id, "startRowIndex": r + k - 1, "endRowIndex": r + k,
                    "startColumnIndex": ord(c0) - 65, "endColumnIndex": ord(c1) - 64}}})
    return req


if __name__ == "__main__":
    if "--merges" in sys.argv:
        json.dump(merges(), sys.stdout, ensure_ascii=False)
        sys.exit()
    res = build()
    if "--inputs" in sys.argv:
        res.update(inputs(json.load(open(sys.argv[sys.argv.index("--inputs") + 1]))))
    json.dump(res, sys.stdout, ensure_ascii=False)
