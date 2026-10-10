"""Load the sample with pandas: join the order book and trades to the market
questions, then build a 1-minute midpoint series for the busiest market.

    python examples/quickstart_pandas.py [path/to/bundle-folder]
"""
import sys
from pathlib import Path

import pandas as pd

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "data" / "polymarket-btc-4h-2026-08-19-day")

l1 = pd.read_parquet(DATA / "l1.parquet")
trades = pd.read_parquet(DATA / "trades.parquet")
# token_id is a 77-digit integer: always read it as a string.
tokens = pd.read_csv(DATA / "reference" / "tokens.csv", dtype={"token_id": str})
markets = pd.read_csv(DATA / "reference" / "markets.csv",
                      dtype={"yes_token_id": str, "no_token_id": str})

# Timestamps: ts_recv_ns is our receive time in nanoseconds (use it for ordering).
l1["ts"] = pd.to_datetime(l1.ts_recv_ns, utc=True)
trades["ts"] = pd.to_datetime(trades.ts_recv_ns, utc=True)

# Label every token with its market question and outcome.
labels = tokens[["token_id", "condition_id", "outcome_label"]].merge(
    markets[["condition_id", "question"]], on="condition_id")
trades = trades.merge(labels[["token_id", "question", "outcome_label"]], on="token_id")

print(f"L1 updates: {len(l1):,}   trades: {len(trades):,}   "
      f"from {l1.ts.min():%Y-%m-%d %H:%M} to {l1.ts.max():%H:%M} UTC\n")

per_market = (trades.groupby("question")
              .agg(trades=("price", "size"), contracts=("size", "sum"))
              .sort_values("trades", ascending=False))
print(per_market.round(1).to_string(), "\n")

# 1-minute midpoint of the YES token in the market with the most L1 updates,
# over the four hours the market covers (it closes at end_time).
busiest = l1.groupby("condition_id").size().idxmax()
m = markets.set_index("condition_id").loc[busiest]
end = pd.Timestamp(m.end_time)
yes = l1[l1.token_id == m.yes_token_id].set_index("ts").sort_index()
# An empty best_bid or best_ask means that side of the book was empty: no midpoint then.
book = yes.dropna(subset=["best_bid", "best_ask"])
mid = ((book.best_bid + book.best_ask) / 2).resample("1min").last().ffill()   # quiet minutes keep the last mid
mid = mid[end - pd.Timedelta(hours=4):end - pd.Timedelta(minutes=1)]
print(f"{m.question}: YES midpoint, {len(mid)} one-minute bars, "
      f"{mid.iloc[0]:.3f} at the open, {mid.iloc[-1]:.3f} in the last minute")
print(mid.head(5).round(4).to_string())
