import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pytest
from conftest import make_source

from brownstone.config import read_sources
from brownstone.normalization import normalize
from brownstone.pipeline import run

NOW = datetime.now(UTC)
HEADER = "itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n"


def csv(rows):
    return (HEADER + "\n".join(
        f"{item},Item {item},{market},{buy},{recent},{historical},{updated}"
        for item, market, buy, recent, historical, updated in rows
    )).encode()


def norm(raw):
    return normalize(raw, "test", "snapshot", NOW, 24)


def test_schema_and_zero_prices():
    frame = norm(csv([(1, 100, 0, 100, 100, NOW.isoformat())]))
    assert frame.schema["min_buyout"] == pl.Int64
    assert frame["min_buyout"][0] == 0
    assert frame["updated_at"][0] == NOW


def test_missing_name_fallback():
    raw = csv([(1, 100, 50, 100, 100, NOW.isoformat())]).replace(b"Item 1", b"")
    assert norm(raw)["item_name"][0] == "Item 1"


def test_explicit_source_policy_allows_entirely_missing_upstream_time():
    raw = csv([(1, 100, 50, 100, 100, "")])
    frame = normalize(raw, "classic-test", "snapshot", NOW, 24, allow_missing_updated_at=True)
    assert frame["updated_at"][0] is None


def test_source_policy_rejects_partially_missing_upstream_time():
    raw = csv([
        (1, 100, 50, 100, 100, ""),
        (2, 100, 50, 100, 100, NOW.isoformat()),
    ])
    with pytest.raises(ValueError, match="complete or entirely unavailable"):
        normalize(raw, "classic-test", "snapshot", NOW, 24, allow_missing_updated_at=True)


@pytest.mark.parametrize("raw,match", [
    (b"wrong,column\n1,2", "Missing"),
    (HEADER.encode(), "no rows"),
    (csv([(1, 100, 50, 100, 100, NOW.isoformat())] * 2), "Duplicate"),
    (csv([(1, -1, 50, 100, 100, NOW.isoformat())]), "nonnegative"),
    (csv([(0, 100, 50, 100, 100, NOW.isoformat())]), "positive"),
    (csv([(1, 100, 50, 100, 100, (NOW-timedelta(days=2)).isoformat())]), "stale"),
    (csv([(1, 100, 50, 100, 100, (NOW+timedelta(hours=1)).isoformat())]), "future"),
    (csv([(1, "", 50, 100, 100, NOW.isoformat())]), "null"),
])
def test_bad_data(raw, match):
    with pytest.raises(ValueError, match=match):
        norm(raw)


def test_round_trip_and_ranking(tmp_path):
    raw = csv([
        (1, 10000, 4000, 8000, 9000, NOW.isoformat()),
        (2, 10000, 7000, 10000, 10000, NOW.isoformat()),
        (3, 10000, 0, 10000, 10000, NOW.isoformat()),
        (4, 10000, 2000, 0, 10000, NOW.isoformat()),
    ])
    source = tmp_path / "input.csv"
    source.write_bytes(raw)
    config = make_source(tmp_path / "data")
    result, gold = run(config, source)
    assert result["item_id"].to_list() == [1, 2]
    assert result["reference_copper"][0] == 8000
    assert result["net_spread_copper"][0] == 3600
    assert next((tmp_path / "data/bronze/test").glob("*.csv")).read_bytes() == raw
    assert pl.read_csv(gold).height == 2
    result2, gold2 = run(config, source)
    assert gold2 != gold  # Repeated pulls preserve distinct collection observations.
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        assert db.execute("SELECT count(*) FROM market_snapshots").fetchone()[0] == 4
    assert len(list((tmp_path / "data/silver/test").glob("*.parquet"))) == 2


def test_failed_source_preserved(tmp_path):
    source = tmp_path / "bad.csv"
    source.write_bytes(b"html instead of CSV")
    config = make_source(tmp_path / "data")
    with pytest.raises(ValueError):
        run(config, source)
    assert next((tmp_path / "data/bronze/test").glob("*.csv")).read_bytes() == source.read_bytes()
    failed = json.loads(next((tmp_path / "data/bronze/test").glob("*.json")).read_text())
    assert failed["status"] == "failed"
    assert (failed["source_id"], failed["market_id"]) == ("test", "retail-us-area-52")  # Identity kept on failure.


def test_config():
    sources = read_sources(Path(__file__).resolve().parents[1] / "config/market.toml")
    assert all(source["data_dir"].is_absolute() for source in sources)


def test_single_source_file_and_per_source_validation(tmp_path):
    shared = 'data_dir = "data"\nmax_age_hours = 24\nauction_cut = 0.05\nmin_discount = 0.2\ntop_n = 20\n'
    source = ('source_id = "{id}"\nprovider = "tsm"\ngame_version = "classic"\nregion = "us"\n'
              'scope = "house"\nrealm = "x"\nfaction = "horde"\nsource_url = "https://example.com/items.csv"\n')
    (tmp_path / "config").mkdir()
    path = tmp_path / "config/market.toml"
    path.write_text(shared + source.format(id="solo"))
    [only] = read_sources(path)
    assert (only["source_id"], only["market_id"]) == ("solo", "classic-us-x-horde")
    assert only["data_dir"] == (tmp_path / "data").resolve()
    # A per-source override is validated, not just the shared value.
    path.write_text(shared + "[[sources]]\n" + source.format(id="a") + "auction_cut = 1.5\n")
    with pytest.raises(ValueError, match="auction_cut"):
        read_sources(path)
    path.write_text(shared + "[[sources]]\n" + source.format(id="a") + "[[sources]]\n" + source.format(id="a"))
    with pytest.raises(ValueError, match="unique"):
        read_sources(path)
    path.write_text(shared + "[[sources]]\nsource_id = \"a\"\n")
    with pytest.raises(ValueError, match="missing"):
        read_sources(path)
