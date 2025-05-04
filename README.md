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
