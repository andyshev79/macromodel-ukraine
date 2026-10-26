"""Download Gosstat data (stat.gov.ua SDMX API) with full history and log every revision.

Each run re-downloads the full history of every set in macromodel/loaders/ukrstat_sdmx.SETS
(Gosstat revises past values, so appending only new months would leave stale history) and
compares it with the previous snapshot:

- data/ukrstat/<set>.csv.gz   current snapshot: series, period, value, flag, updated
- data/ukrstat/revisions.csv  log of changed and removed values (appended, never rewritten):
                              fetched, set, released, series, period, kind, old, new, diff, pct
- data/ukrstat/status.csv     per set: version, rows, first/last period, last and next release,
                              new values and revisions in this run, error if the download failed
- data/ukrstat/crosscheck.csv Gosstat vs the model history (data/history) for the key series

A set that fails to download keeps its previous snapshot. Exit code is 0 unless all sets failed.

Usage: python scripts/fetch_ukrstat.py [--sets gdp_q cpi_m ...] [--check-only]
  --check-only  skip the download, only rebuild crosscheck.csv from the snapshots
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from macromodel import ukrstat
from macromodel.loaders import ukrstat_sdmx as u

OUT = ROOT / "data" / "ukrstat"
BIG = 0.5  # % change of a published value worth printing


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sets", nargs="*", default=list(u.SETS))
    p.add_argument("--check-only", action="store_true")
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    failed = 0
    if not args.check_only:
        status_path = OUT / "status.csv"
        status = (pd.read_csv(status_path, dtype=str, keep_default_na=False).set_index("set").to_dict("index")
                  if status_path.exists() else {})
        vers = u.versions()
        logs = []
        for name in args.sets:
            path = OUT / f"{name}.csv.gz"
            try:
                new, meta = u.fetch(name, vers)
            except Exception as e:  # keep the old snapshot, say why
                failed += 1
                print(f"{name}: ОШИБКА загрузки, оставлен прошлый снимок: {e!r}"[:300])
                status[name] = {**status.get(name, {"flow": u.SETS[name].flow}), "checked": today, "error": repr(e)[:200]}
                continue
            meta.update(checked=today, error="", new_values=len(new), revised=0, removed=0)
            prev_dims = status.get(name, {}).get("dims")
            if path.exists() and prev_dims and prev_dims != meta["dims"]:
                # Gosstat changed the structure of the set: series ids are not comparable, start over
                print(f"{name}: структура набора изменилась ({prev_dims} -> {meta['dims']}), "
                      "пересмотры за этот запуск не считаются, снимок заменён")
            elif path.exists():
                old = ukrstat.snapshot(OUT, name)
                rev = u.revisions(old, new)
                meta.update(new_values=rev.attrs["new"], revised=int((rev["kind"] == "revised").sum()),
                            removed=int((rev["kind"] == "removed").sum()))
                if len(rev):
                    rev.insert(0, "released", meta["released"])
                    rev.insert(0, "set", name)
                    rev.insert(0, "fetched", today)
                    logs.append(rev)
                    big = rev[rev["pct"].abs() >= BIG]
                    print(f"{name}: пересмотрено {meta['revised']} значений, удалено {meta['removed']}; "
                          f"изменения от {BIG}%: {len(big)}")
                    for r in big.reindex(big["pct"].abs().sort_values(ascending=False).index).head(8).itertuples():
                        print(f"    {r.series} {r.period}: {r.old:g} -> {r.new:g} ({r.pct:+.1f}%)")
            new.to_csv(path, index=False, compression="gzip")
            status[name] = meta
            print(f"{name}: {meta['rows']} значений, {meta['first']}..{meta['last']}, выпуск {meta['released']}, "
                  f"следующий {meta['next_release']}, новых {meta['new_values']}, пересмотров {meta['revised']}")
        if logs:
            log = pd.concat(logs, ignore_index=True)
            log_path = OUT / "revisions.csv"
            log.to_csv(log_path, mode="a", header=not log_path.exists(), index=False)
        st = pd.DataFrame.from_dict(status, orient="index").drop(columns="set", errors="ignore")
        st.index.name = "set"
        st.to_csv(status_path)

    cc = ukrstat.crosscheck(OUT, ROOT / "data" / "history")
    cc.to_csv(OUT / "crosscheck.csv", index=False)
    if len(cc):
        bad = cc[cc["ok"] == False]  # noqa: E712 (None = no model value)
        ahead = cc[cc["model"].isna()]
        print(f"\nСверка с историей модели: {len(cc) - len(ahead)} кварталов, расхождений {len(bad)}")
        for r in bad.itertuples():
            print(f"    {r.code} {r.quarter}: Госстат {r.ukrstat:g}, модель {r.model:g} ({r.gap:+g} {r.gap_unit})")
        for code, g in ahead.groupby("code"):
            print(f"    {code}: у Госстата уже есть {', '.join(g['quarter'])}, в истории модели ещё нет")
    return 1 if failed and failed == len(args.sets) else 0


if __name__ == "__main__":
    sys.exit(main())
