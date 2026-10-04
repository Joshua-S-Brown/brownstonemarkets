"""Shared snapshot loading, freshness display and money columns for every view."""
from contextlib import contextmanager
from datetime import UTC, datetime

import duckdb
import streamlit as st

from brownstone.freshness import assess
from brownstone.money import GOLD_TABLE_FORMAT
from brownstone.storage import latest_snapshot


def load_latest(config, empty_message):
    """Return (manifest, analytical snapshot ID, manifest count), or show a message and None."""
    manifest, sid, count = latest_snapshot(config)
    if manifest is None:
        st.info(empty_message)
    return manifest, sid, count


@contextmanager
def read_db(config):
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        yield db


def show_freshness(config, manifest):
    """Caption the price age honestly and warn when the policy calls it stale."""
    freshness = assess(manifest, datetime.now(UTC), config["max_age_hours"])
    if freshness["upstream_known"]:
        st.caption(f"Prices scanned {freshness['age_hours']:.1f} hours ago "
                   f"({freshness['observed_at']:%Y-%m-%d %H:%M} UTC) · stale after {config['max_age_hours']} hours")
    else:
        st.caption(f"Price age unknown: this source gives no scan time. Downloaded "
                   f"{freshness['age_hours']:.1f} hours ago; prices may be older. Stale after "
                   f"{config['max_age_hours']} hours since download.")
    if manifest.get("scan_id"):
        st.caption(f"Addon scan {manifest['scan_id']} · complete scans only feed prices; "
                   "stacks are priced per unit, rounded up when the buyout does not divide evenly")
    if freshness["stale"]:
        st.warning("Saved prices are stale or future-dated. Refresh before acting on them.")
    return freshness


def gold_columns(*names):
    return {name: st.column_config.NumberColumn(name, format=GOLD_TABLE_FORMAT) for name in names}
