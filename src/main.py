"""
Stock growth scanner — main entry point.

Run from the project root:

    python src/main.py
    python src/main.py --limit 20
    python src/main.py --tickers config/my_tickers.csv --limit 50
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta

# Ensure project root is on sys.path when the script is run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    FINNHUB_API_KEY,
    GROWTH_THRESHOLD_PCT,
    LOOKBACK_DAYS,
    MAX_REQUESTS_PER_MINUTE,
    VOLUME_SPIKE_MULTIPLIER,
)
from src.analysis.growth_detector import GrowthDetector
from src.data.finnhub_client import FinnhubClient
from src.data.ticker_loader import load_custom_tickers, load_sp500_tickers
from src.output.formatter import print_summary, save_csv

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def run(
    ticker_file: str | None = None,
    limit: int | None = None,
    refresh_tickers: bool = False,
) -> list:
    if not FINNHUB_API_KEY:
        sys.exit(
            "ERROR: FINNHUB_API_KEY is not set.\n"
            "Copy .env.example to .env and add your Finnhub API key."
        )

    # ── 1. Load tickers ──────────────────────────────────────────────
    if ticker_file:
        tickers = load_custom_tickers(ticker_file)
        print(f"Loaded {len(tickers)} tickers from {ticker_file}")
    else:
        print("Loading S&P 500 tickers …")
        tickers = load_sp500_tickers(refresh=refresh_tickers)
        print(f"  {len(tickers)} tickers loaded.")

    if limit:
        tickers = tickers[:limit]

    # ── 2. Set up date range ─────────────────────────────────────────
    to_ts = int(datetime.now().timestamp())
    # Fetch extra days so that the longest window has enough candles
    extra_days = max(10, max([5, 10, 30]) + 5)
    from_ts = int((datetime.now() - timedelta(days=LOOKBACK_DAYS + extra_days)).timestamp())

    print(
        f"\nScanning {len(tickers)} tickers | "
        f"last {LOOKBACK_DAYS} days | "
        f"growth threshold {GROWTH_THRESHOLD_PCT:.1f}% | "
        f"volume spike {VOLUME_SPIKE_MULTIPLIER:.1f}x\n"
    )

    # ── 3. Fetch & analyse ───────────────────────────────────────────
    client = FinnhubClient()
    detector = GrowthDetector(
        windows=[5, 10, 30],
        threshold_pct=GROWTH_THRESHOLD_PCT,
        volume_spike_multiplier=VOLUME_SPIKE_MULTIPLIER,
    )

    results = []
    errors = 0

    for idx, ticker in enumerate(tickers, start=1):
        print(f"  [{idx:>4}/{len(tickers)}]  {ticker:<8}", end="\r", flush=True)
        try:
            candles = client.get_candles(ticker, from_ts, to_ts)
            result = detector.analyze(ticker, candles)
            if result:
                results.append(result)
        except Exception as exc:
            errors += 1
            logger.warning("Failed to process %s: %s", ticker, exc)

    print()  # newline after the progress line
    if errors:
        print(f"  {errors} tickers could not be fetched (see warnings above).\n")

    # ── 4. Output ────────────────────────────────────────────────────
    print_summary(results)
    save_csv(results)

    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan stocks for significant price growth using Finnhub data."
    )
    parser.add_argument(
        "--tickers",
        metavar="FILE",
        help="Path to a custom CSV ticker file (must have a 'ticker' column). "
             "Defaults to S&P 500.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process only the first N tickers (useful for quick tests).",
    )
    parser.add_argument(
        "--refresh-tickers",
        action="store_true",
        help="Re-fetch the S&P 500 list from Wikipedia even if a cached copy exists.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(
        ticker_file=args.tickers,
        limit=args.limit,
        refresh_tickers=args.refresh_tickers,
    )
