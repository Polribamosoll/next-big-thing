"""
Yahoo Finance data client (yfinance) — drop-in replacement for the former
Finnhub client.

Returns candle dicts in the same Finnhub-compatible shape so that the rest
of the codebase (GrowthDetector, etc.) needs no changes:

    {"t": [unix_ts, ...], "o": [...], "h": [...], "l": [...],
     "c": [...], "v": [...]}

No API key required.
"""

import logging
import time
import warnings
from datetime import datetime, timezone

import urllib3
import yfinance as yf
from curl_cffi.requests import Session as CurlSession

logger = logging.getLogger(__name__)

# Corporate proxy intercepts TLS; disable cert verification.
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

_SESSION = CurlSession(impersonate="chrome", verify=False)


class FinnhubClient:
    """yfinance-backed client with the same public interface as the former
    Finnhub wrapper so that call sites require zero changes."""

    def __init__(self, api_key: str = None, max_rpm: int = None):
        # api_key / max_rpm kept for signature compatibility — not used.
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_candles(
        self,
        ticker: str,
        from_ts: int,
        to_ts: int,
        resolution: str = "D",
        retries: int = 3,
    ) -> dict | None:
        """
        Fetch OHLCV daily candles for *ticker* between Unix timestamps
        *from_ts* and *to_ts*.

        Returns a Finnhub-compatible dict on success, or None when no data
        is available for the ticker/range.
        """
        start = datetime.fromtimestamp(from_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        end = datetime.fromtimestamp(to_ts, tz=timezone.utc).strftime("%Y-%m-%d")

        for attempt in range(1, retries + 1):
            try:
                df = yf.Ticker(ticker, session=_SESSION).history(start=start, end=end, interval="1d", auto_adjust=True)

                if df.empty:
                    logger.info("No candle data for %s", ticker)
                    return None

                df = df.sort_index()
                timestamps = [int(ts.timestamp()) for ts in df.index]

                return {
                    "t": timestamps,
                    "o": df["Open"].tolist(),
                    "h": df["High"].tolist(),
                    "l": df["Low"].tolist(),
                    "c": df["Close"].tolist(),
                    "v": df["Volume"].tolist(),
                }

            except Exception as exc:
                logger.warning(
                    "Error fetching %s (attempt %d/%d): %s",
                    ticker, attempt, retries, exc,
                )
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    raise
