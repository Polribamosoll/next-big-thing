"""
Finnhub API wrapper with built-in rate limiting and retry logic.

Free tier limit: 60 requests/minute.
We stay under that via a sliding-window counter controlled by
MAX_REQUESTS_PER_MINUTE in config/settings.py.
"""

import time
import logging
import finnhub

# Import lazily so tests can patch config before it is evaluated
from config.settings import FINNHUB_API_KEY, MAX_REQUESTS_PER_MINUTE

logger = logging.getLogger(__name__)


class FinnhubClient:
    """Thin wrapper around the official finnhub-python client."""

    def __init__(self, api_key: str = None, max_rpm: int = None):
        self._api_key = api_key or FINNHUB_API_KEY
        self._max_rpm = max_rpm or MAX_REQUESTS_PER_MINUTE
        self._client = finnhub.Client(api_key=self._api_key)
        # Timestamps (float) of recent requests within the rolling 60-s window
        self._request_log: list[float] = []

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Block until we're allowed to fire the next request."""
        now = time.monotonic()
        # Drop timestamps older than 60 seconds
        self._request_log = [t for t in self._request_log if now - t < 60.0]

        if len(self._request_log) >= self._max_rpm:
            # Oldest request inside the window; wait until it ages out
            oldest = self._request_log[0]
            sleep_for = 60.0 - (now - oldest) + 0.1  # small buffer
            if sleep_for > 0:
                logger.debug("Rate limit reached — sleeping %.1fs", sleep_for)
                time.sleep(sleep_for)

        self._request_log.append(time.monotonic())

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

        Returns the raw Finnhub dict on success, or None when the API
        reports no data for that ticker/range.

        Raises the underlying exception after *retries* failed attempts.
        """
        for attempt in range(1, retries + 1):
            try:
                self._rate_limit()
                data = self._client.stock_candles(ticker, resolution, from_ts, to_ts)

                if data.get("s") == "no_data":
                    logger.info("No candle data for %s", ticker)
                    return None

                return data

            except finnhub.FinnhubAPIException as exc:
                logger.warning(
                    "Finnhub API error for %s (attempt %d/%d): %s",
                    ticker, attempt, retries, exc,
                )
                if attempt < retries:
                    time.sleep(2 ** attempt)  # exponential back-off
                else:
                    raise

            except Exception as exc:  # network errors, timeouts, etc.
                logger.warning(
                    "Unexpected error for %s (attempt %d/%d): %s",
                    ticker, attempt, retries, exc,
                )
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    raise
