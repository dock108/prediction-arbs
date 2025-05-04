"""Tests for the alert sink implementations."""

import sys
from pathlib import Path

import pytest
import requests
import responses

# Add the src directory to the path before importing arbscan
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from arbscan.alerts import SlackSink, StdoutSink


class TestStdoutSink:
    """Tests for the StdoutSink class."""

    def test_send_prints_to_stdout(self, capsys):
        """Test that StdoutSink.send() prints the message to stdout."""
        # Arrange
        sink = StdoutSink()
        message = "Test alert message"

        # Act
        sink.send(message)

        # Assert
        captured = capsys.readouterr()
        assert message in captured.out
        assert captured.err == ""


class TestSlackSink:
    """Tests for the SlackSink class."""

    def test_init_with_explicit_url(self):
        """Test SlackSink initialization with explicit webhook URL."""
        # Arrange
        webhook_url = "https://hooks.slack.com/services/TEST123/TEST456"

        # Act
        sink = SlackSink(webhook_url=webhook_url)

        # Assert
        assert sink.webhook_url == webhook_url

    def test_init_with_env_var(self, monkeypatch):
        """Test SlackSink initialization using environment variable."""
        # Arrange
        webhook_url = "https://hooks.slack.com/services/TEST123/TEST456"
        monkeypatch.setenv("SLACK_WEBHOOK_URL", webhook_url)

        # Act
        sink = SlackSink()

        # Assert
        assert sink.webhook_url == webhook_url

    def test_init_without_url_raises_error(self, monkeypatch):
        """Test SlackSink initialization without URL raises RuntimeError."""
        # Arrange
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        # Act/Assert
        with pytest.raises(RuntimeError):
            SlackSink()

    @responses.activate
    def test_send_posts_to_webhook(self):
        """Test that SlackSink.send() posts the message to the webhook URL."""
        # Arrange
        webhook_url = "https://hooks.slack.com/services/TEST123/TEST456"
        sink = SlackSink(webhook_url=webhook_url)
        message = "Test alert message"

        # Mock the response
        responses.add(
            responses.POST,
            webhook_url,
            json={"ok": True},
            status=200,
        )

        # Act
        sink.send(message)

        # Assert
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == webhook_url
        assert responses.calls[0].request.body == b'{"text": "Test alert message"}'

    @responses.activate
    def test_send_raises_on_error(self):
        """Test that SlackSink.send() raises an exception on HTTP error."""
        # Arrange
        webhook_url = "https://hooks.slack.com/services/TEST123/TEST456"
        sink = SlackSink(webhook_url=webhook_url)
        message = "Test alert message"

        # Mock the error response
        responses.add(
            responses.POST,
            webhook_url,
            json={"ok": False, "error": "invalid_payload"},
            status=400,
        )

        # Act/Assert
        with pytest.raises(requests.RequestException):
            sink.send(message)

        # Verify the request was made
        assert len(responses.calls) == 1
