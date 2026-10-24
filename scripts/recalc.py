"""Recalculate the model after new history: facts into ANCHORS, re-estimated coefficients into COEFS,
equation texts on the block sheets and the MODEL_QUALITY sheet.

Writes data/recalc/payload.json ({range: 2D list}, ru_RU formulas) for the sheet and prints what
changed against the previous run (data/recalc/last.json). Only cells derived from data are
written: SCENARIOS, forecast formulas and hand-entered cells in ANCHORS are left alone, so the
user's inputs survive. SUMMARY is refreshed separately (snapshots per scenario).

Usage: python scripts/recalc.py [--fetch]   (--fetch runs scripts/fetch_history.py first)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from macromodel.anchors import ANCHORS

OUT = ROOT / "data" / "recalc"
BLOCKS = ["b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8"]
TEXT_SHEETS = ("B1_REAL", "B2_DEMAND", "B3_PRICES", "B4_LABOUR", "B7_MONETARY")  # equation texts follow the estimates
FIRST_ROW, FIRST_Q, LAST_FACT = 5, "2015Q1", "2026Q2"  # ANCHORS layout: row 5 = first anchor, H = 2015Q1
FORMULA_ROWS = {"DEFL", "TRADE_BAL", "FIN_GAP_USD"}


def col(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def num(c: str) -> int:
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n - 1


def cells(rng: str, values: list) -> dict:
    """Range + 2D list -> {"SHEET!A1": value}."""
    sheet, a1 = rng.split("!")
    m = re.match(r"([A-Z]+)(\d+)", a1)
    c0, r0 = num(m.group(1)), int(m.group(2))
    return {f"{sheet}!{col(c0 + j)}{r0 + i}": v for i, row in enumerate(values) for j, v in enumerate(row)}


def payload(name: str, *args) -> dict:
    res = subprocess.run([sys.executable, str(ROOT / "sheet" / f"{name}_payload.py"), *args],
                         capture_output=True, text=True, check=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
    return json.loads(res.stdout)


def build() -> dict:
    out, written = {}, set()
    for b in BLOCKS:
        for rng, vals in payload(b, "--coefs").items():
            written |= set(cells(rng, vals))
            if rng.startswith("COEFS!"):
                out[rng] = vals
            elif rng.split("!")[0] in TEXT_SHEETS:
                # column C of equation rows: a text next to formulas
                for ref, v in cells(rng, vals).items():
                    if ref.split("!")[1].startswith("C") and re.fullmatch(r"[A-Z_0-9]+!C\d+", ref) \
                            and isinstance(v, str) and v and not v.startswith("="):
                        right = cells(rng, vals).get(ref.replace("!C", "!E"))
                        if isinstance(right, str) and "COEFS!" in right:
                            out[ref] = [[v]]
    out.update(payload("shocks", "--coefs"))
    out.update(payload("cpi_blocks", "--coefs"))
    out.update(payload("quality"))
    # facts: anchors with data in the history file; cells the blocks fill (estimates, formulas) are skipped
    a = pd.read_csv(ROOT / "data" / "history" / "anchors_q.csv", index_col=0)
    quarters = [q for q in a.columns if FIRST_Q <= q <= LAST_FACT]
    q0 = 7  # column H
    rows = []
    for i, anc in enumerate(ANCHORS):
        r = FIRST_ROW + i
        row = []
        if anc.code in FORMULA_ROWS or anc.code not in a.index:
            rows.append([None] * len(quarters))
            continue
        for k, q in enumerate(quarters):
            ref = f"ANCHORS!{col(q0 + k)}{r}"
            v = a.loc[anc.code, q]
            row.append(None if pd.isna(v) or ref in written else round(float(v), 4))
        rows.append(row)
    # one block; None = leave the cell as it is (formula rows, block estimates, gaps in the data)
    out[f"ANCHORS!H{FIRST_ROW}:{col(q0 + len(quarters) - 1)}{FIRST_ROW + len(ANCHORS) - 1}"] = rows
    return out


def changes(old: dict, new: dict) -> list[str]:
    o = {k: v for r, vals in old.items() for k, v in cells(r, vals).items()}
    n = {k: v for r, vals in new.items() for k, v in cells(r, vals).items()}
    diff = []
    for k, v in n.items():
        if v is None or k.startswith("MODEL_QUALITY"):
            continue
        w = o.get(k)
        if isinstance(v, (int, float)) and isinstance(w, (int, float)):
            if abs(v - w) > 1e-6 * max(1, abs(v)):
                diff.append(f"{k}: {w} -> {v}")
        elif v != w and w is not None:
            diff.append(f"{k}: {w!r} -> {v!r}")
    return diff


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fetch", action="store_true")
    args = p.parse_args()
    if args.fetch:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_history.py")], check=True, cwd=ROOT)
    new = build()
    OUT.mkdir(parents=True, exist_ok=True)
    last = OUT / "last.json"
    diff = changes(json.loads(last.read_text()) if last.exists() else {}, new)
    (OUT / "payload.json").write_text(json.dumps(new, ensure_ascii=False))
    last.write_text(json.dumps(new, ensure_ascii=False))
    print(f"{len(new)} ranges -> {OUT / 'payload.json'}; changed since last run: {len(diff)}")
    for d in diff:
        print(" ", d)
