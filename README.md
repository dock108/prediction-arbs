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

### Event Registry

The Event Registry provides a single source-of-truth mapping that links equivalent contracts across different prediction market venues.

#### Registry Structure

The registry is a YAML file containing an array of events, where each event has:
- `tag`: A canonical identifier used internally (e.g., "BTC-31MAY70K")
- `description`: Human-readable description of the event
- `kalshi`, `nadex`, `predictit`: Venue-specific identifiers (or `null` if not available)

#### Matcher Utility

The matcher utility provides two key functions for working with the registry:

- `tag_from(exchange, symbol)`: Converts a venue-specific symbol to the canonical tag
- `venues_for(tag)`: Returns all venue-specific symbols for a canonical tag

This enables the system to identify equivalent contracts across venues, which is essential for arbitrage detection and cross-venue price comparison.

### Edge Calculation & Fees

The Edge Calculator determines if there are profitable arbitrage opportunities between different venues, accounting for trading fees.

#### Fee Structure

The system maintains a YAML-based fee model for each venue:
- **Entry Fee**: Fixed dollar amount charged per contract
- **Exit Fee**: Percentage of profit taken when exiting a position

All calculations use a conservative approach, assuming worst-case fee scenarios.

#### Edge Formula

The edge calculator computes the potential profit margin after fees using:

1. **Fee-Adjusted Prices**: Convert raw probabilities to true costs including fees
   - For YES positions: `adjusted_price = price + entry_fee + ((1 - entry_cost) * exit_fee_pct)`
   - For NO positions: `adjusted_price = (1 - price) + entry_fee + (price * exit_fee_pct)`

2. **Cross-Venue Edge**: Compare buying YES on one venue vs NO on another
   - `edge = (1 - adjusted_yes_price_venue_a) - adjusted_no_price_venue_b`

Positive edge values indicate potential arbitrage opportunities, with the magnitude representing the expected profit margin as a decimal percentage.

### Kelly Sizing

The system includes a Kelly criterion calculator to determine optimal stake sizing based on edge:

```python
from decimal import Decimal
from arbscan.sizing import kelly

# For a 5% edge at 1.95 odds
fraction = kelly(Decimal("0.05"), Decimal("1.95"))
# Returns approximately 0.1 (10% of bankroll)
```

The Kelly criterion calculates the optimal fraction of your bankroll to wager on a favorable bet to maximize long-term growth while minimizing risk of ruin. The formula used is:

f = (p*odds - (1 - p)) / odds

Where:
- f is the fraction of your bankroll to wager
- p is the probability of winning
- odds is the decimal payout ratio (net payout per $1 stake, e.g., 1.95 means you receive $1.95 for a $1 stake, representing a 95¢ profit)

The implementation automatically clamps negative values to zero (don't bet) and values above 1 to exactly 1 (bet full bankroll).

### Alerting

The system includes a pluggable alert framework to notify users when profitable opportunities are detected:

```python
from arbscan.alerts import StdoutSink, SlackSink

# Use stdout for development/testing
alert = StdoutSink()
alert.send("Found 3.2% edge on BTC-31MAY70K: PredictIt YES vs Kalshi NO")

# Use Slack for production
# First set your webhook URL: export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ"
alert = SlackSink()  # Reads from environment variable
alert.send("🚨 OPPORTUNITY ALERT: 3.2% edge on BTC-31MAY70K")
```

The alert sinks share a common interface through the `AlertSink` abstract base class, making it easy to add additional notification channels in the future.

To use Slack notifications, you'll need to create a Slack App with Incoming Webhooks enabled and set the webhook URL as an environment variable:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR_WEBHOOK_PATH"
```

If the webhook URL is not provided, the system will default to standard output.

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

    # Optional: Set Slack webhook URL for alert notifications
    export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR_WEBHOOK_PATH"
    ```

## 🚀 Docker Quick Start

The easiest way to run arbscan is with Docker:

1. **Copy the example environment file and fill in your keys:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Run with Docker Compose:**
   ```bash
   docker compose up
   ```

This will build and start the scanner with default settings. The container will automatically restart unless explicitly stopped.

For custom settings, you can either:
- Edit the environment variables in your `.env` file
- Pass command-line arguments directly:
  ```bash
  docker compose run arbscan --threshold 0.03 --interval 30 --bankroll 5000
  ```

## Usage

The `arbscan` command-line tool continuously monitors venues for arbitrage opportunities and sends alerts when profitable edges are found.

### Basic Usage

Run the scanner with default settings (5% edge threshold, 60-second polling interval):

```bash
poetry run arbscan
```

### Command-line Options

- `--threshold` - Minimum positive edge before alert (default: 0.05)
- `--interval` - Polling interval in seconds (default: 60)
- `--bankroll` - Optional bankroll amount for Kelly sizing recommendations

### Examples

Scan with a lower 3% edge threshold:

```bash
poetry run arbscan --threshold 0.03
```

Scan more frequently (every 30 seconds):

```bash
poetry run arbscan --interval 30
```

Include Kelly stake sizing recommendations with a $10,000 bankroll:

```bash
poetry run arbscan --bankroll 10000
```

Combine multiple options:

```bash
poetry run arbscan --threshold 0.02 --interval 45 --bankroll 5000
```

### Alert Output

When an arbitrage opportunity is found, an alert will be sent with the following format:

```
EDGE 6.200 | BTC-31MAY70K YES@Kalshi 0.46 vs NO@Nadex 0.55 | Kelly stake: $37
```

Alerts are sent to Slack if the `SLACK_WEBHOOK_URL` environment variable is set, otherwise they are printed to the console.
