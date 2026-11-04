"""ANNUAL sheet fixes (04.11.2026): anchors that had no forecast or a wrong concept, and a comment
column that explains every gap on the sheet.

- POP: government-controlled territory (history in data/external/population_controlled.csv);
  forecast = last quarter + migrants and foreign workers from B4_LABOUR + natural change (COEFS POP_NAT).
- GFCF: forecast = the same quarter a year ago x growth of real GFCF after the import squeeze
  (B2_DEMAND row 61) x growth of the GDP deflator (ANCHORS row 9).
- CFC: World Bank to 2021; from 2022 nominal GDP x the 2017-2021 share (COEFS CFC_SH).
- ANNUAL row 3 says fact / forecast per year; column T explains rows with gaps or estimates.

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators). --coefs is accepted
(scripts/recalc.py passes it) and changes nothing: every cell here is a rule, not a fact.
"""
import json
import sys

FIRST = 5
CODES = ["GDP_REAL", "GDP_REAL_P", "GDP_REAL_E", "GDP_NOM", "DEFL", "CPI_YOY", "PPI_YOY", "FX_AVG", "FX_EOP",
         "NBU_RATE", "LOAN_RATE", "DEP_RATE", "POP", "EMPL", "UNEMP", "WAGE_NOM", "EXP_USD", "IMP_USD", "TRADE_BAL",
         "RES_USD", "GFCF", "CFC", "BUDGET_DEF", "FIN_NEED_USD", "FIN_RECEIVED_USD", "FIN_GAP_USD", "DEBT_GDP",
         "ELEC_CONS", "FREIGHT"]
R = {c: FIRST + i for i, c in enumerate(CODES)}
QUARTERS = [f"{y}Q{q}" for y in range(2015, 2029) for q in range(1, 5)]
FIRST_FC = QUARTERS.index("2026Q3")
CFC_FROM = QUARTERS.index("2022Q1")

POP_NAT = -0.08    # mln a quarter: 2024 births ~0.18 mln, deaths ~0.50 mln a year
CFC_SH = 0.1272    # CFC / nominal GDP, sum 2017-2021 (World Bank CFC, Gosstat GDP)
COEF_ROW = {"POP_NAT": 257, "CFC_SH": 258}


def col(i: int) -> str:
    """0-based column index -> letters."""
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


A = lambda k: col(7 + k)        # ANCHORS / B2_DEMAND: H = 2015Q1
B4 = lambda k: col(3 + k - 40)  # B4_LABOUR: D = 2025Q1
num = lambda x: f"{x:g}".replace(".", ",")

out = {}
out[f"COEFS!A{COEF_ROW['POP_NAT']}:L{COEF_ROW['CFC_SH']}"] = [
    ["POP_NAT", "ANCHORS", "POP", "NAT", POP_NAT, "", "", "2024", "оценка", "", "2026-11-04",
     "Естественная убыль населения подконтрольной территории за квартал: рождений ~0,18 млн, смертей ~0,50 млн в год (2024). "
     "Оценка Claude (млн человек за квартал)"],
    ["CFC_SH", "ANCHORS", "CFC", "SH", CFC_SH, "", "", "2017–2021", "расчёт", "", "2026-11-04",
     "Износ основного капитала / номинальный ВВП, сумма 2017–2021 (износ — Всемирный банк, ВВП — Госстат). "
     "Оценка износа с 2022, пока нет данных; разрушения войны сюда не входят (доля)"],
]

# POP forecast: migrants (B4 row 14) and foreign workers (B4 row 16) are thousand people a quarter
for k in range(FIRST_FC, len(QUARTERS)):
    out[f"ANCHORS!{A(k)}{R['POP']}"] = [[
        f"={A(k - 1)}{R['POP']}+(B4_LABOUR!{B4(k)}14+B4_LABOUR!{B4(k)}16)/1000+COEFS!$E${COEF_ROW['POP_NAT']}"]]

# GFCF forecast: nominal = same quarter a year ago x real growth (after the import squeeze) x deflator growth
for k in range(FIRST_FC, len(QUARTERS)):
    c, p = A(k), A(k - 4)
    out[f"ANCHORS!{c}{R['GFCF']}"] = [[
        f"={p}{R['GFCF']}*B2_DEMAND!{c}61/B2_DEMAND!{p}61*{c}{R['DEFL']}/{p}{R['DEFL']}"]]

# CFC from 2022: share of nominal GDP
for k in range(CFC_FROM, len(QUARTERS)):
    c = A(k)
    out[f"ANCHORS!{c}{R['CFC']}"] = [[f"={c}{R['GDP_NOM']}*COEFS!$E${COEF_ROW['CFC_SH']}"]]

