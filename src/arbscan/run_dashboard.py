"""Runner script for the Streamlit dashboard."""

import sys
from pathlib import Path

import streamlit.web.cli as stcli


def main() -> None:
    """Run the dashboard script with Streamlit."""
    current_dir = Path(__file__).parent
    dashboard_path = current_dir / "dashboard.py"

    sys.argv = [
        "streamlit",
        "run",
        str(dashboard_path),
        "--browser.gatherUsageStats",
        "false",
        "--server.headless",
        "true",
    ]

    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
