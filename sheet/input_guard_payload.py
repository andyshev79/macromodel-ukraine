"""CHECKS rows 37-38: SCENARIOS inputs that turned into text or dates.

The sheet locale is ru_RU: a pasted "0.9" stays text and "11.5" becomes the date 11 May (serial ~46150),
which breaks ANCHORS and ANNUAL with #VALUE! (happened 2026-10-27). The check counts such cells.
Output: JSON {range: 2D list}, formulas in ru_RU syntax.
"""
import json

from macromodel import scenario_layout as SL

L = SL.LABOUR
RANGES = [f"C{SL.ANNUAL_FIRST + 1}:N{SL.ANNUAL_LAST}", f"C{SL.FIN_Q}:L{SL.RATE_Q}", f"C{SL.TARIFF}:L{SL.TARIFF}", f"C{SL.FUEL_QQ}:L{SL.FUEL_QQ}", f"C{L + 2}:L{SL.LAB_NOTE - 1}",
          f"C{SL.Q_MAIN + 3}:M{SL.EXTRA_FIN + 3}", f"C{SL.DESTROYED + 2}:E{SL.DESTROYED + 4}"]
# numeric input rows: annual, quarterly financing to near-term, tariffs, fuel q/q, labour, main quarterly block, destroyed shares
DATE_RANGES = [(RANGES[0], f"*(ROW(SCENARIOS!{RANGES[0]})<>{SL.Y['FIN']})")] + [(r, "") for r in RANGES[1:]]  # financing in USD mn
DATE_RANGES[1] = (f"C{SL.GDP_Q}:L{SL.RATE_Q}", "")  # quarterly financing is in USD mn, above the date serials
LO, HI = 45000, 47000  # date serials of 2023-2028

text = "+".join(f"SUMPRODUCT(--ISTEXT(SCENARIOS!{r}))" for r in RANGES)
dates = "+".join(f"SUMPRODUCT(ISNUMBER(SCENARIOS!{r})*(SCENARIOS!{r}>{LO})*(SCENARIOS!{r}<{HI}){extra})" for r, extra in DATE_RANGES)
out = {"CHECKS!A37:D38": [
    ["Ввод SCENARIOS: числа не стали текстом или датами",
     f"Число ячеек ввода (строки {SL.ANNUAL_FIRST + 1}–{SL.ANNUAL_LAST}, {SL.DESTROYED + 2}–{SL.DESTROYED + 4}, {SL.Q_MAIN + 3}–{SL.EXTRA_FIN + 3}, "
     f"{SL.FIN_Q}–{SL.RATE_Q}, {SL.TARIFF}, {SL.FUEL_QQ}, {L + 2}–{SL.LAB_NOTE - 1}) с текстом или датой («0.9» с точкой в русской локали остаётся "
     "текстом, «11.5» становится 11 мая); вводите дроби через запятую", "0", f"=IFERROR({text}+{dates};-1)"],
    ["  статус", "", "", '=IF(D37=0;"OK";IF(D37<0;"ВНИМАНИЕ: ошибка в ячейках ввода";"ВНИМАНИЕ: "&D37&" ячеек с текстом или датой"))'],
]}
json.dump(out, __import__("sys").stdout, ensure_ascii=False)
