import duckdb
import polars as pl


def browse(connection, snapshot_id, search="", limit=100):
    return connection.execute("""SELECT item_id, item_name, min_buyout,
        market_value, recent_value, historical_value, updated_at FROM market_snapshots
        WHERE snapshot_id=? AND (contains(lower(item_name), lower(?)) OR contains(CAST(item_id AS VARCHAR), ?))
        ORDER BY item_name, item_id LIMIT ?""", [snapshot_id, search, search, limit]).pl()


def screenable_count(connection, snapshot_id):
    """Rows with every reference price positive; the discount screen can use only these."""
    return connection.execute("""SELECT count(*) FROM market_snapshots WHERE snapshot_id=?
        AND min_buyout > 0 AND market_value > 0 AND recent_value > 0 AND historical_value > 0""",
        [snapshot_id]).fetchone()[0]


def rank(connection: duckdb.DuckDBPyConnection, snapshot_id: str, config: dict) -> pl.DataFrame:
    return connection.execute("""
        WITH price_references AS (
            SELECT *, least(market_value, recent_value, historical_value) AS reference_copper
            FROM market_snapshots WHERE snapshot_id = ?
              AND min_buyout > 0 AND market_value > 0 AND recent_value > 0 AND historical_value > 0
        ), candidates AS (
            SELECT *, 1.0 - min_buyout::DOUBLE / reference_copper AS discount,
                reference_copper * (1 - ?) - min_buyout AS net_spread_copper
            FROM price_references
        )
        SELECT row_number() OVER (ORDER BY discount DESC, net_spread_copper DESC, item_id) AS rank,
            snapshot_id, market_id, item_id, item_name, updated_at,
            min_buyout, reference_copper, discount, net_spread_copper,
            min_buyout / 10000.0 AS buy_gold,
            net_spread_copper / 10000.0 AS net_spread_gold
        FROM candidates WHERE discount >= ? AND net_spread_copper > 0
        ORDER BY rank LIMIT ?
    """, [snapshot_id, config["auction_cut"], config["min_discount"], config["top_n"]]).pl()
