"""Read-only Today evidence assembly shared by every presentation layer."""
from datetime import datetime

import duckdb

from brownstone import professions
from brownstone.storage import latest_snapshot
from brownstone.today_data import read_today_evidence
from brownstone.today_funds import resolve_funds


def load_today(config, catalogs, settings, character_data, now: datetime, *, item_ids=()):
    """Return the latest manifest and build_today arguments, or None when no snapshot exists.

    Reads retain the existing full market/source predicates. The caller owns settings,
    character evidence error presentation, and session choices; this function never writes.
    """
    manifest, sid, _ = latest_snapshot(config)
    if manifest is None:
        return None, None
    ids = sorted({item for catalog in catalogs for item in catalog["items_by_id"]} | set(item_ids))
    with duckdb.connect(str(config["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        observations, listings, metrics, vendors = read_today_evidence(db, config, sid, ids)
    settings = resolve_funds(settings, character_data, now, config["max_age_hours"]).settings
    arguments = dict(catalogs=catalogs, observations=observations, market=config,
                     snapshot={**manifest, "snapshot_id": sid}, settings=settings, now=now,
                     listings=listings, metrics=metrics, vendor_prices=vendors,
                     max_age_hours=config["max_age_hours"], auction_cut=config["auction_cut"],
                     character_data=character_data)
    return manifest, arguments


def load_today_characters(config):
    """Read the shared profession projection; retain a failure for the UI to explain."""
    try:
        return professions.latest_data(config), None
    except Exception as error:
        return {}, f"Unable to read character evidence: {error}. Showing every catalog recipe."