# ANNUAL row 3: fact / forecast by year (SCENARIOS C4 = last fact quarter)
out["ANNUAL!D3:R3"] = [["Период"] + [
    f'=IF({col(4 + i)}$4<VALUE(LEFT(SCENARIOS!$C$4;4));"факт";IF({col(4 + i)}$4=VALUE(LEFT(SCENARIOS!$C$4;4));'
    f'IF(RIGHT(SCENARIOS!$C$4;1)="4";"факт";"факт + прогноз");"прогноз"))' for i in range(14)]]

# rows 6-7 (Andrey 04.11.2026: "зачем 3 одинаковых строки ... добавить реальный ВВП %"): GDP by production and by
# expenditure equal GDP_REAL by construction, so row 6 shows real GDP growth and row 7 (control copy) is hidden by
# sheet/annual_format.py. Rows are not deleted: ANNUAL rows stay aligned with ANCHORS rows 5-31 for the SUMMARY paste.
out["ANNUAL!A5:D7"] = [["=ANCHORS!A5", "=ANCHORS!B5", "млн грн, цены 2021 года", "=ANCHORS!E5"],
                       ["GDP_REAL_G", "Реальный ВВП, рост", "% г/г", "год к году"],
                       ["=ANCHORS!A7", "=ANCHORS!B7", "млн грн, цены 2021 года", "=ANCHORS!E7"]]
out["ANNUAL!E6:R6"] = [[""] + [f'=IFERROR({col(4 + i)}5/{col(3 + i)}5*100-100;"")' for i in range(1, 14)]]

NOTES = {
    "GDP_REAL": "Цены 2021 года: в 2021 реальный ВВП равен номинальному. Год = сумма четырёх кварталов (ANCHORS строка 5), "
                "поэтому рост может отличаться от годовой цифры Госстата на 0,1–0,2 п.п.",
    "GDP_REAL_P": "Рост реального ВВП к прошлому году = строка 5. Код строки на ANCHORS — GDP_REAL_P (ВВП по производству, "
                  "он равен строке 5), здесь вместо уровня показан рост",
    "GDP_REAL_E": "Скрытая контрольная строка. С 03.11.2026 равен ВВП по производству по построению: импорт — замыкающая статья (B2_DEMAND раздел 6). "
                  "В истории Госстат публикует ВВП одной цифрой, расхождение методов сидит в «запасах и статистическом расхождении»",
    "PPI_YOY": "Прогноз ИЦП годовой (B3_PRICES, годовая часть): рост года ставится во все кварталы",
    "POP": "Подконтрольная территория, млн. До 2021 — Госстат без Крыма и Севастополя; 2022–2026Q2 — оценки демографов (±1 млн, "
           "data/external/population_controlled.csv). Прогноз: прошлый квартал + миграция и иностранные рабочие (B4_LABOUR строки 14, 16) "
           "+ естественная убыль (COEFS POP_NAT). Прогноз падает медленнее, чем в 2023–2025 (−1,5 млн в год): миграция в SCENARIOS "
           "ниже фактического выезда. Раньше здесь был ряд Всемирного банка по всей Украине (рос в 2025)",
    "EMPL": "2015–2021 — обследование рабочей силы Госстата (15–70 лет); 2022–2024 обследования нет, пусто; с 2025 — оценка B4_LABOUR. "
            "Разница уровней 2021 и 2025 — война, выезд и мобилизация, а не сбой ряда",
    "UNEMP": "Как занятые: 2022–2024 обследования нет; с 2025 — оценка B4_LABOUR",
    "WAGE_NOM": "Госстат; пропуски 2022–2024 из квартальных данных (MacroStat, лист Salary)",
    "GFCF": "Прогноз: тот же квартал год назад × рост реального ВНОК после сжатия импорта (B2_DEMAND строка 61) × рост дефлятора ВВП",
    "CFC": "До 2021 — Всемирный банк; с 2022 — оценка: номинальный ВВП × доля 2017–2021 (12,7%, COEFS CFC_SH). Разрушения войны не входят",
    "BUDGET_DEF": "2026: факт Казначейства по месяцам, остаток года поровну (B6_FISCAL раздел 5)",
    "FIN_NEED_USD": "Потребность считает B5_EXTERNAL с 2025; раньше не считалась",
    "FIN_GAP_USD": "Потребность − получено; > 0 покрывается резервами, импортом или курсом (B5_EXTERNAL раздел 7)",
    "DEBT_GDP": "Прогноз годовой (B6_FISCAL): одно значение на все кварталы года",
    "ELEC_CONS": "Всемирный банк до 2024 (вся Украина). Прогноза нет: ограничение по энергии B8_CAPACITY считает по мощности в ГВт",
    "FREIGHT": "Госстат до 2025. Прогноза нет: логистику B8_CAPACITY проверяет по пропускной способности портов",
}
out[f"ANNUAL!S4:S{FIRST + len(CODES) - 1}"] = [["Комментарий"]] + [[NOTES.get(c, "")] for c in CODES]

if __name__ == "__main__":
    json.dump(out, sys.stdout, ensure_ascii=False)
