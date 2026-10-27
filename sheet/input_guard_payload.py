"""CHECKS rows 37-38: SCENARIOS inputs that turned into text or dates.

The sheet locale is ru_RU: a pasted "0.9" stays text and "11.5" becomes the date 11 May (serial ~46150),
which breaks ANCHORS and ANNUAL with #VALUE! (happened 2026-10-27). The check counts such cells.
Output: JSON {range: 2D list}, formulas in ru_RU syntax.
"""
import json

RANGES = ["C17:N33", "C40:L53", "C82:L117"]  # numeric input rows: annual, quarterly near-term, labour quarterly
DATE_RANGES = [("C17:N33", "*(ROW(SCENARIOS!C17:N33)<>20)"), ("C43:L53", ""), ("C82:L117", "")]  # row 20: financing in USD mn
LO, HI = 45000, 47000  # date serials of 2023-2028

text = "+".join(f"SUMPRODUCT(--ISTEXT(SCENARIOS!{r}))" for r in RANGES)
dates = "+".join(f"SUMPRODUCT(ISNUMBER(SCENARIOS!{r})*(SCENARIOS!{r}>{LO})*(SCENARIOS!{r}<{HI}){extra})" for r, extra in DATE_RANGES)
out = {"CHECKS!A37:D38": [
    ["Ввод SCENARIOS: числа не стали текстом или датами",
     "Число ячеек ввода (строки 17–33, 40–53, 82–117) с текстом или датой («0.9» с точкой в русской локали остаётся "
     "текстом, «11.5» становится 11 мая); вводите дроби через запятую", "0", f"=IFERROR({text}+{dates};-1)"],
    ["  статус", "", "", '=IF(D37=0;"OK";IF(D37<0;"ВНИМАНИЕ: ошибка в ячейках ввода";"ВНИМАНИЕ: "&D37&" ячеек с текстом или датой"))'],
]}
json.dump(out, __import__("sys").stdout, ensure_ascii=False)
