"""
Growth detection logic.

GrowthDetector ingests raw Finnhub candle data for a single ticker and
produces a GrowthResult that summarises price momentum and volume spikes
across configurable look-back windows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class GrowthResult:
    ticker: str
    latest_close: float
    # Mapping of window (days) -> % price change over that window
    growth_pct: dict[int, float]
    volume_spike: bool
    avg_volume: float
    latest_volume: float
    flagged: bool
    # Human-readable reason(s) for flagging
    reasons: list[str] = field(default_factory=list)


class GrowthDetector:
    """
    Analyse OHLCV data for price momentum and volume anomalies.

    Parameters
    ----------
    windows : list[int]
        Look-back windows in trading days (e.g. [5, 10, 30]).
    threshold_pct : float
        Flag a ticker when growth in *any* window exceeds this value (%).
    volume_spike_multiplier : float
        Flag a ticker when the latest day's volume is >= this multiple
        of the historical average volume.
    """

    def __init__(
        self,
        windows: list[int] = None,
        threshold_pct: float = 20.0,
        volume_spike_multiplier: float = 2.0,
    ):
        self.windows = sorted(windows or [5, 10, 30])
        self.threshold_pct = threshold_pct
        self.volume_spike_multiplier = volume_spike_multiplier

    # ------------------------------------------------------------------

    def analyze(self, ticker: str, candle_data: dict | None) -> GrowthResult | None:
        """
        Analyse *candle_data* (the dict returned by FinnhubClient.get_candles).

        Returns a GrowthResult, or None when the data is absent / unusable.
        """
        if not candle_data or candle_data.get("s") == "no_data":
            return None

        df = self._to_dataframe(candle_data)
        if df is None or len(df) < 2:
            logger.debug("Insufficient data for %s (%d rows)", ticker, len(df) if df is not None else 0)
            return None

        latest_close = float(df["close"].iloc[-1])
        growth_pct: dict[int, float] = {}

        for window in self.windows:
            # We need at least window+1 rows to compute a meaningful change
            if len(df) >= window + 1:
                base_close = float(df["close"].iloc[-(window + 1)])
                if base_close != 0:
                    pct = (latest_close - base_close) / base_close * 100
                    growth_pct[window] = round(pct, 2)

        # Volume spike: compare latest day vs. historical average (excluding today)
        avg_volume = float(df["volume"].iloc[:-1].mean()) if len(df) > 1 else 0.0
        latest_volume = float(df["volume"].iloc[-1])
        volume_spike = (
            avg_volume > 0
            and latest_volume >= self.volume_spike_multiplier * avg_volume
        )

        # Determine flagging and collect human-readable reasons
        reasons: list[str] = []
        for window, pct in growth_pct.items():
            if pct >= self.threshold_pct:
                reasons.append(f"+{pct:.1f}% over {window}d (threshold {self.threshold_pct:.1f}%)")
        if volume_spike:
            ratio = latest_volume / avg_volume if avg_volume > 0 else 0
            reasons.append(f"Volume spike {ratio:.1f}x avg ({latest_volume:,.0f} vs {avg_volume:,.0f})")

        flagged = bool(reasons)

        return GrowthResult(
            ticker=ticker,
            latest_close=round(latest_close, 2),
            growth_pct=growth_pct,
            volume_spike=volume_spike,
            avg_volume=round(avg_volume, 0),
            latest_volume=latest_volume,
            flagged=flagged,
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dataframe(candle_data: dict) -> pd.DataFrame | None:
        """Convert a Finnhub candle dict to a sorted DataFrame."""
        try:
            df = pd.DataFrame(
                {
                    "timestamp": candle_data["t"],
                    "open": candle_data["o"],
                    "high": candle_data["h"],
                    "low": candle_data["l"],
                    "close": candle_data["c"],
                    "volume": candle_data["v"],
                }
            )
        except KeyError:
            return None

        df["date"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.sort_values("date").reset_index(drop=True)
        return df
