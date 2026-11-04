"""batchUpdate requests that format the NOWCAST sheet like the block sheets (04.11.2026)."""
import json
import sys

from sheet.nowcast_layout import (B_HDR, F_HDR, F_ROW, INDS, M_HDR, N_HDR, N_ROW, P_HDR, P_ROW, Q_HDR, SECTORS, QCOL,
                                  FIRST_FC, col)

SID = 614231277
DARK = {"red": 0.231, "green": 0.420, "blue": 0.639}
HEAD = {"red": 0.910, "green": 0.929, "blue": 0.957}
SEC = {"red": 0.851, "green": 0.886, "blue": 0.937}
TXT = {"red": 0.349, "green": 0.349, "blue": 0.349}
RED = {"red": 0.957, "green": 0.8, "blue": 0.8}
GREEN = {"red": 0.851, "green": 0.918, "blue": 0.824}
FCT = {"red": 0.988, "green": 0.973, "blue": 0.902}   # forecast tint
WHITE = {"red": 1, "green": 1, "blue": 1}


def rng(r0, r1, c0, c1):
    return {"sheetId": SID, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def cell(r0, r1, c0, c1, fmt, fields):
    return {"repeatCell": {"range": rng(r0, r1, c0, c1), "cell": {"userEnteredFormat": fmt},
                           "fields": ",".join(f"userEnteredFormat.{f}" for f in fields)}}


NUM = lambda p: {"numberFormat": {"type": "NUMBER", "pattern": p}}
req = [
    {"updateSheetProperties": {"properties": {"sheetId": SID, "gridProperties": {"frozenRowCount": 2, "frozenColumnCount": 3}},
                               "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
    cell(0, 1, 0, 53, {"backgroundColor": DARK, "textFormat": {"bold": True, "fontSize": 12, "foregroundColor": WHITE}},
         ["backgroundColor", "textFormat"]),
    cell(1, 2, 0, 53, {"textFormat": {"italic": True, "fontSize": 9, "foregroundColor": TXT}}, ["textFormat"]),
]
last_col = {M_HDR: 52, Q_HDR: 19, B_HDR: 13, N_HDR: 20, F_HDR: 19, P_HDR: 19}
for h, nc in last_col.items():
    req.append(cell(h - 2, h - 1, 0, nc, {"backgroundColor": SEC, "textFormat": {"bold": True, "fontSize": 10}},
                    ["backgroundColor", "textFormat"]))
    req.append(cell(h - 1, h, 0, nc, {"backgroundColor": HEAD, "horizontalAlignment": "CENTER", "textFormat": {"bold": True, "fontSize": 9},
                                      "borders": {"bottom": {"style": "SOLID_MEDIUM", "color": DARK}}},
                    ["backgroundColor", "horizontalAlignment", "textFormat", "borders"]))
# code column, names
req.append(cell(M_HDR, P_ROW["USED"], 0, 1, {"textFormat": {"fontFamily": "Roboto Mono", "fontSize": 9, "foregroundColor": TXT}}, ["textFormat"]))
req.append(cell(M_HDR, P_ROW["USED"], 2, 3, {"textFormat": {"fontSize": 9, "foregroundColor": TXT}}, ["textFormat"]))
# numbers
req.append(cell(M_HDR, M_HDR + len(INDS), 3, 51, NUM("0.0"), ["numberFormat"]))
req.append(cell(Q_HDR, Q_HDR + len(INDS), 3, 19, NUM("0.0"), ["numberFormat"]))
req.append(cell(B_HDR, B_HDR + len(SECTORS), 3, 6, NUM("0.00"), ["numberFormat"]))
req.append(cell(B_HDR, B_HDR + len(SECTORS), 8, 13, NUM("0.0"), ["numberFormat"]))
req.append(cell(B_HDR, B_HDR + len(SECTORS), 12, 13, NUM("0.00"), ["numberFormat"]))
req.append(cell(N_HDR, N_ROW[SECTORS[-1]]["RES"], 3, 19, NUM("0.0"), ["numberFormat"]))
for s in SECTORS:
    req.append(cell(N_ROW[s]["DEV"] - 1, N_ROW[s]["DEV"], 3, 19, NUM("0.00"), ["numberFormat"]))
    req.append(cell(N_ROW[s]["NC"] - 1, N_ROW[s]["NC"], 0, 19, {"textFormat": {"bold": True}}, ["textFormat.bold"]))
    req.append({"updateBorders": {"range": rng(N_ROW[s]["RES"] - 1, N_ROW[s]["RES"], 0, 20),
                                  "bottom": {"style": "SOLID", "color": {"red": 0.6, "green": 0.6, "blue": 0.6}}}})
req.append(cell(F_HDR, P_ROW["USED"], 3, 19, NUM("0.0"), ["numberFormat"]))
req.append(cell(F_ROW["FLASH"] - 1, F_ROW["FLASH"], 3, 19, {"backgroundColor": {"red": 1, "green": 0.949, "blue": 0.8}}, ["backgroundColor"]))
# forecast quarters tint (from 2026Q3) in sections 4-6 and a border before them
fc_col = 3 + list(QCOL).index(FIRST_FC)
for r0, r1 in ((N_HDR, N_ROW[SECTORS[-1]]["RES"]), (F_HDR, F_ROW["FLAG"]), (P_HDR, P_ROW["USED"]), (Q_HDR, Q_HDR + len(INDS))):
    req.append({"updateBorders": {"range": rng(r0 - 1, r1, fc_col, fc_col + 1), "left": {"style": "SOLID_MEDIUM", "color": DARK}}})
# widths
for c0_, c1_, px in ((0, 1, 95), (1, 2, 330), (2, 3, 150), (3, 51, 62), (51, 52, 90)):
    req.append({"updateDimensionProperties": {"range": {"sheetId": SID, "dimension": "COLUMNS", "startIndex": c0_, "endIndex": c1_},
                                              "properties": {"pixelSize": px}, "fields": "pixelSize"}})
for txt, color in (("ВНИМАНИЕ", RED), ("OK", GREEN)):
    req.append({"addConditionalFormatRule": {"index": 0, "rule": {"ranges": [rng(0, 100, 0, 53)], "booleanRule": {
        "condition": {"type": "TEXT_STARTS_WITH", "values": [{"userEnteredValue": txt}]}, "format": {"backgroundColor": color}}}}})

if __name__ == "__main__":
    json.dump(req, sys.stdout, ensure_ascii=False)
