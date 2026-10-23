"""Build the SCENARIOS rows and COEFS rows for tariff and metallurgy shocks (macromodel.blocks.shocks).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). The model links
are written by b1_payload (manufacturing, mining), b2_payload (exports) and
scenarios_q_payload (CPI in ANCHORS row 10). SCENARIOS needs at least 63 rows.
"""
import json
import sys

from macromodel import quarterly
from macromodel.blocks.shocks import COEF_FIRST, MET_ROW, SHOCKS, TARIFF_ROW, estimated

EST = estimated()


def coef_row(k, v, block, note):
    if k == "CPI_SPEED":  # estimated: 1 − coefficient on last quarter's CPI
        v, se = quarterly.cpi_speed()
        return [f"SHOCK_{k}", block, "SHOCK", k, round(v, 2), round(se, 2), round(v / se, 1), "2011–2025",
                quarterly.METHOD, "", "2026-10-23",
                "Инерция инфляции: доля разрыва между прошлым кварталом и годовой моделью B3, закрываемая за квартал. "
                "Оценка: ИПЦ г/г на курс, зарплату и ИПЦ прошлого квартала (1 − коэффициент при нём). Тарифы добавляются сразу"]
    if k in EST:
        v, se, period, method, note = EST[k]
        return [f"SHOCK_{k}", block, "SHOCK", k, round(v, 2), round(se, 2) if se else "", round(v / se, 1) if se else "",
                period, method, "", "2026-10-23", note]
    return [f"SHOCK_{k}", block, "SHOCK", k, v, "", "", "", "калибровка", "", "2026-10-23", note]


out = {}
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(SHOCKS) - 1}"] = [coef_row(k, *spec) for k, spec in SHOCKS.items()]
choose = lambda cols: f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{';'.join(f'{c}{MET_ROW}' for c in cols)})"
out[f"SCENARIOS!A{TARIFF_ROW - 2}:N{MET_ROW}"] = [
    ["Тарифы и отраслевые шоки"],
    ["Параметр", "Единицы"] + [f"={c}38" for c in "CDEFGHIJKL"],
    ["Повышение коммунальных тарифов (для всех сценариев)", "% в квартал повышения, средний по ЖКУ"],
    [f"Как считается: ИПЦ г/г вырастает на вес ЖКУ в ИПЦ (COEFS!E{COEF_FIRST}) × повышение, в квартал повышения и три следующих "
     "(пока повышение в базе г/г). Если ИПЦ квартала задан в строке 51, тариф в этом квартале уже считается включённым."],
    [""],
    ["Отраслевые шоки по годам"],
    ["Параметр", "Единицы", "База", "", "", "Пессимистичный", "", "", "Оптимистичный", "", "", "Активный"],
    ["", ""] + [2026, 2027, 2028] * 4,
    ["Металлургия: загрузка мощностей, средняя за год", "% от уровня 2025"] + [100] * 9
    + [choose(cols) for cols in ("CFI", "DGJ", "EHK")],
]
if "--coefs" in sys.argv:  # SCENARIOS rows hold the user's shock inputs: rewrite only on a fresh frame
    out = {k: v for k, v in out.items() if k.startswith("COEFS")}
json.dump(out, sys.stdout, ensure_ascii=False)
