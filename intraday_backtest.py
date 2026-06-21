#!/usr/bin/env python3
"""
Kronos INTRADAY edge test — Step 0c of the highest-best plan.

WHY THIS EXISTS
---------------
Step 0 and Step 0b tested Kronos on *daily* bars (US equities + crypto) and found
no exploitable directional edge: 0/18 cells cleared any gate, and the predicted
90% bands covered truth only 30-67% of the time (overconfident / too narrow).

But Kronos's published benchmarks are on *intraday Chinese A-share K-lines*. US
*daily* bars may simply be off-distribution for the model. Before we abandon the
AI-signal plays, the honest experiment is to test Kronos where it is on-distribution:
short-horizon INTRADAY candles. Crypto (BTC/ETH/SOL) is used because it trades 24/7,
has clean 1h history, and most resembles continuous K-line data.

This harness is SELF-CONTAINED. It does not import the original backtest.py — it
only depends on the Kronos service HTTP contract that already runs on spark-24:
    POST /api/load-model   {"model_key": "...", "device": "cuda"}
    POST /api/predict      {"file_path": "<csv>", "lookback": N, "pred_len": H,
                            "sample_count": 1}
and on yfinance for OHLCV. Copy it to spark-24 and run it there.

GATES (identical to Step 0b so results are directly comparable):
    A. high-confidence directional accuracy: Wilson CI lower > 0.50 AND hc_n >= 15
    B. conviction-weighted Sharpe (net 5bp) >= 0.5 AND |t_stat| >= 2.0
    C. 90% band coverage in [0.85, 0.95]  (calibration)

USAGE (on spark-24):
    python intraday_backtest.py --model kronos-base --device cuda \
        --interval 60m --horizons 1,4,12 --windows 150 --samples 12
    python intraday_backtest.py --report results/scored_<tag>.jsonl   # report only
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import os
import statistics
import sys
import tempfile
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
SHARED_TMP = os.path.join(HERE, "tmp")  # service runs PrivateTmp=true; share via app dir

KRONOS_URL = os.environ.get("KRONOS_URL", "http://127.0.0.1:7070")

# 24/7 crypto = closest match to the intraday K-line distribution Kronos trained on.
DEFAULT_UNDERLYINGS = ["BTC-USD", "ETH-USD", "SOL-USD"]

# Gate constants — kept identical to Step 0b.
CONVICTION_THRESHOLD = 0.20   # |2*p_up - 1| > 0.20 == "high confidence"
TX_COST_BPS = 5.0             # round-trip transaction cost assumption
PERIODS_PER_YEAR = {          # for Sharpe annualization, by bar interval
    "60m": 24 * 365,
    "30m": 48 * 365,
    "15m": 96 * 365,
    "5m":  288 * 365,
    "1h":  24 * 365,
}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def fetch_ohlcv(symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
    """Pull intraday OHLCV via yfinance. yfinance caps 1h history at ~730d."""
    import yfinance as yf

    yf_interval = "60m" if interval in ("1h", "60m") else interval
    period_days = min(lookback_days, 729)
    df = yf.download(
        symbol,
        period=f"{period_days}d",
        interval=yf_interval,
        auto_adjust=False,
        progress=False,
    )
    if df.empty:
        raise RuntimeError(f"no data for {symbol} @ {yf_interval}")
    # flatten possible multiindex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df = df.rename(columns=str.lower).reset_index()
    ts_col = "datetime" if "datetime" in df.columns else df.columns[0]
    out = pd.DataFrame({
        "timestamps": pd.to_datetime(df[ts_col]),
        "open":  df["open"].astype(float),
        "high":  df["high"].astype(float),
        "low":   df["low"].astype(float),
        "close": df["close"].astype(float),
        "volume": df["volume"].astype(float) if "volume" in df.columns else 0.0,
    }).dropna().reset_index(drop=True)
    return out


# --------------------------------------------------------------------------- #
# kronos service
# --------------------------------------------------------------------------- #
def load_model(model_key: str, device: str) -> None:
    r = requests.post(
        f"{KRONOS_URL}/api/load-model",
        json={"model_key": model_key, "device": device},
        timeout=600,
    )
    r.raise_for_status()
    print(f"[load] {r.json()}")


def predict_paths(df_hist: pd.DataFrame, pred_len: int, n_samples: int) -> List[pd.DataFrame]:
    """
    Build a distribution of future paths by calling /api/predict n_samples times
    with sample_count=1. The endpoint requires len(df) >= lookback + pred_len so it
    can read output timestamps from rows [lookback : lookback+pred_len]; we append
    pred_len placeholder rows whose *timestamps* continue the cadence (their OHLCV
    is not consumed for the forecast, only the time index).
    """
    os.makedirs(SHARED_TMP, exist_ok=True)
    paths: List[pd.DataFrame] = []
    with tempfile.TemporaryDirectory(dir=SHARED_TMP) as td:
        csv_path = os.path.join(td, "hist.csv")
        hist = df_hist.copy().reset_index(drop=True)
        hist["timestamps"] = pd.to_datetime(hist["timestamps"])
        step = (hist["timestamps"].iloc[-1] - hist["timestamps"].iloc[-2]
                if len(hist) > 1 else pd.Timedelta(hours=1))
        last_ts = hist["timestamps"].iloc[-1]
        future_ts = pd.date_range(start=last_ts + step, periods=pred_len, freq=step)
        last = hist.iloc[-1]
        future = pd.DataFrame({
            "timestamps": future_ts,
            "open": last["open"], "high": last["high"], "low": last["low"],
            "close": last["close"], "volume": last.get("volume", 0.0),
        })
        pd.concat([hist, future], ignore_index=True).to_csv(csv_path, index=False)

        body = {
            "file_path": csv_path,
            "lookback": len(df_hist),
            "pred_len": pred_len,
            "sample_count": 1,
        }
        for _ in range(n_samples):
            r = requests.post(f"{KRONOS_URL}/api/predict", json=body, timeout=300)
            r.raise_for_status()
            pred = pd.DataFrame(r.json()["prediction"])
            paths.append(pred)
    return paths


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def score_window(df_hist: pd.DataFrame, df_future: pd.DataFrame,
                 horizons: List[int], n_samples: int) -> Dict[int, dict]:
    pred_len = max(horizons)
    paths = predict_paths(df_hist, pred_len, n_samples)
    last_close = float(df_hist["close"].iloc[-1])
    out: Dict[int, dict] = {}

    for h in horizons:
        sample_closes = np.array([
            float(p["close"].iloc[h - 1]) for p in paths if len(p) >= h
        ])
        if sample_closes.size == 0 or h > len(df_future):
            continue
        truth_close = float(df_future["close"].iloc[h - 1])
        truth_up = int(truth_close >= last_close)
        truth_ret = (truth_close - last_close) / last_close if last_close > 0 else 0.0

        mean_pred = float(sample_closes.mean())
        median_pred = float(np.median(sample_closes))
        p_up = float((sample_closes >= last_close).mean())
        conviction = 2.0 * p_up - 1.0
        direction_correct = int((median_pred >= last_close) == bool(truth_up))
        mape = abs(mean_pred - truth_close) / truth_close if truth_close else float("nan")
        brier = (p_up - truth_up) ** 2
        q = np.quantile(sample_closes, [0.05, 0.25, 0.75, 0.95])

        out[h] = {
            "horizon": h,
            "last_close": last_close,
            "truth_close": truth_close,
            "truth_ret": truth_ret,
            "truth_up": truth_up,
            "median_pred_close": median_pred,
            "p_up_kronos": p_up,
            "conviction": conviction,
            "direction_correct": direction_correct,
            "mape_close": mape,
            "brier_up": brier,
            "n_samples_used": int(sample_closes.size),
            "truth_in_90pct_band": int(q[0] <= truth_close <= q[3]),
            "truth_in_50pct_band": int(q[1] <= truth_close <= q[2]),
        }
    return out


def run_backtest(args) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    horizons = [int(x) for x in args.horizons.split(",")]
    underlyings = args.symbols.split(",") if args.symbols else DEFAULT_UNDERLYINGS
    tag = args.tag or f"intraday_{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
    out_path = os.path.join(RESULTS_DIR, f"scored_{tag}.jsonl")

    load_model(args.model, args.device)
    lookback, pred_len = args.lookback, max(horizons)

    written = 0
    with open(out_path, "w") as fout:
        for sym in underlyings:
            try:
                df = fetch_ohlcv(sym, args.interval, args.history_days)
            except Exception as e:  # noqa: BLE001
                print(f"[skip] {sym}: {e}", file=sys.stderr)
                continue
            usable = len(df) - lookback - pred_len
            if usable <= 0:
                print(f"[skip] {sym}: only {len(df)} bars, need >"
                      f"{lookback + pred_len}", file=sys.stderr)
                continue
            stride = max(1, usable // args.windows)
            starts = range(0, usable, stride)
            print(f"[{sym}] {len(df)} bars  ->  {len(list(starts))} windows "
                  f"(stride={stride})")
            for i in range(0, usable, stride):
                hist = df.iloc[i:i + lookback]
                fut = df.iloc[i + lookback:i + lookback + pred_len]
                try:
                    scored = score_window(hist, fut, horizons, args.samples)
                except Exception as e:  # noqa: BLE001
                    print(f"  window {i} failed: {e}", file=sys.stderr)
                    continue
                for h, rec in scored.items():
                    rec.update({"symbol": sym, "interval": args.interval,
                                "window_start": i})
                    fout.write(json.dumps(rec) + "\n")
                    written += 1
                fout.flush()
    print(f"[done] {written} rows -> {out_path}")
    return out_path


# --------------------------------------------------------------------------- #
# report (gates identical to Step 0b)
# --------------------------------------------------------------------------- #
def wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def strategy_metrics(entries: List[dict], periods_per_year: float, horizon: int) -> dict:
    rets = []
    for e in entries:
        pos = float(e.get("conviction", 0.0))
        net = pos * float(e.get("truth_ret", 0.0)) - (TX_COST_BPS / 1e4) * abs(pos)
        rets.append(net)
    if not rets:
        return {"sharpe_5bp": 0.0, "t_stat": 0.0, "mean_ret_bp": 0.0}
    mean = statistics.mean(rets)
    std = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    ann = math.sqrt(max(1.0, periods_per_year / max(1, horizon)))
    sharpe = (mean / std * ann) if std > 0 else 0.0
    se = (std / math.sqrt(len(rets))) if std > 0 else 0.0
    t_stat = (mean / se) if se > 0 else 0.0
    return {"sharpe_5bp": sharpe, "t_stat": t_stat, "mean_ret_bp": mean * 1e4}


def report(jsonl_path: str) -> int:
    rows = [json.loads(l) for l in open(jsonl_path) if l.strip()]
    if not rows:
        print(f"no rows in {jsonl_path}", file=sys.stderr)
        return 2
    interval = rows[0].get("interval", "60m")
    ppy = PERIODS_PER_YEAR.get(interval, 24 * 365)

    by_key: Dict[Tuple[str, int], List[dict]] = defaultdict(list)
    for r in rows:
        by_key[(r["symbol"], int(r["horizon"]))].append(r)

    print(f"\n{'='*118}")
    print(f" KRONOS INTRADAY EDGE REPORT (Step 0c)  rows={len(rows)}  "
          f"interval={interval}  src={os.path.basename(jsonl_path)}")
    print(f"{'='*118}")
    print(f" {'asset':<8} {'h':>2} {'N':>4} | {'dir_acc':>7} {'ci95':>14} "
          f"{'brier':>6} | {'hc_n':>4} {'hc_acc':>6} {'hc_ci95':>14} | "
          f"{'cov90':>5} | {'sharpe':>7} {'t':>5} {'µbp':>6} | gate")
    print(" " + "-" * 116)

    out_report, passes = [], []
    for (sym, h), es in sorted(by_key.items()):
        n = len(es)
        nc = sum(int(e["direction_correct"]) for e in es)
        acc = nc / n
        lo, hi = wilson_ci(nc, n)
        brier = statistics.mean(e["brier_up"] for e in es)

        hc = [e for e in es if abs(float(e["conviction"])) > CONVICTION_THRESHOLD]
        hc_n = len(hc)
        hc_c = sum(int(e["direction_correct"]) for e in hc)
        hc_acc = hc_c / hc_n if hc_n else 0.0
        hc_lo, hc_hi = wilson_ci(hc_c, hc_n)
        cov90 = statistics.mean(e["truth_in_90pct_band"] for e in es)

        st = strategy_metrics(es, ppy, h)
        gate_A = hc_lo > 0.50 and hc_n >= 15
        gate_B = st["sharpe_5bp"] >= 0.5 and abs(st["t_stat"]) >= 2.0
        gate_C = 0.85 <= cov90 <= 0.95
        tags = "+".join([g for g, ok in
                         (("A", gate_A), ("B", gate_B), ("C", gate_C)) if ok]) or "—"

        print(f" {sym:<8} {h:>2} {n:>4} | {acc:>7.3f} [{lo:.3f},{hi:.3f}] "
              f"{brier:>6.3f} | {hc_n:>4} {hc_acc:>6.3f} [{hc_lo:.3f},{hc_hi:.3f}] | "
              f"{cov90:>5.3f} | {st['sharpe_5bp']:>+7.2f} {st['t_stat']:>+5.2f} "
              f"{st['mean_ret_bp']:>+6.1f} | {tags}")

        rec = {"symbol": sym, "horizon": h, "n": n, "dir_acc": acc,
               "hc_acc": hc_acc, "hc_n": hc_n, "cov90": cov90,
               **st, "gates": tags, "passed": tags != "—"}
        out_report.append(rec)
        if rec["passed"]:
            passes.append(rec)

    print("\n Gates:  A=high-conf acc CI>0.50 & hc_n>=15   "
          "B=Sharpe>=0.5 & |t|>=2.0   C=cov90 in [0.85,0.95]")
    print(f" Pass count: {len(passes)} of {len(out_report)} cells")
    if not passes:
        print(" No cell cleared any gate at intraday horizons either — "
              "Kronos shows no exploitable edge. Pivot to basis-trade harvester.")
    else:
        print(" PASSING cells (Kronos may be on-distribution intraday):")
        for r in passes:
            print(f"   {r['symbol']:<8} h={r['horizon']:>2} gates={r['gates']} "
                  f"hc_acc={r['hc_acc']:.3f}({r['hc_n']}) "
                  f"sharpe={r['sharpe_5bp']:+.2f} cov90={r['cov90']:.2f}")

    out_json = os.path.join(RESULTS_DIR, "edge_report_step0c.json")
    json.dump({"source": jsonl_path, "interval": interval, "report": out_report},
              open(out_json, "w"), indent=2)
    print(f"\n full report -> {out_json}\n{'='*118}\n")
    return 0


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", help="report-only on an existing scored_*.jsonl")
    ap.add_argument("--model", default="kronos-base")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--symbols", default="", help="comma list; default BTC/ETH/SOL-USD")
    ap.add_argument("--interval", default="60m", help="60m/30m/15m/5m")
    ap.add_argument("--horizons", default="1,4,12", help="bars ahead, comma list")
    ap.add_argument("--lookback", type=int, default=400)
    ap.add_argument("--windows", type=int, default=150, help="target windows/asset")
    ap.add_argument("--samples", type=int, default=12, help="stochastic paths/window")
    ap.add_argument("--history-days", type=int, default=729)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    if args.report:
        return report(args.report)
    scored = run_backtest(args)
    return report(scored)


if __name__ == "__main__":
    sys.exit(main())
