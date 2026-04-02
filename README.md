# next-big-thing — Stock Market Growth Scanner

Scans a broad list of stock tickers (default: S&P 500) and surfaces companies
with significant price growth or unusual volume over configurable look-back
windows, using the [Finnhub](https://finnhub.io/) market data API.

---

## Project structure

```
next-big-thing/
├── config/
│   ├── settings.py          # Centralised config (reads from .env)
│   └── sp500_tickers.csv    # Auto-generated on first run; gitignored
├── src/
│   ├── data/
│   │   ├── finnhub_client.py  # Finnhub API wrapper (rate limiting, retries)
│   │   └── ticker_loader.py   # S&P 500 / custom ticker list loader
│   ├── analysis/
│   │   └── growth_detector.py # % change + volume spike detection
│   ├── output/
│   │   └── formatter.py       # Console summary + CSV export
│   └── main.py                # Runner / entry point
├── tests/
│   └── test_growth_detector.py
├── output/                    # Scan results land here (gitignored except .gitkeep)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Quick start

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd next-big-thing

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Set up your API key

```bash
cp .env.example .env
```

Open `.env` and replace `your_api_key_here` with your Finnhub API key.
Free keys are available at <https://finnhub.io/>.

```dotenv
FINNHUB_API_KEY=your_real_key_here
```

### 3. Run the scanner

```bash
# Full S&P 500 scan (~500 tickers, takes ~10 minutes on free tier)
python src/main.py

# Quick test with only 20 tickers
python src/main.py --limit 20

# Force-refresh the S&P 500 ticker list from Wikipedia
python src/main.py --refresh-tickers

# Scan a custom ticker list
python src/main.py --tickers config/my_tickers.csv
```

Results are printed to the console **and** saved as a CSV in `output/`.

---

## Configuration

All settings can be overridden in `.env` (or as environment variables):

| Variable | Default | Description |
|---|---|---|
| `FINNHUB_API_KEY` | *(required)* | Your Finnhub API key |
| `LOOKBACK_DAYS` | `30` | Calendar days of history to fetch |
| `GROWTH_THRESHOLD_PCT` | `20.0` | Flag when growth exceeds this % in any window |
| `VOLUME_SPIKE_MULTIPLIER` | `2.0` | Flag when today's volume ≥ N × historical avg |
| `MAX_REQUESTS_PER_MINUTE` | `55` | Stay under Finnhub's 60 req/min free-tier limit |

---

## Custom ticker list

Create a CSV with at least a `ticker` column:

```csv
ticker,name
AAPL,Apple Inc.
NVDA,NVIDIA Corp.
TSLA,Tesla Inc.
```

Then pass it with `--tickers`:

```bash
python src/main.py --tickers config/my_tickers.csv
```

---

## Running tests

```bash
pytest
# or with verbose output
pytest -v
```

Tests are fully self-contained — no API calls, no `.env` required.

---

## Output

Each scan writes a CSV to `output/scan_YYYYMMDD_HHMMSS.csv` with columns:

| Column | Description |
|---|---|
| `ticker` | Stock symbol |
| `latest_close` | Most recent closing price |
| `flagged` | True if any threshold was exceeded |
| `volume_spike` | True if volume spike detected |
| `avg_volume` | Historical average daily volume |
| `latest_volume` | Volume on the most recent day |
| `growth_5d_pct` | % price change over 5 trading days |
| `growth_10d_pct` | % price change over 10 trading days |
| `growth_30d_pct` | % price change over 30 trading days |
| `reasons` | Human-readable explanation of why the ticker was flagged |

---

## Rate limiting

Finnhub's free tier allows **60 API requests per minute**.  
The scanner uses a sliding-window counter and sleeps automatically when
approaching the limit.  `MAX_REQUESTS_PER_MINUTE=55` gives a 5-request
safety buffer.  Scanning all ~500 S&P 500 tickers takes roughly 9–10 minutes.

---

## Adding new data sources or analyses

- **New data source**: add a module under `src/data/` and a corresponding
  loader. The `FinnhubClient` is intentionally decoupled from the rest.
- **New analysis**: add a class under `src/analysis/` following the same
  `analyze(ticker, data) -> Result | None` convention.
- **New output format**: add a function to `src/output/formatter.py` or a
  new module alongside it.
