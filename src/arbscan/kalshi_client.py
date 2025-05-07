"""REST client for Kalshi prediction markets API."""

import os
import time
from typing import Any

import requests


class KalshiClient:
    """Client for Kalshi prediction markets API.

    Provides methods to fetch market data from Kalshi.
    Can use authenticated or public endpoints.
    """

    DEFAULT_BASE_URL = "https://api.kalshi.com/trade-api/v2"
    ELECTION_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    # Check for KALSHI_BASE_URL override first, then use appropriate default
    BASE_URL = os.getenv("KALSHI_BASE_URL", DEFAULT_BASE_URL)

    MAX_RETRY_DELAY = 5  # Maximum seconds to wait for a retry
    RATE_LIMIT_STATUS = 429  # HTTP 429 Too Many Requests

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize Kalshi API client.

        Args:
            api_key: Optional API key for authenticated access.
                    If None, will try to read from KALSHI_API_KEY env var.

        """
        # Try to get API key from env var if not provided
        self.api_key = api_key or os.environ.get("KALSHI_API_KEY")
        self.session = requests.Session()

    def _get_base_url(self, ticker: str | None = None) -> str:
        """Determine the correct base URL.

        Defaults to the general API host.
        Routes to the election-specific host for election tickers.
        Can be overridden by the KALSHI_BASE_URL environment variable.

        Args:
            ticker: Optional market ticker. If provided and is an election ticker,
                    the election-specific base URL is used.

        Returns:
            The appropriate base URL string.

        """
        if os.getenv("KALSHI_BASE_URL"):
            return os.environ["KALSHI_BASE_URL"]
        if ticker and ticker.startswith(
            "PRES2024",
        ):  # Add other election prefixes if needed
            return self.ELECTION_BASE_URL
        return self.DEFAULT_BASE_URL

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests.

        Returns:
            Dict of headers, including auth if API key is available.

        """
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _make_request(self, endpoint: str) -> dict[str, Any]:
        """Make a GET request to the Kalshi API with retry logic.

        Args:
            endpoint: API endpoint path (without base URL)

        Returns:
            JSON response as dictionary

        Raises:
            requests.exceptions.RequestException: For non-retryable errors

        """
        base_url_to_use = self._get_base_url(
            endpoint.split("/")[-1] if "/markets/" in endpoint else None,
        )
        url = f"{base_url_to_use}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as error:
            # Handle rate limiting (HTTP 429)
            if error.response.status_code == self.RATE_LIMIT_STATUS:
                # Get retry delay from headers, capped at MAX_RETRY_DELAY
                retry_after = min(
                    int(error.response.headers.get("Retry-After", "1")),
                    self.MAX_RETRY_DELAY,
                )
                time.sleep(retry_after)

                # Retry once
                response = self.session.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            raise

    def list_markets(self) -> list[str]:
        """Get list of available market event_tickers from the /events endpoint.

        Returns:
            List of market event_tickers (e.g., ["KXROBOTMARS-35", "BTCETHATH-29DEC31"])

        """
        response = self._make_request("/events")  # Query the /events endpoint

        # Extract event_ticker from each event
        return [event["event_ticker"] for event in response.get("events", [])]

    def get_market(self, ticker: str) -> dict[str, Any]:
        """Get raw market data for a specific ticker.

        Args:
            ticker: Market ticker symbol (e.g., "BTC-31MAY70K")

        Returns:
            Raw market JSON data as dictionary

        """
        # The ticker itself is used by _get_base_url to determine the host
        endpoint = f"/markets/{ticker}"
        return self._make_request(endpoint)
