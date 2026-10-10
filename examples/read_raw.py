"""Read the hour of raw websocket messages (21:00-22:00 UTC). Each line is a
capture envelope; payload_text holds the original Polymarket message verbatim.

    python examples/read_raw.py [path/to/bundle-folder]
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "data" / "polymarket-btc-4h-2026-08-19-day")

path = DATA / "raw.jsonl.gz"
if not path.exists():                      # the zip from tickfoundry.com ships it uncompressed
    path = DATA / "raw.jsonl"
opener = gzip.open if path.suffix == ".gz" else open

kinds, first_book = Counter(), None
with opener(path, "rt") as f:
    for line in f:
        msg = json.loads(line)
        kinds[msg["event_type"]] += 1
        if first_book is None and msg["event_type"] == "book":
            first_book = json.loads(msg["payload_text"])   # the upstream message, re-parsed

print(f"{sum(kinds.values()):,} messages")
for kind, n in kinds.most_common():
    print(f"  {kind:<18} {n:>7,}")
print("\nfirst 'book' message, as Polymarket sent it:")
print("  keys:", sorted(first_book))
print("  best 3 bids:", sorted(first_book["bids"], key=lambda l: -float(l["price"]))[:3])
