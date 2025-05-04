"""Client for PredictIt prediction markets data."""

import time
from typing import Any, ClassVar

import requests


class PredictItClient:
    """Client for PredictIt prediction markets data.

    Provides methods to fetch market listings and quotes without authentication.
    """

    BASE_URL = "https://www.predictit.org/api/marketdata/all"
    MAX_RETRY_DELAY = 3  # Maximum seconds to wait before retry
    RETRY_STATUS_CODES: ClassVar[list[int]] = [429]  # HTTP 429 Too Many Requests

    def __init__(self) -> None:
        """Initialize PredictIt client."""
        self.session = requests.Session()

    def _make_request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        """Make a GET request to the PredictIt API with retry logic.

        Args:
            url: Full URL to request
            params: Optional query parameters

        Returns:
            Response object from requests

        Raises:
            requests.exceptions.RequestException: For non-retryable errors

        """
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            # Handle rate limiting
            if error.response.status_code in self.RETRY_STATUS_CODES:
                # Get retry delay from header or use default
                retry_after = int(
                    error.response.headers.get("Retry-After", self.MAX_RETRY_DELAY),
                )
                # Cap the delay
                delay = min(retry_after, self.MAX_RETRY_DELAY)
                time.sleep(delay)

                # Retry the request
                response = self.session.get(url, params=params)
                response.raise_for_status()
                return response
            raise
        return response

    def _is_binary_market(self, market: dict[str, Any]) -> bool:
        """Check if a market contains binary (YES/NO) contracts.

        Args:
            market: Market data dictionary

        Returns:
            True if the market has binary contracts, False otherwise

        """
        # Check if the market has at least one contract
        if not market.get("contracts"):
            return False

        # Check if both YES and NO contracts exist
        has_yes = any(contract.get("name") == "Yes" for contract in market["contracts"])
        has_no = any(contract.get("name") == "No" for contract in market["contracts"])

        return has_yes and has_no

    def list_markets(self) -> list[tuple[int, str]]:
        """Get list of available PredictIt markets with binary (YES/NO) contracts.

        Returns:
            List of tuples containing (market_id, market_name)

        """
        response = self._make_request(self.BASE_URL)
        data = response.json()

        # Filter for markets with binary contracts
        return [
            (market["id"], market["name"])
            for market in data.get("markets", [])
            if self._is_binary_market(market)
        ]

    def get_market(self, market_id: int) -> dict[str, Any]:
        """Get detailed quote information for a specific market.

        Args:
            market_id: Unique identifier for the market

        Returns:
            Dict containing market data with contracts

        Raises:
            ValueError: If market_id is not found or not a binary market

        """
        response = self._make_request(self.BASE_URL)
        data = response.json()

        # Find the requested market
        for market in data.get("markets", []):
            if market["id"] == market_id:
                if self._is_binary_market(market):
                    return market
                error_msg = f"Market {market_id} does not contain binary contracts"
                raise ValueError(error_msg)

        error_msg = f"Market {market_id} not found"
        raise ValueError(error_msg)
