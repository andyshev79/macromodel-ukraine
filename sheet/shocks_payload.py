"""Build the SCENARIOS rows and COEFS rows for tariff and metallurgy shocks (macromodel.blocks.shocks).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). The model links
are written by b1_payload (manufacturing, mining), b2_payload (exports) and
cpi_blocks_payload (CPI by NBU blocks, B3_PRICES section 4). Rows: macromodel.scenario_layout.

Fuel (2026-10-29, Andrey): the input is the growth of fuel prices to the previous quarter; the y/y that B3_PRICES
row 45 reads is (1 + y/y of the previous quarter) x (1 + input) / (1 + q/q a year ago) - 1. An empty quarter keeps the
B3 equation (y/y on Brent and devaluation); the q/q result row shows what q/q the equation gives.
"""
import json
import sys

from macromodel import quarterly
from macromodel import scenario_layout as SL
from sheet.scenarios_quarterly_payload import ROW as _QROW
BRENT_R = _QROW["BRENT"]  # quarterly Brent rows (Base, Pess, Opt, active)
from macromodel.blocks.shocks import (COEF_FIRST, FUEL_COEF_ROW, FUEL_NORM_ROW, FUEL_QOQ, FUEL_ROW, MET_ROW, SHOCKS, TARIFF_ROW,
                                      estimated, fuel)

EST = estimated()


def coef_row(k, v, block, note):
    if k == "CPI_SPEED":  # estimated: 1 − coefficient on last quarter's CPI
        v, se = quarterly.cpi_speed()
        return [f"SHOCK_{k}", block, "SHOCK", k, round(v, 2), round(se, 2), round(v / se, 1), "2011–2025",
                quarterly.METHOD, "", "2026-10-23",
                "Инерция инфляции: доля разрыва между прошлым кварталом и годовой моделью B3, закрываемая за квартал. "
                "Оценка: ИПЦ г/г на курс, зарплату и ИПЦ прошлого квартала (1 − коэффициент при нём). "
                "Не используется с 2026-10-24: ИПЦ считается по блокам НБУ (COEFS 108–126)"]
    if k in EST:
        v, se, period, method, note = EST[k]
        return [f"SHOCK_{k}", block, "SHOCK", k, round(v, 2), round(se, 2) if se else "", round(v / se, 1) if se else "",
                period, method, "", "2026-10-23", note]
    return [f"SHOCK_{k}", block, "SHOCK", k, v, "", "", "", "калибровка", "", "2026-10-23", note]


