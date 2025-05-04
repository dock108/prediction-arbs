"""Client for Nadex prediction markets data."""

import csv
import io
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

import requests


@dataclass
class NadexContract:
    """Represents a Nadex contract listing from the contracts CSV."""

    instrument_id: str
    underlying: str
    strike: float | None
    expiry: datetime


class NadexClient:
    """Client for Nadex prediction markets data.

    Provides methods to fetch contract listings and quotes without authentication.
    """

    BASE_URL = "https://www.nadex.com/markets"
    CONTRACTS_CSV_URL = f"{BASE_URL}/contracts.csv"
    CONTRACT_DETAIL_URL = f"{BASE_URL}/contract"
    RETRY_DELAY = 2  # Seconds to wait before retry
    # HTTP status codes to retry on
    RETRY_STATUS_CODES: ClassVar[list[int]] = [429, 503]
    MIN_CSV_COLUMNS = 4  # Minimum columns required for a valid CSV row

    def __init__(self) -> None:
        """Initialize Nadex client."""
        self.session = requests.Session()

    def _make_request(self, url: str, params: dict | None = None) -> requests.Response:
        """Make a GET request to the Nadex API with retry logic.

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
            # Handle rate limiting or service unavailable
            if error.response.status_code in self.RETRY_STATUS_CODES:
                # Wait and retry once
                time.sleep(self.RETRY_DELAY)
                response = self.session.get(url, params=params)
                response.raise_for_status()
                return response
            raise
        else:
            return response

    def _parse_strike(self, strike_str: str) -> float | None:
        """Parse a strike value from string to float, handling invalid values.

        Args:
            strike_str: Strike value as string

        Returns:
            Float value if parseable, None otherwise

        """
        if not strike_str or not strike_str.strip():
            return None

        try:
            return float(strike_str)
        except ValueError:
            # Invalid float string
            return None

    def list_contracts(self) -> list[NadexContract]:
        """Get list of available Nadex contracts.

        Returns:
            List of NadexContract objects with basic contract information

        """
        response = self._make_request(self.CONTRACTS_CSV_URL)

        # Parse CSV from response
        contracts = []
        csv_content = csv.reader(io.StringIO(response.text))

        # Skip header row
        next(csv_content, None)

        for row in csv_content:
            # CSV format: instrument_id, underlying, strike, expiry, ...
            if len(row) >= self.MIN_CSV_COLUMNS:
                # Convert strike to float if valid, otherwise None
                strike = self._parse_strike(row[2])

                # Parse expiry datetime
                try:
                    expiry = datetime.fromisoformat(row[3])
                except ValueError:
                    # Skip invalid rows
                    continue

                contracts.append(
                    NadexContract(
                        instrument_id=row[0],
                        underlying=row[1],
                        strike=strike,
                        expiry=expiry,
                    ),
                )

        return contracts

    def get_contract(self, instrument_id: str) -> dict[str, Any]:
        """Get detailed quote information for a specific contract.

        Args:
            instrument_id: Unique identifier for the contract

        Returns:
            Dict containing contract quote data (bid/offer, size, timestamp)

        """
        url = f"{self.CONTRACT_DETAIL_URL}/{instrument_id}"
        response = self._make_request(url)

        # Return the JSON response
        return response.json()
