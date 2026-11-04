"""Sheets batchUpdate requests that format the ANNUAL sheet the way the block sheets look (04.11.2026):
title, header band, code / name / unit columns, number formats by unit, groups of rows split by
borders, a border before the first forecast year, the comment column, flag colours.

Output: JSON list of requests for spreadsheets.batchUpdate (sheetId of ANNUAL = 4).
"""
import json
import sys

from sheet.annual_payload import CODES, FIRST

SID = 4
LAST = FIRST + len(CODES) - 1          # row 33
NCOL = 19                              # A..S
DARK = {"red": 0.231, "green": 0.420, "blue": 0.639}
HEAD = {"red": 0.910, "green": 0.929, "blue": 0.957}
GREY = {"red": 0.6, "green": 0.6, "blue": 0.6}
TXT = {"red": 0.349, "green": 0.349, "blue": 0.349}
RED = {"red": 0.957, "green": 0.8, "blue": 0.8}
GREEN = {"red": 0.851, "green": 0.918, "blue": 0.824}

# number format per row (by unit): percents and indices one decimal, money and people as integers
FMT = {"0.0": ["GDP_REAL_P", "DEFL", "CPI_YOY", "PPI_YOY", "NBU_RATE", "LOAN_RATE", "DEP_RATE", "POP", "UNEMP", "DEBT_GDP"],
       "0.00": ["FX_AVG", "FX_EOP"]}
GROUPS = ["DEFL", "PPI_YOY", "DEP_RATE", "WAGE_NOM", "RES_USD", "CFC", "DEBT_GDP"]  # last row of each group


def rng(r0, r1, c0, c1):
    return {"sheetId": SID, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def cell(r0, r1, c0, c1, fmt, fields):
    return {"repeatCell": {"range": rng(r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt}, "fields": fields}}


req = [
    {"updateSheetProperties": {"properties": {"sheetId": SID, "gridProperties": {"frozenRowCount": 4, "frozenColumnCount": 4}},
                               "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
    # title and note
    cell(0, 1, 0, NCOL, {"backgroundColor": DARK, "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                         "verticalAlignment": "MIDDLE"}, "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment"),
    cell(1, 2, 0, NCOL, {"textFormat": {"italic": True, "fontSize": 9, "foregroundColor": TXT}}, "userEnteredFormat.textFormat"),
    # row 3: fact / forecast
    cell(2, 3, 3, 18, {"horizontalAlignment": "CENTER", "textFormat": {"fontSize": 9, "foregroundColor": TXT, "italic": True}},
         "userEnteredFormat.horizontalAlignment,userEnteredFormat.textFormat"),
    # header row 4
    cell(3, 4, 0, NCOL, {"backgroundColor": HEAD, "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                         "numberFormat": {"type": "NUMBER", "pattern": "0"},
                         "textFormat": {"bold": True, "fontSize": 10},
                         "borders": {"bottom": {"style": "SOLID_MEDIUM", "color": DARK}}},
         "userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.numberFormat,userEnteredFormat.textFormat,userEnteredFormat.borders"),
    cell(3, 4, 0, 3, {"horizontalAlignment": "LEFT"}, "userEnteredFormat.horizontalAlignment"),
    cell(3, 4, 18, 19, {"horizontalAlignment": "LEFT"}, "userEnteredFormat.horizontalAlignment"),
    # body: code, name, unit, aggregation, numbers, comment
    cell(4, LAST, 0, 1, {"textFormat": {"fontFamily": "Roboto Mono", "fontSize": 9, "foregroundColor": TXT}, "verticalAlignment": "MIDDLE"},
         "userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment"),
    cell(4, LAST, 1, 2, {"textFormat": {"fontSize": 10}, "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"},
         "userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"),
    cell(4, LAST, 2, 3, {"textFormat": {"fontSize": 9, "foregroundColor": TXT}, "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"},
         "userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"),
    cell(4, LAST, 3, 4, {"horizontalAlignment": "CENTER", "textFormat": {"fontSize": 9, "foregroundColor": TXT}, "verticalAlignment": "MIDDLE"},
         "userEnteredFormat.horizontalAlignment,userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment"),
    cell(4, LAST, 4, 18, {"horizontalAlignment": "RIGHT", "verticalAlignment": "MIDDLE", "textFormat": {"fontSize": 10},
                          "numberFormat": {"type": "NUMBER", "pattern": "#,##0"}},
         "userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,userEnteredFormat.textFormat,userEnteredFormat.numberFormat"),
    cell(4, LAST, 18, 19, {"textFormat": {"fontSize": 9, "foregroundColor": TXT}, "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"},
         "userEnteredFormat.textFormat,userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy"),
    # clear the old static white fill so the forecast tint (conditional format) shows
    cell(4, LAST, 4, 18, {}, "userEnteredFormat.backgroundColor"),
]
for pat, codes in FMT.items():
    for c in codes:
        r = FIRST + CODES.index(c) - 1
        req.append(cell(r, r + 1, 4, 18, {"numberFormat": {"type": "NUMBER", "pattern": pat}}, "userEnteredFormat.numberFormat"))
for c in GROUPS:
    r = FIRST + CODES.index(c) - 1
    req.append({"updateBorders": {"range": rng(r, r + 1, 0, NCOL), "bottom": {"style": "SOLID", "color": GREY}}})
# border between the last full fact year (2025, column O) and 2026
req.append({"updateBorders": {"range": rng(2, LAST, 15, 16), "left": {"style": "SOLID_MEDIUM", "color": DARK}}})
req.append({"updateBorders": {"range": rng(2, LAST, 18, 19), "left": {"style": "SOLID", "color": GREY}}})
# row 7 (GDP by expenditure = row 5 by construction) hidden, row 6 shows growth (sheet/annual_payload.py)
req.append({"updateDimensionProperties": {"range": {"sheetId": SID, "dimension": "ROWS", "startIndex": 6, "endIndex": 7},
                                          "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}})
# column widths
for c0, c1, px in ((0, 1, 120), (1, 2, 300), (2, 3, 170), (3, 4, 80), (4, 18, 90), (18, 19, 480)):
    req.append({"updateDimensionProperties": {"range": {"sheetId": SID, "dimension": "COLUMNS", "startIndex": c0, "endIndex": c1},
                                              "properties": {"pixelSize": px}, "fields": "pixelSize"}})
req.append({"updateDimensionProperties": {"range": {"sheetId": SID, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                                          "properties": {"pixelSize": 28}, "fields": "pixelSize"}})
# OK green next to the existing ВНИМАНИЕ red rule
req.append({"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [rng(0, 1000, 0, 26)], "booleanRule": {
    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "OK"}]}, "format": {"backgroundColor": GREEN}}}}})

if __name__ == "__main__":
    json.dump(req, sys.stdout, ensure_ascii=False)
