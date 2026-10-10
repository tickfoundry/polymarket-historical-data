"""Query the parquet files in place with DuckDB SQL: depth resting within
2 cents of the touch, per market, from the 25-level L2 snapshots.

    python examples/quickstart_duckdb.py [path/to/bundle-folder]
"""
import sys
from pathlib import Path

import duckdb

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "data" / "polymarket-btc-4h-2026-08-19-day")

# Sum the ask sizes priced within 2 cents of the best ask, for every snapshot.
near_ask = " + ".join(
    f"CASE WHEN ask_px_{i} <= best_ask + 0.02 THEN coalesce(ask_sz_{i}, 0) ELSE 0 END"
    for i in range(1, 26))

print(duckdb.sql(f"""
    WITH m AS (
        SELECT condition_id, question, yes_token_id
        FROM read_csv('{DATA}/reference/markets.csv', all_varchar = true)
    )
    SELECT m.question,
           count(*)                            AS yes_snapshots,
           round(median(best_ask - best_bid) * 100, 2) AS median_spread_cents,
           round(median({near_ask}), 0)        AS median_ask_contracts_within_2c
    FROM read_parquet('{DATA}/l2.parquet') b
    JOIN m ON b.condition_id = m.condition_id AND b.token_id = m.yes_token_id
    WHERE best_bid IS NOT NULL AND best_ask IS NOT NULL
    GROUP BY m.question
    ORDER BY yes_snapshots DESC
"""))
