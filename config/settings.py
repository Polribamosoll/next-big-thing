import os
from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_root, ".env"))

FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "30"))
GROWTH_THRESHOLD_PCT: float = float(os.getenv("GROWTH_THRESHOLD_PCT", "20.0"))
VOLUME_SPIKE_MULTIPLIER: float = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))
MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "55"))
