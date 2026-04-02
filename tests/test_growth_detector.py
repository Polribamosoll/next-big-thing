"""
Unit tests for GrowthDetector.

All tests use synthetic candle data — no real API calls are made.
"""

import time
import pytest
from src.analysis.growth_detector import GrowthDetector, GrowthResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_candles(closes: list[float], volumes: list[float] = None) -> dict:
    """Build a fake Finnhub candle dict from lists of close prices (and optionally volumes)."""
    n = len(closes)
    base_ts = int(time.time()) - n * 86_400
    if volumes is None:
        volumes = [1_000_000.0] * n
    assert len(volumes) == n, "volumes must have the same length as closes"
    timestamps = [base_ts + i * 86_400 for i in range(n)]
    return {
        "s": "ok",
        "t": timestamps,
        "o": closes,
        "h": closes,
        "l": closes,
        "c": closes,
        "v": volumes,
    }


# ── Basic happy-path tests ──────────────────────────────────────────────────────

class TestGrowthAboveThreshold:
    def test_flagged_when_growth_exceeds_threshold(self):
        detector = GrowthDetector(windows=[5], threshold_pct=20.0)
        # Flat at 100, then jump to 150 on the final day → +50% over 5 days
        closes = [100.0] * 30 + [150.0]
        result = detector.analyze("TEST", make_candles(closes))
        assert result is not None
        assert result.flagged
        assert result.growth_pct[5] == pytest.approx(50.0, abs=0.01)

    def test_not_flagged_when_growth_below_threshold(self):
        detector = GrowthDetector(windows=[5], threshold_pct=20.0)
        closes = [100.0] * 30 + [105.0]
        result = detector.analyze("TEST", make_candles(closes))
        assert result is not None
        assert not result.flagged
        assert result.growth_pct[5] == pytest.approx(5.0, abs=0.01)


class TestMultipleWindows:
    def test_all_windows_computed(self):
        detector = GrowthDetector(windows=[5, 10, 30], threshold_pct=50.0)
        # 36 candles — all windows computable
        closes = [100.0] * 35 + [125.0]
        result = detector.analyze("TEST", make_candles(closes))
        assert result is not None
        assert 5 in result.growth_pct
        assert 10 in result.growth_pct
        assert 30 in result.growth_pct

    def test_flagged_when_any_window_exceeds_threshold(self):
        # Only the 5-day window crosses 20%; 10-day and 30-day don't
        detector = GrowthDetector(windows=[5, 10, 30], threshold_pct=20.0)
        # 100 for most candles, but close[-6] = 90 so 5-day looks bigger
        closes = [100.0] * 25 + [90.0] + [100.0] * 4 + [115.0]
        result = detector.analyze("TEST", make_candles(closes))
        assert result is not None
        assert result.flagged

    def test_short_window_skipped_when_insufficient_data(self):
        detector = GrowthDetector(windows=[5, 30], threshold_pct=20.0)
        # Only 10 candles — window=30 cannot be computed
        closes = [100.0] * 9 + [130.0]
        result = detector.analyze("TEST", make_candles(closes))
        assert result is not None
        assert 5 in result.growth_pct
        assert 30 not in result.growth_pct


class TestVolumeSpike:
    def test_volume_spike_detected(self):
        detector = GrowthDetector(windows=[5], threshold_pct=20.0, volume_spike_multiplier=2.0)
        closes = [100.0] * 31
        volumes = [1_000_000.0] * 30 + [3_000_000.0]  # 3× the average
        result = detector.analyze("TEST", make_candles(closes, volumes))
        assert result is not None
        assert result.volume_spike
        assert result.flagged

    def test_no_volume_spike_when_within_multiplier(self):
        detector = GrowthDetector(windows=[5], threshold_pct=20.0, volume_spike_multiplier=2.0)
        closes = [100.0] * 31
        volumes = [1_000_000.0] * 30 + [1_500_000.0]  # only 1.5× — under threshold
        result = detector.analyze("TEST", make_candles(closes, volumes))
        assert result is not None
        assert not result.volume_spike

    def test_volume_spike_alone_flags_ticker(self):
        # Growth is tiny, but the volume spike should still cause flagging
        detector = GrowthDetector(windows=[5], threshold_pct=20.0, volume_spike_multiplier=2.0)
        closes = [100.0] * 31  # no price change at all
        volumes = [1_000_000.0] * 30 + [5_000_000.0]
        result = detector.analyze("TEST", make_candles(closes, volumes))
        assert result.flagged
        assert result.volume_spike


# ── Edge-case / failure-mode tests ─────────────────────────────────────────────

class TestEdgeCases:
    def test_no_data_returns_none(self):
        detector = GrowthDetector()
        assert detector.analyze("NONE", {"s": "no_data"}) is None

    def test_none_input_returns_none(self):
        detector = GrowthDetector()
        assert detector.analyze("NONE", None) is None

    def test_single_candle_returns_none(self):
        detector = GrowthDetector()
        result = detector.analyze("TEST", make_candles([100.0]))
        assert result is None

    def test_reasons_populated_for_flagged(self):
        detector = GrowthDetector(windows=[5], threshold_pct=20.0)
        closes = [100.0] * 30 + [150.0]
        result = detector.analyze("TEST", make_candles(closes))
        assert result.flagged
        assert len(result.reasons) >= 1
        assert any("50.0%" in r for r in result.reasons)

    def test_latest_close_value(self):
        detector = GrowthDetector(windows=[5], threshold_pct=99.0)
        closes = [100.0] * 10 + [42.5]
        result = detector.analyze("TEST", make_candles(closes))
        assert result is not None
        assert result.latest_close == pytest.approx(42.5, abs=0.01)
