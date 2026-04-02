"""
Ticker list loader.

Default source: S&P 500 constituent list scraped from Wikipedia and cached
locally at config/sp500_tickers.csv.  Call load_sp500_tickers(refresh=True)
to force a fresh fetch.

For a custom list, prepare a CSV with at least a 'ticker' column and call
load_custom_tickers(filepath).
"""

import io
import os
import logging
import urllib.request
import pandas as pd

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
)
SP500_CSV = os.path.join(_CONFIG_DIR, "sp500_tickers.csv")
_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def load_sp500_tickers(refresh: bool = False) -> list[str]:
    """
    Return the list of S&P 500 tickers.

    On first run (or when *refresh=True*) the list is fetched from Wikipedia
    and saved to config/sp500_tickers.csv for fast subsequent loads.

    Finnhub uses hyphens instead of dots (e.g. BRK-B not BRK.B), so we
    normalise the symbols automatically.
    """
    if not refresh and os.path.exists(SP500_CSV):
        logger.info("Loading S&P 500 tickers from cache: %s", SP500_CSV)
        df = pd.read_csv(SP500_CSV)
        return df["ticker"].tolist()

    logger.info("Fetching S&P 500 tickers from Wikipedia …")
    try:
        req = urllib.request.Request(
            _WIKIPEDIA_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; sp500-scanner/1.0)"},
        )
        with urllib.request.urlopen(req) as resp:
            html = resp.read()
        tables = pd.read_html(io.BytesIO(html), flavor="lxml")
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch S&P 500 list from Wikipedia: {exc}\n"
            "Check your internet connection or supply a custom ticker file."
        ) from exc

    df = tables[0][["Symbol", "Security"]].copy()
    df.columns = ["ticker", "name"]
    # Finnhub expects BRK-B, not BRK.B
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

    os.makedirs(_CONFIG_DIR, exist_ok=True)
    df.to_csv(SP500_CSV, index=False)
    logger.info("Saved %d tickers to %s", len(df), SP500_CSV)

    return df["ticker"].tolist()


def load_custom_tickers(filepath: str) -> list[str]:
    """
    Load tickers from a CSV file that has at minimum a 'ticker' column.

    Example CSV:
        ticker,name
        AAPL,Apple Inc.
        MSFT,Microsoft Corp.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Ticker file not found: {filepath}")

    df = pd.read_csv(filepath)
    if "ticker" not in df.columns:
        raise ValueError(
            f"Expected a 'ticker' column in {filepath}. "
            f"Found columns: {list(df.columns)}"
        )
    return df["ticker"].dropna().str.strip().tolist()
