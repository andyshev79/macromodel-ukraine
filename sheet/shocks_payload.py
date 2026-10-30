"""Build the SCENARIOS rows and COEFS rows for tariff and metallurgy shocks (macromodel.blocks.shocks).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). The model links
are written by b1_payload (manufacturing, mining), b2_payload (exports) and
cpi_blocks_payload (CPI by NBU blocks, B3_PRICES section 4). Rows: macromodel.scenario_layout.

Fuel (2026-10-29, Andrey): the only SCENARIOS row is the growth of fuel prices to the previous quarter; B3_PRICES
section 6 turns it into the y/y of row 45 (cpi_blocks_payload).
"""
import json
import sys

from macromodel import quarterly
from macromodel import scenario_layout as SL
from sheet.scenarios_quarterly_payload import ROW as _QROW
BRENT_R = _QROW["BRENT"]  # quarterly Brent rows (Base, Pess, Opt, active)
from macromodel.blocks.shocks import (COEF_FIRST, FUEL_COEF_ROW, FUEL_NORM_ROW, FUEL_QOQ, MET_ROW, SHOCKS, TARIFF_ROW,
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
TARIFF_GAP = 60  # % backlog of household utility tariffs to cost recovery, Claude estimate 2026-10-30 (see the note row)
choose = lambda cols: f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{';'.join(f'{c}{MET_ROW}' for c in cols)})"
out[f"SCENARIOS!A{TARIFF_ROW - 2}:L{TARIFF_ROW + 1}"] = [
    ["Тарифы и отраслевые шоки"],
    ["Параметр", "Единицы"] + [f"={c}{SL.Q_HEAD}" for c in "CDEFGHIJKL"],
    ["Повышение коммунальных тарифов (для всех сценариев)", "% в квартал повышения, средний по ЖКУ"],
    [f"Как считается: ИПЦ г/г вырастает на вес ЖКУ в ИПЦ (COEFS!E{COEF_FIRST}) × повышение, в квартал повышения и три следующих "
     f"(пока повышение в базе г/г). Если ИПЦ квартала задан в строке {SL.CPI_Q}, тариф в этом квартале уже считается включённым. "
     f"Повышения копятся до отмены военного положения (квартал после прекращения огня) и потом идут не больше 25% в год (B3_PRICES раздел 7). "
     f"Оценка Claude 30.10.2026: отставание тарифов населения от экономически обоснованного уровня около {TARIFF_GAP}% "
     "(газ 7,96 грн/м³ с 2022 года — около +100% к импортному паритету; электроэнергия 4,32 грн/кВт·ч с июня 2024 года — около +60%; "
     "отопление и горячая вода заморожены с 2021 года — около +55%; вода — около +25%; веса внутри ЖКУ 0,25 / 0,30 / 0,30 / 0,15), "
     "введено одной суммой в 2026Q3."],
]
# the annual SCENARIOS rows are typed in the annual table since 2026-10-29 (labels: scenarios_quarterly_payload)
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
QC = "CDEFGHIJKL"  # SCENARIOS 2026Q3..2028Q4
# one input row (Andrey, 29.10: fuel has no seasonality worth showing here); the year-ago q/q, the y/y and the q/q
# results are computed in B3_PRICES section 6 (cpi_blocks_payload)
out[f"SCENARIOS!A{SL.FUEL_HEAD}:L{SL.FUEL_QQ + 1}"] = [
    ["Цены топлива (для всех сценариев)", "Единицы"] + [f"={c}{SL.Q_HEAD}" for c in QC],
    ["Топливо: прирост цен к прошлому кварталу (ввод)", "% кв/кв, конец квартала", FUEL_QOQ["2026Q3"]] + [""] * 9,
    [f"Как считается: вводите прирост цен топлива к прошлому кварталу; 2026Q3 — факт (MacroStat, ИПЦ «топливо и масла»). "
     f"B3_PRICES раздел 6 переводит его в г/г: (1 + г/г прошлого квартала) × (1 + ввод) / (1 + кв/кв год назад) − 1, это идёт в "
     f"блок «топливо» (B3_PRICES строка 45). Пустой квартал = уравнение B3: 3,61 + 0,46 × рост нефти Brent (строки "
     f"{BRENT_R}–{BRENT_R + 3}) + 1,04 × девальвация."],
]
if "--coefs" in sys.argv:  # SCENARIOS rows hold the user's shock inputs: rewrite only on a fresh frame
    out = {k: v for k, v in out.items() if k.startswith("COEFS")}
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
