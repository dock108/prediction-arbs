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
