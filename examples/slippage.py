"""Walk the historical L2 book for a market buy and compare the price you would
actually have paid with the price a naive backtest assumes (mid or best ask).

    python examples/slippage.py [path/to/bundle-folder]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "data" / "polymarket-btc-4h-2026-08-19-day")

l2 = pd.read_parquet(DATA / "l2.parquet")              # one full snapshot per book update
markets = pd.read_csv(DATA / "reference" / "markets.csv",
                      dtype={"yes_token_id": str, "no_token_id": str})

# Pick one outcome token: the YES leg of the busiest market of the day.
busiest = l2.groupby("condition_id").size().idxmax()
m = markets.set_index("condition_id").loc[busiest]
book = l2[l2.token_id == m.yes_token_id].sort_values("ts_recv_ns").reset_index(drop=True)

ask_px = book[[f"ask_px_{i}" for i in range(1, 26)]].to_numpy()   # per level, NaN past depth
ask_sz = book[[f"ask_sz_{i}" for i in range(1, 26)]].to_numpy()   # size is in contracts (shares)

def buy_vwap(notional_usd):
    """Average price paid for a market buy of `notional_usd`, walking the ask
    ladder snapshot by snapshot. NaN where the visible book is too thin."""
    cost = ask_px * ask_sz                                         # $ resting at each level
    cum = np.nancumsum(cost, axis=1)
    filled = np.minimum(cost, np.maximum(notional_usd - (cum - cost), 0))   # $ taken per level
    shares = np.nansum(filled / ask_px, axis=1)
    enough = np.nanmax(cum, axis=1) >= notional_usd
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(enough, notional_usd / shares, np.nan)

mid = (book.best_bid + book.best_ask) / 2
rows = []
for usd in (100, 500, 2000):
    vwap = buy_vwap(usd)
    rows.append({
        "order $": usd,
        "fillable": f"{np.mean(~np.isnan(vwap)):.1%}",            # share of snapshots with enough depth
        "median slip vs mid (¢)": np.nanmedian((vwap - mid) * 100),
        "p90 slip vs mid (¢)": np.nanpercentile((vwap - mid) * 100, 90),
        "median slip vs best ask (¢)": np.nanmedian((vwap - book.best_ask) * 100),
        "p90 slip vs best ask (¢)": np.nanpercentile((vwap - book.best_ask) * 100, 90),
    })
print(m.question)
print(f"{len(book):,} book snapshots of the YES token")
print(pd.DataFrame(rows).round(2).to_string(index=False))
