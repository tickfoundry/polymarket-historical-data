# Polymarket historical data: order book, trades and tick data (free sample)

A free, full-day sample of Polymarket historical data from [TickFoundry](https://tickfoundry.com/polymarket-historical-data): every top-of-book change, 25-level order book snapshots, the trade tape, an hour of the raw websocket feed, 1-minute candles and the reference tables, for one Polymarket series on one UTC day. Parquet and CSV, with working pandas, polars and DuckDB examples.

The l1, l2, trades and raw files use the same schema as every TickFoundry download, so code you write against this sample works on the full archive.

## What TickFoundry is

TickFoundry records Polymarket's order book and trades and sells the history per market and per day, as parquet or CSV bundles and through a REST API. It covers Hyperliquid and Kalshi as well. Catalog, docs and plans are at [tickfoundry.com](https://tickfoundry.com).

## What's in this repo

Series **BTC Up or Down 4h** (`series_id` 10331, slug `btc-up-or-down-4h`) on **2026-08-19**, the full UTC day: 13 events, 13 markets, 26 outcome tokens. Everything is in `data/polymarket-btc-4h-2026-08-19-day/`.

| File | Contents | Rows | Size |
|---|---|---|---|
| `l1.parquet`, `l1.csv` | Top of book on every change: best bid and ask with sizes | 99,362 | 1.4 MB, 22 MB |
| `l2.parquet` | Full order book snapshot after every update, best 25 levels per side | 640,735 | 19 MB |
| `trades.parquet`, `trades.csv` | Trade tape from the websocket, one row per fill | 4,781 | 0.3 MB, 1.3 MB |
| `raw.jsonl.gz` | The exact inbound websocket messages, 21:00 to 22:00 UTC only | 40,149 | 3.1 MB |
| `candles/tape_1m.csv` | 1-minute OHLCV from the trade tape | 1,361 | 0.3 MB |
| `candles/mid_1m.csv` | 1-minute candles of the order book midpoint | 2,656 | 0.6 MB |
| `reference/` | Series, events, markets and outcome tokens, as CSV and JSON | 1 / 13 / 13 / 26 | 0.1 MB |

`preview/` holds short CSV excerpts (L1, L2 and trades from 17:00 UTC on the "August 19, 12:00PM-4:00PM ET" market) that GitHub renders as tables, so you can look at the data before cloning.

The same day is a free download at [tickfoundry.com/samples](https://tickfoundry.com/samples), as a parquet zip or a CSV zip. The CSV zip includes the L2 book as CSV (412 MB), which is too large for this repo.

## Quickstart

```bash
git clone https://github.com/tickfoundry/polymarket-historical-data
cd polymarket-historical-data
pip install -r requirements.txt
python examples/quickstart_pandas.py
```

pandas:

```python
import pandas as pd

d = "data/polymarket-btc-4h-2026-08-19-day/"
l1 = pd.read_parquet(d + "l1.parquet")
l2 = pd.read_parquet(d + "l2.parquet")
trades = pd.read_parquet(d + "trades.parquet")
markets = pd.read_csv(d + "reference/markets.csv", dtype={"yes_token_id": str, "no_token_id": str})

l1["ts"] = pd.to_datetime(l1.ts_recv_ns, utc=True)
yes = l1[l1.token_id.isin(markets.yes_token_id)]   # the YES side of every market
```

polars:

```python
import polars as pl

trades = pl.read_parquet("data/polymarket-btc-4h-2026-08-19-day/trades.parquet")
print(trades.group_by("condition_id").agg(fills=pl.len(), contracts=pl.col("size").sum()))
```

DuckDB:

```sql
SELECT condition_id, count(*) AS fills, sum(size) AS contracts, sum(price * size) AS usdc
FROM 'data/polymarket-btc-4h-2026-08-19-day/trades.parquet'
GROUP BY condition_id
ORDER BY fills DESC;
```

### Examples

| Script | What it does |
|---|---|
| `examples/quickstart_pandas.py` | Joins trades to market questions and builds a 1-minute midpoint series |
| `examples/quickstart_polars.py` | Per-market quote updates, time-weighted spread and traded volume |
| `examples/quickstart_duckdb.py` | SQL over the L2 parquet: median spread and depth within 2 cents of the best ask |
| `examples/read_raw.py` | Reads the raw websocket hour and re-parses the original Polymarket messages |
| `examples/slippage.py` | Walks the L2 ask ladder to price market buys of $100, $500 and $2,000 |

Every script takes an optional folder path, so it also runs on the unpacked zip from tickfoundry.com/samples. Tested with Python 3.12, pandas 3.0, polars 2.0, DuckDB 1.5 and pyarrow 26.

## Example: what a market buy actually costs

A backtest that fills at the midpoint or the best ask assumes the book was deep enough. `examples/slippage.py` walks the recorded ask ladder snapshot by snapshot for the YES token of the market with the most book updates in the sample:

```
Bitcoin Up or Down - August 19, 4:00PM-8:00PM ET
93,016 book snapshots of the YES token
 order $ fillable  median slip vs mid (¢)  p90 slip vs mid (¢)  median slip vs best ask (¢)  p90 slip vs best ask (¢)
     100    99.9%                    1.09                 2.00                         0.17                      0.72
     500    99.9%                    2.36                 3.81                         1.48                      2.72
    2000    99.0%                    4.94                 7.28                         3.83                      6.28
```

A $2,000 market buy paid a median 4.94¢ over the midpoint on this market, 3.83¢ of it beyond the best ask. Only the L2 book shows that. The full method is in [How to backtest Polymarket](https://tickfoundry.com/how-to-backtest-polymarket).

## Schema

### Timestamps

Every row carries two timestamps:

- `ts_recv_ns`: our receive time in nanoseconds since the Unix epoch, taken as close to the socket read as possible. Use it for ordering.
- `ts_src_ms`: Polymarket's own timestamp in milliseconds since the Unix epoch, when the message carries one.

There is no ISO-8601 column. Derive one with `pd.to_datetime(df.ts_recv_ns, utc=True)`.

### Identifiers and joins

- `condition_id` (hex) identifies a market. It joins to `reference/markets.csv` directly.
- `token_id` identifies one outcome token. It is a 77-digit integer, so always read it as a string. Each market's two tokens are `markets.yes_token_id` and `markets.no_token_id`.
- Full chain: `token_id` to `tokens.token_id`, then `tokens.market_id` to `markets.market_id`, then `markets.event_id` to `events.event_id`.
- Prices are in USDC per contract, between 0 and 1. Sizes are in contracts (shares).

### l1: top of book

| Column | Meaning |
|---|---|
| `ts_src_ms`, `ts_recv_ns` | Timestamps (see above) |
| `condition_id`, `token_id` | Market and outcome token |
| `best_bid`, `best_bid_size` | Best bid price and the contracts resting there |
| `best_ask`, `best_ask_size` | Best ask price and the contracts resting there |
| `spread` | `best_ask - best_bid`, rounded to 3 decimals. Compute it from the two columns when the 0.25¢ tick matters |
| `source_event_type` | The upstream message type that produced the update |
| `msg_seq` | Capture sequence number of the upstream message |

An empty `best_bid` or `best_ask` means that side of the book was empty.

### l2: order book snapshots

One row per book update per token, holding the full book after the update.

| Column | Meaning |
|---|---|
| `ts_src_ms`, `ts_recv_ns`, `condition_id`, `token_id`, `msg_seq` | As in l1 |
| `event_kind` | `snapshot` (a full `book` message from the venue) or `update` (a `price_change` applied to the book) |
| `source_event_type` | The upstream message type |
| `bid_levels`, `ask_levels` | Number of price levels on each side of the book |
| `best_bid`, `best_ask` | Top of book from our reconstructed book |
| `payload_best_bid`, `payload_best_ask` | Top of book as the venue's message stated it |
| `bid_ask_reconciles` | True when the two agree |
| `bid_px_1` to `bid_px_25`, `bid_sz_1` to `bid_sz_25` | Bid ladder, best first, NaN past the deepest level |
| `ask_px_1` to `ask_px_25`, `ask_sz_1` to `ask_sz_25` | Ask ladder, best first, NaN past the deepest level |

### trades

One row per fill, from the venue's `last_trade_price` websocket messages (socket-derived, not reconstructed from the chain).

| Column | Meaning |
|---|---|
| `ts_src_ms`, `ts_recv_ns`, `condition_id`, `token_id`, `msg_seq` | As in l1 |
| `price`, `size` | Fill price and contracts |
| `side` | `BUY` or `SELL`, the taker's side as the venue reports it |
| `fee_rate_bps` | The websocket's fee field. It is 0 on every row in practice; fees actually paid are recorded on-chain |
| `transaction_hash` | The Polygon transaction that settled the fill |

### raw.jsonl.gz: the websocket feed

One JSON object per line: a capture envelope around the verbatim upstream message.

```json
{
  "source": "polymarket_market_ws",
  "msg_seq": 545692077,
  "ts_recv_ns": 1779235200081988852,
  "ts_src": "1779235200023",
  "event_type": "price_change",
  "token_id": null,
  "condition_id": "0x...",
  "parse_ok": true,
  "parse_error": null,
  "payload_text": "{...the original Polymarket message as a JSON string...}"
}
```

`event_type` is one of `price_change`, `best_bid_ask`, `book`, `last_trade_price` or `tick_size_change`. `payload_text` is preserved byte for byte, including Polymarket's own `hash` fields, so you can check that the normalized rows rebuild from the upstream messages. `ts_src` is Polymarket's timestamp in milliseconds, as a string.

### candles

`tape_1m.csv` is built from the trade tape, so a minute with no trade has no row: `token_id, condition_id, ts, open, high, low, close, vwap, volume_contracts, volume_usdc, trade_count, buy_count, buy_volume_contracts`.

`mid_1m.csv` is built from the top-of-book midpoint, excluding one-sided, crossed and placeholder books wider than 10 cents: `token_id, condition_id, ts, mid_open, mid_high, mid_low, mid_close, bid_close, ask_close, spread_twa, spread_time_ms, quote_events`.

`ts` is the bar's open time in UTC. The two files are separate products on separate clocks and are never merged.

### reference

`series`, `events`, `markets` and `tokens`, as CSV and JSON, with Polymarket's metadata: questions, resolution text, start and end times, and the YES/NO token ids. In this repo `tick_size` in `reference/markets` is written as the venue states it (`0.001`, `0.01`); the zip on tickfoundry.com carries the same values with float noise in the trailing digits.

## The full archive

The hierarchy is series, then events, then markets (`condition_id`), then outcome tokens (`token_id`). TickFoundry sells a series (all its repeating markets) or a standalone event, per day.

- Order book history: L1 top of book on every change and 25-level L2 depth, back to February 2026.
- Trade tape from the websocket: from April 2026.
- Our own continuous capture, including the raw websocket messages with nanosecond receive timestamps: since 2026-05-11.
- On-chain trade fills read from Polygon settlement: back to 2023, per market, thinner before 2026.
- Hyperliquid: the order book on every block since January 2025, trades from March 2025.
- Kalshi: the order book on every change since 27 September 2026, and every trade on the exchange back to June 2021.

Coverage differs by market. The [catalog](https://tickfoundry.com/catalog) shows the dates available for each one.

- Product page: [tickfoundry.com/polymarket-historical-data](https://tickfoundry.com/polymarket-historical-data)
- Free samples: [tickfoundry.com/samples](https://tickfoundry.com/samples). A free account can also download 5 market·days of your choice from July 2026.
- Plans: [tickfoundry.com/pricing](https://tickfoundry.com/pricing)
- Docs and API: [tickfoundry.com/docs](https://tickfoundry.com/docs)

## Licence

The code in `examples/` is MIT-licensed. The data files are provided under the [TickFoundry Terms](https://tickfoundry.com/legal/terms) for evaluation, research and personal use: see [DATA-LICENSE.md](DATA-LICENSE.md). TickFoundry is an independent data product and is not affiliated with, endorsed by, or sponsored by Polymarket.
