"""
Result formatting: console summary + CSV export.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime

from src.analysis.growth_detector import GrowthResult


def print_summary(results: list[GrowthResult]) -> None:
    """Print a concise console summary of all flagged tickers."""
    flagged = [r for r in results if r.flagged]
    total = len(results)

    print(f"\n{'=' * 65}")
    print(f"  SCAN COMPLETE  |  {total} tickers analysed  |  {len(flagged)} flagged")
    print(f"{'=' * 65}")

    if not flagged:
        print("  No tickers exceeded the configured thresholds.")
        return

    # Sort by best (highest) single-window growth, descending
    def _best_growth(r: GrowthResult) -> float:
        return max(r.growth_pct.values(), default=0.0)

    for r in sorted(flagged, key=_best_growth, reverse=True):
        growth_str = "  ".join(
            f"{w}d: {v:+.1f}%" for w, v in sorted(r.growth_pct.items())
        )
        vol_tag = "  [VOL SPIKE]" if r.volume_spike else ""
        print(f"  {r.ticker:<8}  ${r.latest_close:>9.2f}  {growth_str}{vol_tag}")
        for reason in r.reasons:
            print(f"             -> {reason}")

    print(f"{'=' * 65}\n")


def save_csv(results: list[GrowthResult], output_dir: str = "output") -> str | None:
    """
    Write all results (flagged and unflagged) to a timestamped CSV file.

    Returns the path of the written file, or None if results is empty.
    """
    if not results:
        print("No results to save.")
        return None

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"scan_{timestamp}.csv")

    # Collect all windows present across results so column order is stable
    all_windows = sorted({w for r in results for w in r.growth_pct})
    growth_cols = [f"growth_{w}d_pct" for w in all_windows]

    fieldnames = [
        "ticker",
        "latest_close",
        "flagged",
        "volume_spike",
        "avg_volume",
        "latest_volume",
        *growth_cols,
        "reasons",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row: dict = {
                "ticker": r.ticker,
                "latest_close": r.latest_close,
                "flagged": r.flagged,
                "volume_spike": r.volume_spike,
                "avg_volume": r.avg_volume,
                "latest_volume": r.latest_volume,
                "reasons": "; ".join(r.reasons),
            }
            for w in all_windows:
                row[f"growth_{w}d_pct"] = r.growth_pct.get(w, "")
            writer.writerow(row)

    print(f"Results saved → {filepath}")
    return filepath
