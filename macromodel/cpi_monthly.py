"""Monthly CPI by the NBU's blocks and the 6-month nowcast (12.11.2026).

1. History. Gosstat publishes CPI m/m by COICOP group and core CPI every month (SDMX cache
   data/ukrstat/cpi_m.csv.gz). The NBU split (core, raw food, administered, fuel) has no published
   weights, so it is rebuilt from Gosstat groups:
   - core = Gosstat core CPI (the NBU uses it as is);
   - raw food = meat, fish, milk/cheese/eggs, fruit, vegetables;
   - administered = alcohol and tobacco (excise), housing and utilities, transport services, communication;
   - fuel = fuels and lubricants.
   Group weights: non-negative least squares of headline m/m on core and the groups, 2017-2026
   (they come out as effective basket weights and sum to about 1). Each rebuilt block is checked
   against the NBU's own monthly (2023+) and quarterly (2017+) components.
2. Nowcast, per block, m/m: x_t = a_month + rho * x_{t-1} + beta * FX m/m_{t-1} (core, raw, administered;
   OLS 2017-2026 without the 2022 war shock). Fuel follows the quarterly fuel input of SCENARIOS (B3_PRICES
   row 59, % q/q) spread evenly over the months of the quarter. Headline m/m = c + sum of w_b x block m/m.
   Six months ahead; the end-of-quarter y/y of the blocks anchors the first two quarters of B3_PRICES.
3. Benchmark: direct regression y/y_{t+h} = a + b y/y_t + c FX y/y_t + d household expectations_t.
   Naive: y/y_{t+h} = y/y_t. Backtest from 2019 with expanding samples; errors by horizon go to the
   accuracy log, and each monthly run appends its forecasts to data/cpi_m/forecast_log.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UK = ROOT / "data" / "ukrstat" / "cpi_m.csv.gz"
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "cpi_m"
HIST_CSV = OUT / "history_m.csv"
LOG_CSV = OUT / "forecast_log.csv"

BLOCKS = ["CORE", "RAW", "ADM", "FUEL"]
NAMES = {"CPI": "ИПЦ", "CORE": "Базовая инфляция", "RAW": "Сырые продукты", "ADM": "Административные цены",
         "FUEL": "Топливо"}
GROUPS = {
    "RAW": {"01_1_2": "Мясо", "01_1_3": "Рыба", "01_1_4": "Молоко, сыр, яйца", "01_1_6": "Фрукты", "01_1_7": "Овощи"},
    "ADM": {"02": "Алкоголь и табак", "04": "Жильё и коммунальные услуги", "07_3": "Транспортные услуги", "08": "Связь"},
    "FUEL": {"07_2_2": "Топливо и смазочные материалы"},
}
W_SAMPLE = ("2017-01", None)          # weights: to the last month
EQ_SAMPLE = ("2017-01", None)
WAR = ("2022-02", "2022-12")           # excluded from the block equations and the benchmark
H = 6                                  # nowcast horizon, months
BT_FIRST = "2019-01"                   # first backtest origin
HORIZONS = [1, 2, 3, 6]


# ---------- data ----------
def _gosstat() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_csv(UK)
    d["code"] = d.series.str.split(".").str[2]
    piv = lambda base: d[d.series.str.contains(base)].pivot_table(index="period", columns="code", values="value")
    mm, yy = piv("PREV_MONTH"), piv("CORMONTH_PREV_YEAR")
    for x in (mm, yy):
        x.index = pd.PeriodIndex(x.index, freq="M")
    return mm.sort_index() - 100, yy.sort_index() - 100


def nnls(A: np.ndarray, b: np.ndarray, iters: int = 500) -> np.ndarray:
    """Lawson-Hanson non-negative least squares (no scipy in the requirements)."""
    n = A.shape[1]
    P, x = [], np.zeros(n)
    for _ in range(iters):
        w = A.T @ (b - A @ x)
        Z = [j for j in range(n) if j not in P]
        if not Z or max(w[Z]) <= 1e-10:
            break
        P.append(Z[int(np.argmax(w[Z]))])
        while True:
            z = np.zeros(n)
            z[P] = np.linalg.lstsq(A[:, P], b, rcond=None)[0]
            if (z[P] > 0).all():
                x = z
                break
            neg = [j for j in P if z[j] <= 0]
            a = min(x[j] / (x[j] - z[j]) for j in neg)
            x = x + a * (z - x)
            P = [j for j in P if x[j] > 1e-12]
    return x


def group_weights(mm: pd.DataFrame) -> tuple[dict, float]:
    cols = ["_Z"] + [g for b in GROUPS.values() for g in b]
    X = mm[cols].loc[W_SAMPLE[0]:W_SAMPLE[1]].dropna()
    y = mm["0"].loc[X.index]
    w = nnls(X.values, y.values)
    e = y.values - X.values @ w
    r2 = 1 - e @ e / ((y - y.mean()) @ (y - y.mean()))
    return dict(zip(cols, w)), float(r2)


def yoy_from_mm(mm: pd.Series) -> pd.Series:
    lv = np.log1p(mm / 100).cumsum()
    return (np.exp(lv - lv.shift(12)) - 1) * 100


def _nbu_components() -> tuple[pd.DataFrame, pd.DataFrame]:
    from macromodel.loaders import nbu_ir
    paths = sorted((RAW_DIR / "nbu_ir").glob("Tables_Charts_*.xlsx"))
    if not paths:
        paths = nbu_ir.download(RAW_DIR, refresh=False)
    return nbu_ir.quarterly(paths), nbu_ir.monthly(paths)


def _fx_m() -> pd.Series:
    """UAH/USD, monthly average of the NBU official rate (daily file in data/raw, else the NBU API)."""
    p = RAW_DIR / "usd_daily.csv"
    if p.exists():
        s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
    else:
        from datetime import date
        from macromodel.loaders import nbu
        s = nbu.exchange_rate(date(2012, 1, 1), date.today())
        p.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(p)
    return s.groupby(s.index.to_period("M")).mean()


def build_history(refresh: bool = False) -> pd.DataFrame:
    """Monthly table: headline and blocks (m/m and y/y), NBU components, expectations, FX, Brent.
    Saved to data/cpi_m/history_m.csv so later runs work without the raw downloads."""
    if HIST_CSV.exists() and not refresh:
        h = pd.read_csv(HIST_CSV, index_col=0)
        h.index = pd.PeriodIndex(h.index, freq="M")
        return h
    from macromodel.loaders import commodities, nbu_files
    mm, yy = _gosstat()
    W, r2 = group_weights(mm)
    h = pd.DataFrame(index=mm.loc["2010-01":].index)
    h["CPI_MM"], h["CPI_YY"] = mm["0"], yy["0"]
    h["CORE_MM"], h["CORE_YY"] = mm["_Z"], yy["_Z"]
    for b, gs in GROUPS.items():
        w = np.array([W[g] for g in gs])
        h[f"{b}_MM"] = (mm[list(gs)] * w).sum(axis=1, min_count=len(gs)) / w.sum()
        h[f"{b}_YY"] = yoy_from_mm(h[f"{b}_MM"])
    # administered prices without utilities (excise, transport, communication) and utilities, as in B3_PRICES
    wx = {g: W[g] for g in ("02", "07_3", "08")}
    h["ADMX_MM"] = sum(w * mm[g] for g, w in wx.items()) / sum(wx.values())
    h["UTIL_MM"] = mm["04"]
    h["REB_MM"] = W["_Z"] * mm["_Z"] + sum(W[g] * mm[g] for gs in GROUPS.values() for g in gs)
    qn, mn = _nbu_components()
    for b, k in (("RAW", "RAW_FOOD"), ("ADM", "ADMIN"), ("FUEL", "FUEL")):
        nb = mn[k].copy() if k in mn else pd.Series(dtype=float)
        q = qn[k].dropna()
        for per, v in q.items():          # quarterly charts give end-of-quarter months before 2023
            m = per.asfreq("M", "end")
            if m not in nb.index or pd.isna(nb.get(m)):
                nb.loc[m] = v
        h[f"NBU_{b}_YY"] = nb.sort_index()
    cache = RAW_DIR
    s = nbu_files.surveys_m(nbu_files.path(cache, "surveys_price", refresh))
    for k in ["HH", "BUSINESS", "BANKS", "ANALYSTS"]:
        h[f"EXP_{k}"] = s[k]
    fx = _fx_m()
    h["FX"] = fx
    h["FX_MM"] = (fx / fx.shift(1) - 1) * 100
    h["FX_YY"] = (fx / fx.shift(12) - 1) * 100
    h["BRENT"] = commodities.brent_m(cache, refresh=refresh)
    h = h.loc["2010-01":mm.index[-1]]
    OUT.mkdir(parents=True, exist_ok=True)
    h.round(4).to_csv(HIST_CSV)
    pd.DataFrame([{"group": g, "block": "CORE" if g == "_Z" else next((b for b, gs in GROUPS.items() if g in gs), ""),
                   "name": "Базовая инфляция (Госстат)" if g == "_Z" else next(gs[g] for gs in GROUPS.values() if g in gs),
                   "weight": round(w, 4)} for g, w in W.items()] + [{"group": "R2", "block": "", "name": "R² подгонки", "weight": round(r2, 4)}]
                 ).to_csv(OUT / "weights.csv", index=False)
    return h


def weights() -> tuple[dict, dict, float]:
    """Group weights, block weights (sum of the group weights) and R² of the headline fit."""
    w = pd.read_csv(OUT / "weights.csv")
    r2 = float(w.loc[w.group == "R2", "weight"].iloc[0])
    w = w[w.group != "R2"]
    gw = dict(zip(w.group, w.weight))
    bw = w.groupby("block").weight.sum().to_dict()
    return gw, bw, r2


# ---------- equations ----------
def _war_mask(idx: pd.PeriodIndex) -> np.ndarray:
    return (idx >= pd.Period(WAR[0], "M")) & (idx <= pd.Period(WAR[1], "M"))


def ols(y: pd.Series, X: pd.DataFrame) -> dict:
    b, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    e = y.values - X.values @ b
    s2 = e @ e / max(len(y) - X.shape[1], 1)
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(X.values.T @ X.values)))
    r2 = 1 - e @ e / ((y - y.mean()) @ (y - y.mean()))
    return {"coef": dict(zip(X.columns, b)), "se": dict(zip(X.columns, se)), "r2": float(r2), "n": len(y),
            "sigma": float(np.sqrt(s2))}


def block_design(h: pd.DataFrame, b: str) -> tuple[pd.Series, pd.DataFrame]:
    y = h[f"{b}_MM"]
    X = pd.DataFrame(index=h.index)
    for m in range(1, 13):
        X[f"M{m:02d}"] = (h.index.month == m).astype(float)
    X["L1"] = y.shift(1)
    if b in ("CORE", "RAW"):
        X["FX_L1"] = h["FX_MM"].shift(1)
    return y, X


def estimate_blocks(h: pd.DataFrame, last: pd.Period | None = None) -> dict:
    out = {}
    for b in ["CORE", "RAW", "ADMX"]:
        y, X = block_design(h, b)
        df = pd.concat([y.rename("y"), X], axis=1).loc[EQ_SAMPLE[0]:last].dropna()
        df = df[~_war_mask(df.index)]
        out[b] = ols(df["y"], df.drop(columns="y"))
    df = h[["CPI_MM"] + [f"{b}_MM" for b in BLOCKS]].loc[EQ_SAMPLE[0]:last].dropna()
    out["W"] = ols(df["CPI_MM"], df[[f"{b}_MM" for b in BLOCKS]].assign(const=1.0))
    return out


UTIL_HIKE = 3.0   # % m/m: months with a utility tariff decision, left out of the drift


def util_drift(h: pd.DataFrame, last: pd.Period | None = None) -> float:
    """Utilities m/m without tariff decisions: median since 2023 (tariffs frozen under martial law)."""
    u = h["UTIL_MM"].loc["2023-01":last].dropna()
    return float(u[u.abs() < UTIL_HIKE].median())


def fuel_path(h: pd.DataFrame, origin: pd.Period, months: list[pd.Period], fuel_qq: dict | None) -> dict:
    """Fuel m/m for the forecast months. With a quarterly input (% q/q of the end-of-quarter level) the rest of
    the quarter is spread evenly over its remaining months; without one, the same calendar months a year ago."""
    out = {}
    for m in months:
        q = str(m.asfreq("Q"))
        if fuel_qq and q in fuel_qq and fuel_qq[q] is not None and not pd.isna(fuel_qq[q]):
            q_start = m.asfreq("Q").asfreq("M", "start")
            done = [p for p in pd.period_range(q_start, origin) if p >= q_start]
            got = np.prod([1 + h.loc[p, "FUEL_MM"] / 100 for p in done]) if done else 1.0
            left = 3 - len(done)
            out[m] = (((1 + fuel_qq[q] / 100) / got) ** (1 / left) - 1) * 100 if left > 0 else 0.0
        else:
            out[m] = float(h["FUEL_MM"].get(m - 12, 0.0))
    return out


def nowcast(h: pd.DataFrame, origin: pd.Period, est: dict | None = None, fuel_qq: dict | None = None,
            fx_path: dict | None = None, horizon: int = H, util_path: dict | None = None) -> pd.DataFrame:
    """Months origin+1..origin+horizon: m/m and y/y by block and headline. fx_path: FX m/m by month
    (default 0 = rate stays at the last month's average)."""
    est = est or estimate_blocks(h, origin)
    months = list(pd.period_range(origin + 1, origin + horizon, freq="M"))
    mm = {f"{b}_MM": h[f"{b}_MM"].loc[:origin].copy() for b in BLOCKS + ["CPI", "ADMX", "UTIL"]}
    gw, _, _ = weights()
    wx, wu = sum(gw[g] for g in ("02", "07_3", "08")), gw["04"]
    drift = util_drift(h, origin)
    fx = h["FX_MM"].loc[:origin].copy()
    fp = fuel_path(h.loc[:origin], origin, months, fuel_qq)
    for m in months:
        fx.loc[m] = (fx_path or {}).get(m, 0.0)
        for b in ["CORE", "RAW", "ADMX"]:
            c = est[b]["coef"]
            v = c[f"M{m.month:02d}"] + c["L1"] * mm[f"{b}_MM"].loc[m - 1]
            if "FX_L1" in c:
                v += c["FX_L1"] * fx.loc[m - 1]
            mm[f"{b}_MM"].loc[m] = v
        mm["UTIL_MM"].loc[m] = (util_path or {}).get(m, drift)
        mm["ADM_MM"].loc[m] = (wx * mm["ADMX_MM"].loc[m] + wu * mm["UTIL_MM"].loc[m]) / (wx + wu)
        mm["FUEL_MM"].loc[m] = fp[m]
        w = est["W"]["coef"]
        mm["CPI_MM"].loc[m] = w["const"] + sum(w[f"{b}_MM"] * mm[f"{b}_MM"].loc[m] for b in BLOCKS)
    out = pd.DataFrame(index=pd.PeriodIndex(months, freq="M"))
    for k, s in mm.items():
        b = k[:-3]
        if b in ("ADMX", "UTIL"):
            out[k] = s.loc[months]
            continue
        out[k] = s.loc[months]
        # y/y chains the forecast m/m onto the actual series (headline and core from Gosstat y/y)
        full = pd.concat([h[f"{b}_MM"].loc[:origin], s.loc[months]])
        base = yoy_from_mm(full)
        if b in ("CPI", "CORE"):
            # anchor to the published y/y: y/y_t = (1 + y/y_{t-1}) * (1 + mm_t) / (1 + mm_{t-12}) - 1
            yy = h[f"{b}_YY"].loc[:origin].copy()
            for m in months:
                yy.loc[m] = ((1 + yy.loc[m - 1] / 100) * (1 + full.loc[m] / 100) / (1 + full.loc[m - 12] / 100) - 1) * 100
            out[f"{b}_YY"] = yy.loc[months]
        else:
            out[f"{b}_YY"] = base.loc[months]
    out["FX_MM"] = fx.loc[months]
    return out


# ---------- benchmark ----------
BENCH_REGS = ["FXY", "GAP", "D3"]


def bench_design(h: pd.DataFrame) -> pd.DataFrame:
    """Inputs of the benchmark at each origin: headline y/y, devaluation y/y, gap of household
    expectations to current inflation, and the 3-month change of y/y (momentum)."""
    x = pd.DataFrame({"Y": h["CPI_YY"], "FXY": h["FX_YY"], "EXP": h["EXP_HH"].ffill(limit=3)})
    x["GAP"] = x["EXP"] - x["Y"]
    x["D3"] = x["Y"] - x["Y"].shift(3)
    return x


def bench_fit(x: pd.DataFrame, k: int) -> dict:
    """y/y_{t+k} - y/y_t = a + b FX y/y_t + c (expectations - y/y)_t + d (y/y_t - y/y_{t-3})."""
    df = x[BENCH_REGS].assign(y=x["Y"].shift(-k) - x["Y"]).loc["2016-01":]
    df = df[~_war_mask(df.index + k) & ~_war_mask(df.index)].dropna()
    return ols(df["y"], df[BENCH_REGS].assign(const=1.0))


def benchmark(h: pd.DataFrame, origin: pd.Period, horizon: int = H) -> dict:
    """{k: headline y/y at origin+k}, estimated on data up to the origin."""
    x = bench_design(h.loc[:origin])
    cur, out = x.loc[origin], {}
    for k in range(1, horizon + 1):
        c = bench_fit(x, k)["coef"]
        out[k] = cur["Y"] + c["const"] + sum(c[r] * cur[r] for r in BENCH_REGS)
    return out


def benchmark_coefs(h: pd.DataFrame) -> dict:
    x = bench_design(h)
    return {k: bench_fit(x, k) for k in range(1, H + 1)}


# ---------- backtest ----------
def backtest(h: pd.DataFrame, first: str = BT_FIRST) -> pd.DataFrame:
    """Pseudo out-of-sample: every origin re-estimates on data up to it. FX and fuel use actual values
    (as if the inputs were right), so the errors measure the equations, not the input assumptions."""
    rows = []
    last = h["CPI_MM"].dropna().index[-1]
    origins = pd.period_range(first, last - 1, freq="M")
    fuel_actual = {}
    for q in sorted({str(p.asfreq("Q")) for p in h.index}):
        ms = pd.period_range(pd.Period(q, "Q").asfreq("M", "start"), pd.Period(q, "Q").asfreq("M", "end"))
        if all(m in h.index and not pd.isna(h.loc[m, "FUEL_MM"]) for m in ms):
            fuel_actual[q] = (np.prod([1 + h.loc[m, "FUEL_MM"] / 100 for m in ms]) - 1) * 100
    for o in origins:
        if _war_mask(pd.PeriodIndex([o]))[0]:
            continue
        hz = min(H, (last - o).n)
        est = estimate_blocks(h, o)
        fxp = {m: h.loc[m, "FX_MM"] for m in pd.period_range(o + 1, o + hz)}
        up = {m: h.loc[m, "UTIL_MM"] for m in pd.period_range(o + 1, o + hz)}
        nc = nowcast(h, o, est, fuel_qq=fuel_actual, fx_path=fxp, horizon=hz, util_path=up)
        nc0 = nowcast(h, o, est, fuel_qq=None, fx_path=None, horizon=hz)   # no knowledge of inputs
        bm = benchmark(h, o, hz)
        for k in range(1, hz + 1):
            t = o + k
            fact = h.loc[t, "CPI_YY"]
            war_t = bool(_war_mask(pd.PeriodIndex([t]))[0])
            rec = {"origin": str(o), "target": str(t), "h": k, "fact": fact, "war": war_t,
                   "NOWCAST": nc.loc[t, "CPI_YY"], "NOWCAST_RW": nc0.loc[t, "CPI_YY"], "BENCH": bm[k],
                   "NAIVE": h.loc[o, "CPI_YY"]}
            for b in BLOCKS:
                rec[f"{b}_FACT"] = h.loc[t, f"{b}_YY"]
                rec[f"{b}_NC"] = nc.loc[t, f"{b}_YY"]
            rows.append(rec)
    return pd.DataFrame(rows)


def accuracy(bt: pd.DataFrame, since: str | None = None) -> pd.DataFrame:
    d = bt[~bt.war]
    if since:
        d = d[d.origin >= since]
    out = []
    for k in sorted(d.h.unique()):
        x = d[d.h == k]
        r = {"h": k, "n": len(x)}
        for m in ["NOWCAST", "NOWCAST_RW", "BENCH", "NAIVE"]:
            e = x[m] - x["fact"]
            r[f"{m}_MAE"], r[f"{m}_RMSE"], r[f"{m}_BIAS"] = e.abs().mean(), np.sqrt((e ** 2).mean()), e.mean()
        for b in BLOCKS:
            e = x[f"{b}_NC"] - x[f"{b}_FACT"]
            r[f"{b}_MAE"] = e.abs().mean()
        out.append(r)
    return pd.DataFrame(out)


# ---------- forecast log ----------
def append_log(origin: pd.Period, nc: pd.DataFrame, bm: dict, run_date: str) -> pd.DataFrame:
    """One row per (origin, target month, model). Re-running the same origin replaces its rows."""
    rows = []
    for i, t in enumerate(nc.index, start=1):
        for model, v in (("NOWCAST", nc.loc[t, "CPI_YY"]), ("BENCH", bm[i])):
            rows.append({"run": run_date, "origin": str(origin), "target": str(t), "h": i, "model": model,
                         "forecast": round(float(v), 3)})
        for b in BLOCKS:
            rows.append({"run": run_date, "origin": str(origin), "target": str(t), "h": i, "model": f"NOWCAST_{b}",
                         "forecast": round(float(nc.loc[t, f"{b}_YY"]), 3)})
    new = pd.DataFrame(rows)
    if LOG_CSV.exists():
        old = pd.read_csv(LOG_CSV, dtype={"origin": str, "target": str})
        old = old[old.origin != str(origin)]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(LOG_CSV, index=False)
    return new


def score_log(h: pd.DataFrame) -> pd.DataFrame:
    """Errors of logged forecasts whose target month is out."""
    if not LOG_CSV.exists():
        return pd.DataFrame()
    lg = pd.read_csv(LOG_CSV, dtype={"origin": str, "target": str})
    def f(r):
        b = r.model.split("_")[1] if r.model.startswith("NOWCAST_") else "CPI"
        t = pd.Period(r.target, "M")
        return h[f"{b}_YY"].get(t, np.nan)
    lg["fact"] = lg.apply(f, axis=1)
    lg["error"] = lg.forecast - lg.fact
    return lg


if __name__ == "__main__":
    h = build_history(refresh=True)
    gw, bw, r2 = weights()
    print("block weights", {k: round(v, 3) for k, v in bw.items()}, "R2", r2)
    est = estimate_blocks(h)
    print("utilities drift", util_drift(h))
    for k, r in est.items():
        print(k, r["n"], round(r["r2"], 2), {v: round(c, 3) for v, c in r["coef"].items() if not v.startswith("M")})
