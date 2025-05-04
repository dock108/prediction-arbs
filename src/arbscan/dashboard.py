"""Streamlit dashboard for visualizing arbitrage opportunities.

This module provides a web-based dashboard for viewing live edges
and historical data from the arbscan database.
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import streamlit as st
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from arbscan.db import Edge

# Configure page
st.set_page_config(
    page_title="ArbScan Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db_path() -> str:
    """Get database path with override support for testing."""
    return os.environ.get("ARBSCAN_DB_PATH", "data/arb.db")


def create_db_engine() -> Engine:
    """Create SQLite engine with connection to the database."""
    db_path = get_db_path()
    if db_path == ":memory:":
        # In-memory database for testing
        engine = create_engine("sqlite:///:memory:", echo=False)
        SQLModel.metadata.create_all(engine)
    else:
        # Regular file-based database
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine


def get_recent_edges(engine: Engine, limit: int = 15) -> list[Edge]:
    """Get the most recent edges from the database."""
    with Session(engine) as session:
        statement = select(Edge).order_by(Edge.ts.desc()).limit(limit)
        return session.exec(statement).all()


def get_tags(engine: Engine) -> list[str]:
    """Get unique tags from the edges table."""
    with Session(engine) as session:
        statement = select(Edge.tag).distinct()
        return [result for (result,) in session.exec(statement)]


def get_edge_history(engine: Engine, tag: str, hours: int = 24) -> list[Edge]:
    """Get edge history for a specific tag."""
    time_cutoff = datetime.now(tz=UTC) - timedelta(hours=hours)
    with Session(engine) as session:
        statement = (
            select(Edge)
            .where(Edge.tag == tag)
            .where(Edge.ts >= time_cutoff)
            .order_by(Edge.ts)
        )
        return session.exec(statement).all()


def format_edge_percent(edge: Decimal) -> str:
    """Format edge as percentage with 2 decimal places."""
    return f"{float(edge) * 100:.2f}%"


def main() -> None:
    """Run the Streamlit dashboard application."""
    st.title("ArbScan Dashboard")
    st.subheader("Cross-venue arbitrage opportunity monitor")

    # Create sidebar
    st.sidebar.title("Settings")
    refresh_interval = st.sidebar.slider(
        "Refresh interval (seconds)",
        min_value=5,
        max_value=120,
        value=30,
        step=5,
    )

    # Connect to database
    try:
        engine = create_db_engine()

        # Main content
        st.header("Recent Edges")

        # Recent edges table
        edges = get_recent_edges(engine)
        if edges:
            # Format data for display
            edge_data = [
                {
                    "Tag": edge.tag,
                    "YES Exchange": edge.yes_exchange,
                    "NO Exchange": edge.no_exchange,
                    "Edge": format_edge_percent(edge.edge),
                    "Timestamp": edge.ts.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for edge in edges
            ]

            # Display as table
            st.dataframe(
                edge_data,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No edge data found. Run the arbscan tool to populate the database.",
            )

        # Historical chart
        st.header("Edge History")

        # Get unique tags for selection
        tags = get_tags(engine)
        if tags:
            selected_tag = st.selectbox("Select market", tags)

            # Get historical data for selected tag
            edge_history = get_edge_history(engine, selected_tag)

            if edge_history:
                # Prepare data for chart
                chart_data = {
                    "timestamp": [e.ts for e in edge_history],
                    "edge_pct": [float(e.edge) * 100 for e in edge_history],
                }

                # Plot chart
                st.line_chart(
                    chart_data,
                    x="timestamp",
                    y="edge_pct",
                    height=400,
                )

                # Show statistics
                if edge_history:
                    max_edge = max(edge_history, key=lambda e: e.edge)
                    avg_edge = sum(float(e.edge) for e in edge_history)
                    avg_edge = avg_edge / len(edge_history)

                    # Create delta string for metric
                    delta_text = (
                        f"{max_edge.yes_exchange} YES / {max_edge.no_exchange} NO"
                    )
                    st.metric(
                        "Maximum Edge",
                        format_edge_percent(max_edge.edge),
                        delta=delta_text,
                    )
                    st.metric(
                        "Average Edge",
                        f"{avg_edge * 100:.2f}%",
                    )
            else:
                st.info(f"No historical edge data found for {selected_tag}")
        else:
            st.info("No markets found in the database.")

    except (ConnectionError, OSError) as e:
        st.error(f"Error connecting to database: {e}")
        st.info("Make sure the arb.db file exists in the data directory.")

    # Auto-refresh
    st.empty()
    st.caption(f"Data refreshes every {refresh_interval} seconds")
    st.caption(f"Last update: {datetime.now(tz=UTC).strftime('%Y-%m-%d %H:%M:%S')}")

    # Schedule refresh
    if not st.session_state.get("stop_refresh"):
        st.session_state["stop_refresh"] = False
        st.session_state["last_refresh"] = datetime.now(tz=UTC)

        # Check if it's time to refresh
        refresh_time = st.session_state["last_refresh"]
        now = datetime.now(tz=UTC)
        if (now - refresh_time).seconds >= refresh_interval:
            st.session_state["last_refresh"] = now
            st.experimental_rerun()


if __name__ == "__main__":
    main()
