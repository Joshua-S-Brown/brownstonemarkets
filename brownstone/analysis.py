from collections.abc import Mapping
from typing import Any

import duckdb
import polars as pl

from .money import COPPER_PER_GOLD
from .storage import scope_predicate

# Matches an item by name (case-insensitive) or ID; an empty search matches everything.
_SEARCH = "(contains(lower(item_name), lower(?)) OR contains(CAST(item_id AS VARCHAR), ?))"


def browse(connection, snapshot_id, config, search="", limit=100):
    predicate, scope = scope_predicate(config)
    return connection.execute(f"""SELECT item_id, item_name, min_buyout,
        market_value, recent_value, historical_value, updated_at FROM named_market_snapshots
        WHERE snapshot_id=? AND {predicate} AND {_SEARCH}
        ORDER BY item_name, item_id LIMIT ?""", [snapshot_id, *scope, search, search, limit]).pl()


def screenable_count(connection, snapshot_id, config):
    """Rows with every reference price positive; the discount screen can use only these."""
    predicate, scope = scope_predicate(config)
    return connection.execute(f"""SELECT count(*) FROM market_snapshots WHERE snapshot_id=? AND {predicate}
        AND min_buyout > 0 AND market_value > 0 AND recent_value > 0 AND historical_value > 0""",
        [snapshot_id, *scope]).fetchone()[0]


def rank(connection: duckdb.DuckDBPyConnection, snapshot_id: str, config: Mapping[str, Any],
         search: str = "") -> pl.DataFrame:
    """Discounted listings, ranked over the whole snapshot; ``search`` then filters without renumbering.

    The spread is integer copper: the reference price after the auction cut rounds down to the copper
    (as crafting net revenue does, CRAFT-07), then the minimum buyout is subtracted.
    """
    predicate, scope = scope_predicate(config)
    return connection.execute(f"""
        WITH price_references AS (
            SELECT *, least(market_value, recent_value, historical_value) AS reference_copper
            FROM named_market_snapshots WHERE snapshot_id = ? AND {predicate}
              AND min_buyout > 0 AND market_value > 0 AND recent_value > 0 AND historical_value > 0
        ), candidates AS (
            SELECT *, 1.0 - min_buyout::DOUBLE / reference_copper AS discount,
                CAST(floor(reference_copper * (1 - CAST(? AS DECIMAL(9, 6)))) AS BIGINT) - min_buyout
                    AS net_spread_copper
            FROM price_references
        ), ranked AS (
            SELECT row_number() OVER (ORDER BY discount DESC, net_spread_copper DESC, item_id) AS rank,
                snapshot_id, market_id, item_id, item_name, updated_at,
                min_buyout, reference_copper, discount, net_spread_copper,
                min_buyout / {COPPER_PER_GOLD}.0 AS buy_gold,
                net_spread_copper / {COPPER_PER_GOLD}.0 AS net_spread_gold
            FROM candidates WHERE discount >= ? AND net_spread_copper > 0
        )
        SELECT * FROM ranked WHERE {_SEARCH} ORDER BY rank LIMIT ?
    """, [snapshot_id, *scope, config["auction_cut"], config["min_discount"], search, search, config["top_n"]]).pl()
