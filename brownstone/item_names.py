"""Derived labels only: game-version isolation, immutable observations and one read contract.

Schema 5 (``storage.py``) owns the ``item_names`` table, the ``loaded_item_name`` macro and the
named views; this module keeps the lookup current as observations and catalogs arrive.
"""
from pathlib import Path

import duckdb
import polars as pl

from .config import MARKET_KEYS
from .crafting import load_recipe_catalog


def _remember(db, candidates: str, parameters: list) -> None:
    """Choose a deterministic winner; old imports and placeholders never erase a loaded name."""
    db.execute(f"""INSERT INTO item_names
        SELECT game_version, item_id, loaded_item_name(item_name), origin_rank, observed_at, evidence FROM (
            SELECT *, row_number() OVER (PARTITION BY game_version, item_id
                ORDER BY origin_rank DESC, observed_at DESC, loaded_item_name(item_name), evidence) AS choice
            FROM ({candidates}) candidates
            WHERE game_version IS NOT NULL AND item_id > 0 AND loaded_item_name(item_name) IS NOT NULL
        ) WHERE choice=1
        ON CONFLICT (game_version, item_id) DO UPDATE SET
            item_name=excluded.item_name, origin_rank=excluded.origin_rank,
            observed_at=excluded.observed_at, evidence=excluded.evidence
        WHERE excluded.origin_rank > item_names.origin_rank
            OR (excluded.origin_rank = item_names.origin_rank AND
                (excluded.observed_at > item_names.observed_at OR
                 (excluded.observed_at = item_names.observed_at AND
                  (excluded.item_name, excluded.evidence) < (item_names.item_name, item_names.evidence))))""",
               parameters)


def remember_observed_names(db, snapshot_id: str | None = None) -> None:
    """Backfill all observations, or incrementally remember one newly imported snapshot's labels."""
    # A variant's name ("Willow Robe of the Bear") never becomes the item ID's label; legacy rows lack
    # variant evidence and keep their existing behavior (ADDON-08).
    base = "({0}variant_state IS NULL OR {0}variant_state='base')"
    price_filter = f"WHERE {base.format('')}" + (" AND snapshot_id=?" if snapshot_id is not None else "")
    listing_filter = f"WHERE {base.format('l.')}" + (" AND l.snapshot_id=?" if snapshot_id is not None else "")
    parent_scope = " AND ".join(f"s.{key} IS NOT DISTINCT FROM l.{key}" for key in MARKET_KEYS)
    candidates = f"""
        SELECT game_version, item_id, item_name, 1 AS origin_rank,
            coalesce(updated_at, collected_at, TIMESTAMPTZ '1970-01-01') AS observed_at,
            concat_ws(':', source_id, snapshot_id, 'price') AS evidence
        FROM market_snapshots {price_filter}
        UNION ALL
        SELECT l.game_version, l.item_id, l.item_name, 1 AS origin_rank,
            coalesce(s.finished_at, s.collected_at, TIMESTAMPTZ '1970-01-01') AS observed_at,
            concat_ws(':', l.source_id, l.scan_id, 'listing', l.listing_index) AS evidence
        FROM scan_listings l LEFT JOIN addon_scans s
            ON s.source_id=l.source_id AND s.scan_id=l.scan_id AND {parent_scope} {listing_filter}
    """
    _remember(db, candidates, [snapshot_id, snapshot_id] if snapshot_id is not None else [])


def remember_catalog_names(db, catalogs: list[dict]) -> None:
    """Catalog labels are fallback evidence, independent of rules/roles/prices and versioned by game."""
    rows = [(catalog['game_version'], item['item_id'], item.get('name'),
             item.get('source_url', catalog.get('source_url', 'catalog')))
            for catalog in catalogs for item in catalog.get('items', [])]
    if not rows:
        return
    # One batch instead of one SQL query per catalog item; no temporary persistent observation rows.
    frame = pl.DataFrame(rows, schema=['game_version', 'item_id', 'item_name', 'evidence'], orient='row')
    db.register('catalog_name_candidates', frame.to_arrow())
    try:
        _remember(db, """SELECT game_version, item_id, item_name, 0 AS origin_rank,
            TIMESTAMPTZ '1970-01-01' AS observed_at, evidence FROM catalog_name_candidates""", [])
    finally:
        db.unregister('catalog_name_candidates')


def remember_local_catalog_names(db, config_dir: Path | None = None) -> None:
    """Seed validated local catalogs on upgrade/import; malformed catalogs keep existing UI isolation."""
    config_dir = config_dir or Path(__file__).resolve().parents[1] / 'config'
    catalogs = []
    for selection in sorted((config_dir / 'recipe-selections').glob('*.toml')):
        try:
            catalogs.append(load_recipe_catalog(config_dir / selection.name))
        except Exception:  # Like the app's catalog loader: any malformed catalog is skipped, never fatal.
            continue
    remember_catalog_names(db, catalogs)


def seed_catalog_names(data_dir: Path, catalogs: list[dict]) -> None:
    """Remember already-parsed catalog labels in an existing, current database; never creates one."""
    database = Path(data_dir) / 'brownstone.duckdb'
    if database.exists():
        with duckdb.connect(str(database)) as db:
            remember_catalog_names(db, catalogs)