out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(SHOCKS) - 1}"] = [coef_row(k, *spec) for k, spec in SHOCKS.items()]
choose = lambda cols: f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{';'.join(f'{c}{MET_ROW}' for c in cols)})"
out[f"SCENARIOS!A{TARIFF_ROW - 2}:L{TARIFF_ROW + 1}"] = [
    ["Тарифы и отраслевые шоки"],
    ["Параметр", "Единицы"] + [f"={c}{SL.Q_HEAD}" for c in "CDEFGHIJKL"],
    ["Повышение коммунальных тарифов (для всех сценариев)", "% в квартал повышения, средний по ЖКУ"],
    [f"Как считается: ИПЦ г/г вырастает на вес ЖКУ в ИПЦ (COEFS!E{COEF_FIRST}) × повышение, в квартал повышения и три следующих "
     f"(пока повышение в базе г/г). Если ИПЦ квартала задан в строке {SL.CPI_Q}, тариф в этом квартале уже считается включённым."],
]
out[f"SCENARIOS!A{MET_ROW - 3}:N{MET_ROW}"] = [
    ["Отраслевые шоки по годам"],
    ["Параметр", "Единицы", "База", "", "", "Пессимистичный", "", "", "Оптимистичный", "", "", "Активный"],
    ["", ""] + [2026, 2027, 2028] * 4,
    ["Металлургия: загрузка мощностей, средняя за год", "% от уровня 2025"] + [100] * 9
    + [choose(cols) for cols in ("CFI", "DGJ", "EHK")],
]
F = fuel()
out[f"COEFS!A{FUEL_COEF_ROW}:L{FUEL_NORM_ROW}"] = [
    ["SHOCK_FUEL_W", "B3", "SHOCK", "FUEL_W", round(F["coef"], 3), round(F["se"], 3), round(F["coef"] / F["se"], 1), "2011–2025",
     quarterly.METHOD, round(F["r2"], 2), "2026-10-24",
     "ИПЦ г/г на курс, зарплату и цены топлива прошлого квартала (ИПЦ: топливо и масла): +10 п.п. к росту цен топлива "
     "дают +1 п.п. к ИПЦ через квартал. Через продукты: " + f"{F['food']:.2f}".replace(".", ",")
     + f" (t {F['food'] / F['food_se']:.1f})".replace(".", ",") + " — дорогое топливо для аграриев и перевозок. Не используется с 2026-10-24: топливо — блок ИПЦ (COEFS 108–126)"],
    ["SHOCK_FUEL_NORM", "B3", "SHOCK", "FUEL_NORM", round(F["norm"], 1), "", "", "2011–2025", "расчёт по данным", "", "2026-10-24",
     "Средний рост цен топлива 2011–2025 без 2022Q1–2023Q1, % г/г. Не используется с 2026-10-24 (ИПЦ по блокам НБУ)"],
]
QC, B3C = "CDEFGHIJKL", "EFGHIJKLMNO"  # SCENARIOS 2026Q3..2028Q4; B3_PRICES row 45 from 2026Q2 (E) to 2028Q4 (O)
QI, LAG, RES, QR = SL.FUEL_QQ, SL.FUEL_LAG, SL.FUEL, SL.FUEL_QQ_RES
lag = [FUEL_QOQ[q] for q in ("2025Q3", "2025Q4", "2026Q1", "2026Q2")] + [f"={QC[k - 4]}{QR}" for k in range(4, 10)]
out[f"SCENARIOS!A{SL.FUEL_HEAD}:L{QR + 1}"] = [
    ["Цены топлива (для всех сценариев)", "Единицы"] + [f"={c}{SL.Q_HEAD}" for c in QC],
    ["Топливо: прирост цен к прошлому кварталу (ввод)", "% кв/кв, конец квартала", FUEL_QOQ["2026Q3"]] + [""] * 9,
    ["Тот же квартал год назад, кв/кв (для сезонности)", "% кв/кв"] + lag,
    ["Топливо: бензин, дизель, газ для авто (ИПЦ «топливо и масла») — итог г/г", "% г/г, конец квартала"]
    + [f"=IF({c}{QI}=\"\";\"\";(1+B3_PRICES!{B3C[k]}45/100)*(1+{c}{QI}/100)/(1+{c}{LAG}/100)*100-100)" for k, c in enumerate(QC)],
    ["Топливо: итог кв/кв (ввод или уравнение)", "% кв/кв"]
    + [f"=IF({c}{QI}<>\"\";{c}{QI};(1+B3_PRICES!{B3C[k + 1]}45/100)/(1+B3_PRICES!{B3C[k]}45/100)*(1+{c}{LAG}/100)*100-100)"
       for k, c in enumerate(QC)],
    [f"Как считается: вводите прирост цен топлива к прошлому кварталу (строка {QI}); 2026Q3 — факт (MacroStat, ИПЦ «топливо и масла»). "
     f"Строка {LAG} — тот же квартал год назад: видно сезонность. Итог г/г (строка {RES}) = (1 + г/г прошлого квартала) × (1 + ввод) / "
     f"(1 + кв/кв год назад) − 1, он идёт в блок «топливо» B3_PRICES, строка 45. Пустой квартал = уравнение B3: 3,61 + 0,46 × рост "
     f"нефти Brent (строки {BRENT_R}–{BRENT_R + 3}) + 1,04 × девальвация; строка {QR} показывает, какой кв/кв из него получился."],
]
if "--coefs" in sys.argv:  # SCENARIOS rows hold the user's shock inputs: rewrite only on a fresh frame
    out = {k: v for k, v in out.items() if k.startswith("COEFS")}
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
