"""Same data with polars: per-market quote and trade counts, and the
time-weighted spread of each market's YES book.

    python examples/quickstart_polars.py [path/to/bundle-folder]
"""
import sys
from pathlib import Path

import polars as pl

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "data" / "polymarket-btc-4h-2026-08-19-day")

markets = pl.read_csv(DATA / "reference" / "markets.csv",
                      schema_overrides={"yes_token_id": pl.String, "no_token_id": pl.String})

yes_books = (
    pl.scan_parquet(DATA / "l1.parquet")
    .join(markets.lazy().select("condition_id", "question", pl.col("yes_token_id").alias("token_id")),
          on=["condition_id", "token_id"])                  # keep the YES side only
    .sort("token_id", "ts_recv_ns")
    .with_columns(
        spread=pl.col("best_ask") - pl.col("best_bid"),     # exact; the stored `spread` column is rounded to 3 dp
        held_ns=pl.col("ts_recv_ns").shift(-1).over("token_id") - pl.col("ts_recv_ns"),
    )
    .drop_nulls(["spread", "held_ns"])                     # null spread = one side of the book was empty
    .group_by("question")
    .agg(
        updates=pl.len(),
        twa_spread_cents=(pl.col("spread") * pl.col("held_ns")).sum() / pl.col("held_ns").sum() * 100,
    )
)

trades = (
    pl.scan_parquet(DATA / "trades.parquet")
    .join(markets.lazy().select("condition_id", "question"), on="condition_id")
    .group_by("question")
    .agg(trades=pl.len(), contracts=pl.col("size").sum())
)

out = yes_books.join(trades, on="question", how="left").sort("updates", descending=True).collect()
with pl.Config(tbl_rows=20, fmt_str_lengths=60, tbl_width_chars=140):
    print(out.with_columns(pl.col("twa_spread_cents", "contracts").round(2)))
