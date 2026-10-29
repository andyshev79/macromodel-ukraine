"""Build the cell contents of B10_AGRO, its COEFS rows and SCENARIOS rows (block B10).

Output: JSON {range: 2D list}, formulas in ru_RU syntax (";" separators).
"""
import json
import sys

from macromodel import scenario_layout as SL
from macromodel.blocks.agro import (CALIBRATED, COEF_FIRST, CROPS, FACT, GRAINS, NOW, ROW, SPRING, coef_rows, crops,
                                    history, sources)

num = lambda v, d=1: f"{v:.{d}f}".replace(".", ",").replace("-", "−")
fnum = lambda v, d=1: f"{v:.{d}f}".replace(".", ",")  # inside formulas
C = lambda code: f"COEFS!$E${ROW[code]}"
h = history()
c = crops()
pc = dict(zip("EFG", "DEF"))
ACT = dict(zip("EFG", "LMN"))

out = {}
rows = coef_rows()
out[f"COEFS!A{COEF_FIRST}:L{COEF_FIRST + len(rows) - 1}"] = [
    [r["code"], "B10", r["eq"], r["var"], float(r["coef"]), "", "", "", r["method"], "", "2026-10-25", r["note"]] for r in rows]

# SCENARIOS: sunflower oil price, weather and sown area (base / pessimistic / optimistic), active columns L:N
SUN, WEA, AREA = SL.SUNOIL, SL.WEATHER, SL.AREA  # SCENARIOS annual table, active columns L:N
act = lambda r: [f"=CHOOSE(MATCH($C$3;$A$8:$A$10;0);{a}{r};{b}{r};{c_}{r})" for a, b, c_ in ["CFI", "DGJ", "EHK"]]
# the annual SCENARIOS rows are typed in the annual table since 2026-10-29 (labels: scenarios_quarterly_payload)

g0 = h["grain_my"] + 0  # 2025 marketing-year values, numbers
text = [
    ["10. Сельское хозяйство и агроэкспорт"],
    [""],
    ["Что считает", "Урожай 6 основных культур, агроэкспорт (объём, запасы, выручка в USD); проверки: коридор урожая, "
                    "порты, история экспорта"],
    ["Берёт", "SCENARIOS (цены пшеницы и масла, порты, погода, площадь), COEFS; факт агроэкспорта — НБУ (MacroStat)"],
    ["Пишет в", "B1_REAL строка 11 (урожай → ВДС сельского хозяйства), B2_DEMAND строка 23 (реальный экспорт) и "
                "раздел 3 (запасы)"],
    ["Статус", "в работе: версия 1; часть истории урожая 2015–2018 по памяти (см. источники в столбце H)"],
    ["Как читать", f"Агро — около {round(h['agro_sh'] * 100)}% экспорта товаров и услуг ({FACT}). Год экспорта = половина "
                   "урожая этого года + половина прошлого (маркетинговый год июль–июнь)."],
    [""],
    ["1. Драйверы"],
    ["Код", "Показатель", "Единицы", int(FACT), int(NOW), 2027, 2028, "Источник"],
    ["PX_WHEAT", "Цена пшеницы FOB Чёрное море", "USD/т", round(h["px"].loc[FACT, "WHEAT"]), round(h["px"].loc[NOW, "WHEAT"])] +
    [f"={pc[cc]}11*SCENARIOS!{ACT[cc]}{SL.Y['WHEAT']}/SCENARIOS!{ACT[pc[cc]]}{SL.Y['WHEAT']}" for cc in "FG"] +
    [f"{FACT}–{NOW} — MacroStat AGROTrends (среднее месяцев с данными); дальше рост по SCENARIOS строка 25"],
    ["PX_SUNOIL", "Цена подсолнечного масла FOB", "USD/т", round(h["px"].loc[FACT, "SUNOIL"]), round(h["px"].loc[NOW, "SUNOIL"])] +
    [f"=SCENARIOS!{ACT[cc]}{SUN}" for cc in "FG"] + [f"SCENARIOS строка {SUN}"],
    ["PORTS", "Пропускная способность морских портов", "млн т в год", 82.2] + [f"=SCENARIOS!{ACT[cc]}{SL.Y['PORTS']}" for cc in "EFG"] +
    ["SCENARIOS строка 19"],
    ["WEATHER", "Погода: отклонение урожайности", "%", "", ""] + [f"=SCENARIOS!{ACT[cc]}{WEA}" for cc in "FG"] +
    [f"SCENARIOS строка {WEA}"],
    ["AREA", "Посевная площадь к 2026", "%", "", ""] + [f"=SCENARIOS!{ACT[cc]}{AREA}" for cc in "FG"] +
    [f"SCENARIOS строка {AREA}"],
    [""],
    ["2. Урожай, млн т"],
    ["Код", "Культура", "Как считается 2027–28", int(FACT), int(NOW), 2027, 2028, "Источник", "Средний 2023–2026"],
]
CROP_FIRST = 19
for i, (k, name) in enumerate(CROPS.items()):
    r = CROP_FIRST + i
    shift = (C("A_SHIFT_WHEAT") if k == "WHEAT" else C("A_SHIFT_SPRING") if k in SPRING else None)
    sf = f"*(1+{shift}/100)" if shift else ""
    how = "средний × площадь × погода" + (" × сдвиг пшеницы" if k == "WHEAT" else " × рост яровых" if k in SPRING else "")
    text.append([k, name, how, float(c.loc[k, FACT]), float(c.loc[k, NOW])] +
                [f"=$I{r}*(1+{cc}$15/100)*(1+{cc}$14/100){sf}" for cc in "FG"] + [sources()[k], round(float(h["base"][k]), 2)])
