"""Edit this file to change simulator starting prices, volatility, or correlations."""

# Starting prices (approximate real prices at project start)
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 415.00, "AMZN": 185.00,
    "TSLA": 175.00, "NVDA":  950.00, "META": 490.00, "JPM":  200.00,
    "V":    275.00, "NFLX":  620.00,
}

# Annualized drift μ (e.g. 0.05 = +5%/year expected return)
DRIFTS: dict[str, float] = {
    "AAPL": 0.05, "GOOGL": 0.06, "MSFT": 0.07, "AMZN": 0.05,
    "TSLA": 0.00, "NVDA":  0.10, "META": 0.06, "JPM":  0.04,
    "V":    0.05, "NFLX":  0.05,
}

# Annualized volatility σ (e.g. 0.25 = 25%/year std-dev of log returns)
VOLS: dict[str, float] = {
    "AAPL": 0.25, "GOOGL": 0.27, "MSFT": 0.24, "AMZN": 0.30,
    "TSLA": 0.55, "NVDA":  0.45, "META": 0.32, "JPM":  0.20,
    "V":    0.18, "NFLX":  0.35,
}

# Pairwise correlations (upper-triangle; reverse lookup handled by _corr_matrix).
# Missing pairs fall back to DEFAULT_CORR (0.30).
CORRELATIONS: dict[tuple[str, str], float] = {
    ("AAPL", "GOOGL"): 0.60, ("AAPL", "MSFT"):  0.60, ("AAPL", "AMZN"): 0.55,
    ("AAPL", "TSLA"):  0.45, ("AAPL", "NVDA"):  0.55, ("AAPL", "META"): 0.55,
    ("AAPL", "NFLX"):  0.50, ("AAPL", "JPM"):   0.20, ("AAPL", "V"):    0.25,
    ("GOOGL", "MSFT"): 0.65, ("GOOGL", "META"): 0.65, ("GOOGL", "NVDA"): 0.55,
    ("GOOGL", "AMZN"): 0.55, ("GOOGL", "NFLX"): 0.55, ("GOOGL", "TSLA"): 0.40,
    ("MSFT", "NVDA"):  0.55, ("MSFT", "AMZN"):  0.50, ("MSFT", "META"): 0.55,
    ("NVDA", "META"):  0.55, ("NVDA", "TSLA"):   0.50,
    ("JPM",  "V"):     0.55,
}

DEFAULT_PRICE = 100.00
DEFAULT_DRIFT = 0.05
DEFAULT_VOL   = 0.30
DEFAULT_CORR  = 0.30   # for ticker pairs not in CORRELATIONS
