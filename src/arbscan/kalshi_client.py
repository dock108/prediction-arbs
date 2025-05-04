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

    BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"
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
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
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
        """Get list of available market tickers.

        Returns:
            List of market tickers (e.g., ["BTC-31MAY70K", "DEMS-2024-PRES"])

        """
        response = self._make_request("/markets")

        # Extract ticker from each market
        return [market["ticker"] for market in response.get("markets", [])]

    def get_market(self, ticker: str) -> dict[str, Any]:
        """Get raw market data for a specific ticker.

        Args:
            ticker: Market ticker symbol (e.g., "BTC-31MAY70K")

        Returns:
            Raw market JSON data as dictionary

        """
        endpoint = f"/markets/{ticker}"
        return self._make_request(endpoint)