H_ROW = CROP_FIRST + len(CROPS)  # 25
text.append(["HARVEST", "Урожай шести культур", "сумма → B1_REAL строка 11"] +
            [f"=SUM({cc}{CROP_FIRST}:{cc}{H_ROW - 1})" for cc in "DEFG"] + ["", f"=SUM(I{CROP_FIRST}:I{H_ROW - 1})"])
text.append(["HARVEST_G", "Рост урожая", "%", round(float((h["harvest"][FACT] / h["harvest"]["2024"] - 1) * 100), 1)] +
            [f"=({cc}25/{pc[cc]}25-1)*100" for cc in "EFG"])
gr = lambda cc: f"SUM({cc}{CROP_FIRST}:{cc}{CROP_FIRST + 2})"
oil = lambda cc: f"SUM({cc}{CROP_FIRST + 3}:{cc}{CROP_FIRST + 5})"
my = lambda f, cc: f"(0,5*{f(cc)}+0,5*{f(pc[cc])})"
pmy = lambda r, cc: f"(0,5*{cc}{r}+0,5*{pc[cc]}{r})"
text += [
    [""],
    ["3. Агроэкспорт"],
    ["Код", "Показатель", "Как считается", int(FACT), int(NOW), 2027, 2028, "Комментарий"],
    ["GRAIN_S", "Зерно на экспорт, маркетинговый год", "½ урожая года + ½ прошлого − внутреннее потребление, млн т",
     round(h["grain_my"], 1)] + [f"={my(gr, cc)}-{C('A_DOM_GRAIN')}" for cc in "EFG"] +
    [f"внутреннее потребление {num(CALIBRATED[('DOM', 'GRAIN')][0], 0)} млн т (COEFS A_DOM_GRAIN)"],
    ["OIL_S", "Масличные (экспорт семян и продуктов переработки)", "½ урожая года + ½ прошлого, млн т",
     round(h["oil_my"], 1)] + [f"={my(oil, cc)}" for cc in "EFG"] + ["подсолнечник почти весь перерабатывается внутри"],
    ["CARRY_IN", "Запасы, не вывезенные в прошлом году", "млн т", 0] + [f"={pc[cc]}36" for cc in "EFG"] +
    ["сверх обычных переходящих запасов"],
    ["SUPPLY", "Можно вывезти", "зерно + масличные + запасы, млн т", "=D30+D31+D32"] + [f"={cc}30+{cc}31+{cc}32" for cc in "EFG"],
    ["CAP", "Можно вывезти по логистике", "порты × доля агро + Дунай, ж/д, авто, млн т"] +
    [f"={cc}13*{C('A_CAP_SH')}+{C('A_CAP_LAND')}" for cc in "DEFG"] + ["COEFS A_CAP_SH, A_CAP_LAND"],
    ["EXP_VOL", "Вывезено", "меньшее из «можно вывезти» и логистики, млн т"] + [f"=MIN({cc}33;{cc}34)" for cc in "DEFG"],
    ["CARRY", "Осталось в запасах", "млн т"] + [f"={cc}33-{cc}35" for cc in "DEFG"] + ["вывозится в следующем году"],
    ["PRICE_MIX", "Средняя цена тонны агроэкспорта", "(зерно + запасы) × пшеница + масличные × выход масла × масло, USD/т",
     round(h["mix"], 1)] +
    [f"=(({cc}30+{cc}32)*{pmy(11, cc)}+{cc}31*{C('A_OIL_K')}*{pmy(12, cc)})/({cc}30+{cc}31+{cc}32)" for cc in "EFG"] +
    ["цены за маркетинговый год: ½ этого + ½ прошлого; запасы — в основном зерно"],
    ["AGRO_MODEL", "Агроэкспорт по модели", "факт 2025 × объём × цена к 2025, млн USD", round(h["exp"])] +
    [f"=$D$38*({cc}35*{cc}37)/($D$35*$D$37)" for cc in "EFG"] + ["НБУ: экспорт продовольственных товаров и сырья"],
    ["AGRO_EXP", "Агроэкспорт", f"{NOW}: факт 1 пол. + модель 2 пол.; дальше рост модели, млн USD", round(h["exp"]),
     f"={fnum(h['h1_now'], 0)}+E38*{fnum(1 - h['h1_prev'] / h['exp'], 3)}"] + [f"={pc[cc]}39*{cc}38/{pc[cc]}38" for cc in "FG"] +
    [f"факт 1 пол. {NOW}: {num(h['h1_now'] / 1000)} млрд USD ({'+' if h['h1_now'] > h['h1_prev'] else ''}"
     f"{num((h['h1_now'] / h['h1_prev'] - 1) * 100)}% г/г); доля 2 пол. — как в {FACT}"],
    ["AGRO_EXP_G", "Рост агроэкспорта в USD", "%", round(float((h["exp"] / 24669 - 1) * 100), 1)] +
    [f"=({cc}39/{pc[cc]}39-1)*100" for cc in "EFG"],
    ["AGRO_REAL_G", "Реальный рост агроэкспорта", "рост в USD без роста цены, % → B2_DEMAND строка 23", ""] +
    [f"=(({cc}39/{pc[cc]}39)/({cc}37/{pc[cc]}37)-1)*100" for cc in "EFG"],
    ["STOCK_D", "Изменение запасов", "% агроэкспорта прошлого года → B2_DEMAND раздел 3", ""] +
    [f"=({cc}36-{pc[cc]}36)/{pc[cc]}35*100" for cc in "EFG"] + ["рост запасов не меняет ВВП: экспорт ниже, запасы выше"],
    [""],
    ["4. Проверки"],
    ["Код", "Проверка", "Правило", int(FACT), int(NOW), 2027, 2028, "Комментарий"],
    ["CHK_HARV", "Урожай в коридоре погоды", f"отклонение от среднего 2023–2026 не больше ±{num(h['sigma'])}% (1σ 2016–2021)", ""] +
    [f"=IF(ABS({cc}25/$I$25-1)*100<={C('A_SIGMA')};\"OK\";\"ВНИМАНИЕ: урожай \"&ROUND(({cc}25/$I$25-1)*100;1)&\"% к среднему — \"&"
     f"IF(ABS({cc}15)>ABS({cc}14);\"площадь\";\"погода\"))" if cc != "E" else
     f"=IF(ABS(E25/$I$25-1)*100<={C('A_SIGMA')};\"OK\";\"ВНИМАНИЕ: урожай \"&ROUND((E25/$I$25-1)*100;1)&\"% к среднему\")"
     for cc in "EFG"] + ["2026 — оценка Минагрополитики, кукуруза убрана на 20%"],
    ["PORT_CHK", "Логистика вывозит урожай", "можно вывезти ≤ логистика", ""] +
    [f"=IF({cc}33<={cc}34;\"OK\";\"ВНИМАНИЕ: не вывозится \"&ROUND({cc}33-{cc}34;1)&\" млн т, остаётся в запасах\")"
     for cc in "EFG"] + ["узкое место: порты (SCENARIOS строка 19)"],
    ["CHK_EXP", "Рост агроэкспорта в коридоре истории",
     f"10–90-й процентиль 2016–{FACT} без 2022–2024: от {num(h['exp_lo'])} до {num(h['exp_hi'])}%", ""] +
    [f"=IF(AND({cc}40>={fnum(h['exp_lo'])};{cc}40<={fnum(h['exp_hi'])});\"OK\";\"ВНИМАНИЕ: \"&IF({cc}36>{pc[cc]}36;"
     f"\"порты не вывозят урожай\";IF({cc}32>0;\"вывоз запасов прошлых лет\";IF(ABS({cc}26)>ABS(({cc}37/{pc[cc]}37-1)*100);"
     f"\"урожай\";\"цены\"))))" for cc in "EFG"] + ["выход объясняется: урожай, цены, порты или запасы"],
    ["RISK_DRY", "Погодный риск: засуха", "урожай при погоде −1σ, млн т", "", ""] +
    [f"={cc}25*(1-{C('A_SIGMA')}/100)" for cc in "FG"] + ["для сравнения с 2022 (70 млн т) и 2024 (76 млн т)"],
]
out["B10_AGRO!A1:I50"] = text
HV = SL.Y["HARVEST"]  # the annual row shows B10's harvest (active scenario); since 2026-10-25 it is not an input
out[f"SCENARIOS!A{HV}:O{HV}"] = [["Урожай шести культур (считает B10_AGRO, активный сценарий)", "млн т"] + [""] * 9
                                 + [f"=B10_AGRO!{c}25" for c in "EFG"]
                                 + [f"Не вводить: урожай считает B10_AGRO по культурам (погода и площадь — строки {SL.WEATHER}–{SL.AREA}). "
                                    "Рост урожая идёт в ИПЦ «сырые продукты» (B3_PRICES строка 44)"]]
from sheet.scenarios_quarterly_payload import protect  # annual SCENARIOS cells are formulas over the quarters

json.dump(protect(out), sys.stdout, ensure_ascii=False)
