"""Alert sink implementations for notifying users of arbitrage opportunities."""

import os
from abc import ABC, abstractmethod

import requests


class AlertSink(ABC):
    """Abstract base class for alert notifications."""

    @abstractmethod
    def send(self, message: str) -> None:
        """Send an alert with the provided message.

        Args:
            message: The alert message to send

        """
        ...


class StdoutSink(AlertSink):
    """Simple alert sink that prints messages to standard output."""

    def send(self, message: str) -> None:
        """Print the message to standard output.

        Args:
            message: The message to print

        """
        print(message)  # noqa: T201 - Intentional print for stdout sink


class SlackSink(AlertSink):
    """Alert sink that sends messages to a Slack webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        """Initialize the Slack alert sink.

        Args:
            webhook_url: The Slack webhook URL to post alerts to.
                If not provided, will attempt to read from SLACK_WEBHOOK_URL env var.

        Raises:
            RuntimeError: If webhook_url is not provided and env var is not set

        """
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            msg = (
                "Slack webhook URL not provided. "
                "Set SLACK_WEBHOOK_URL environment variable."
            )
            raise RuntimeError(msg)

    def send(self, message: str) -> None:
        """Send a message to the Slack webhook.

        Args:
            message: The message to send to Slack

        Raises:
            requests.RequestException: If the request to Slack fails

        """
        response = requests.post(
            self.webhook_url,
            json={"text": message},
            timeout=5,
        )
        response.raise_for_status()
