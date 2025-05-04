# arbscan

A cross-venue sports betting mis-pricing scanner.

## Data Model

The core data model consists of three main dataclasses:

1. **EventKey** - Identifies a prediction market event across different exchanges:
   - `exchange`: The source exchange (Kalshi, Nadex, PredictIt)
   - `symbol`: Venue-native contract code or ID
   - `question`: Human-readable question text
   - `expiry`: UTC settlement/expiry time
   - `strike`: Optional numeric strike price (None for pure binary events)
   - `settlement`: Settlement type ("price" or "boolean")

2. **Quote** - Represents a market quote for a single side (YES/NO):
   - `side`: Quote side, either "YES" or "NO"
   - `price`: Decimal probability between 0 and 1
   - `size`: Size available at this price in contracts/shares
   - `ts`: UTC timestamp when the quote was captured

3. **MarketSnapshot** - Combines an EventKey with the best available YES/NO quotes:
   - `key`: EventKey identifying the market
   - `best_yes`: Best available Quote for the YES side
   - `best_no`: Best available Quote for the NO side

## Architecture

### Normalizer Layer

The Normalizer layer converts venue-specific API responses into the canonical `MarketSnapshot` format:

- **to_snapshot(raw, source)** - Main entry point that converts raw API responses to MarketSnapshot
- Supports three venues:
  - **Kalshi** - Converts prices from cents (0-100) to decimal probability (0-1)
  - **Nadex** - Converts prices from ticks (0-100) to decimal probability (0-1)
  - **PredictIt** - Uses prices directly as they are already in probability format (0-1)

Each venue adapter handles the specific data structure and price format of its venue, extracting relevant information to create standardized MarketSnapshot objects for consistent processing.

All prices are normalized to the standard decimal probability range (0-1) using venue-specific rules: Kalshi cents are divided by 100, Nadex ticks are divided by 100, and PredictIt prices are used as-is since they're already in the 0-1 range.

### API Clients

The application provides thin REST clients for interacting with prediction market APIs:

- **KalshiClient** - Client for Kalshi prediction markets API
  - Authentication via API key (passed in constructor or KALSHI_API_KEY environment variable)
  - Handles rate limits with automatic retry
  - Methods:
    - `list_markets()` - Returns list of available market tickers
    - `get_market(ticker)` - Gets detailed data for a specific market

- **NadexClient** - Client for Nadex prediction markets data
  - No authentication required (uses public endpoints)
  - Nadex client requires no API key
  - Handles rate limits and service unavailability with automatic retry
  - Methods:
    - `list_contracts()` - Returns list of available contracts with metadata
    - `get_contract(instrument_id)` - Gets detailed quote data for a specific contract

- **PredictItClient** - Client for PredictIt prediction markets data
  - No authentication required (uses public endpoints)
  - PredictIt client requires no API key
  - Handles rate limits with automatic retry (respects Retry-After header)
  - Methods:
    - `list_markets()` - Returns list of markets with binary (YES/NO) contracts
    - `get_market(market_id)` - Gets detailed data for a specific market

## Getting Started

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/dock108/prediction-arbs.git
    cd prediction-arbs
    ```

2.  **Install dependencies:**
    ```bash
    poetry install
    ```

3.  **Run tests:**
    ```bash
    poetry run pytest
    ```

4.  **Environment variables:**
    ```bash
    # Optional: Set API key for authenticated access to Kalshi
    export KALSHI_API_KEY="your-api-key"
    ```
