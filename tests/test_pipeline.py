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


BAD_DATA = [
    (b"wrong,column\n1,2", "Missing"),
    (HEADER.encode(), "no rows"),
    (csv([(1, 100, 50, 100, 100, NOW.isoformat())] * 2), "Duplicate"),
    (csv([(1, -1, 50, 100, 100, NOW.isoformat())]), "nonnegative"),
    (csv([(0, 100, 50, 100, 100, NOW.isoformat())]), "positive"),
    (csv([(1, 100, 50, 100, 100, (NOW-timedelta(days=2)).isoformat())]), "stale"),
    (csv([(1, 100, 50, 100, 100, (NOW+timedelta(hours=1)).isoformat())]), "future"),
    (csv([(1, "", 50, 100, 100, NOW.isoformat())]), "null"),
]


# Name cases by the expected error, not the time-stamped CSV, so xdist workers collect the same IDs.
@pytest.mark.parametrize("raw,match", BAD_DATA, ids=[match for _, match in BAD_DATA])
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


def test_spread_is_whole_copper_and_search_keeps_the_overall_rank(tmp_path):
    from brownstone.analysis import rank
    source = tmp_path / "input.csv"
    source.write_bytes(csv([(1, 8333, 4000, 9000, 9000, NOW.isoformat()),
                            (2, 10000, 7000, 10000, 10000, NOW.isoformat())]))
    config = make_source(tmp_path / "data")
    result, _ = run(config, source)
    # 8333 after a 5% cut is 7916.35c; revenue rounds down to 7916c, as in crafting (CRAFT-07).
    assert result["net_spread_copper"].to_list() == [3916, 2500]
    assert result["net_spread_copper"].dtype == pl.Int64
    with duckdb.connect(str(tmp_path / "data/brownstone.duckdb")) as db:
        found = rank(db, result["snapshot_id"][0], config, search="item 2")
    assert found.select("rank", "item_id").rows() == [(2, 2)]


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


def test_rebuild_replays_all_sources_deterministically_without_touching_archive(tmp_path):
    import gzip

    from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

    from brownstone.pipeline import import_scans
    from brownstone.rebuild import rebuild

    data = tmp_path / 'data'
    tsm = make_source(data, game_version='classic', realm='mankrik', faction='alliance', enabled=False)
    raw = csv([(1, 100, 50, 100, 100, '')])
    tsm['allow_missing_updated_at'] = True
    path = tmp_path / 'input.csv'
    path.write_bytes(raw)
    run(tsm, path)
    run(tsm, path)  # Same content and upstream time reuse one snapshot.
    other = {**tsm, 'source_id': 'other'}
    run(other, path)  # Same house, separate observer.
    addon = addon_source(data)
    records = [scan('full', FINISHED, [listing(1, 3, 10), listing(2, 1, 0)]),
               scan('partial', FINISHED + 1, [listing(3, 1, 50)], reported=2)]
    path = write_scans(tmp_path / 'scan.lua', *records)
    first = import_scans(addon, path, scan_ids=['full'], now=NOW)
    import_scans(addon, path, scan_ids=['partial'], now=NOW)
    # Exercise historical uncompressed bronze and legacy environment inference.
    folder = data / 'bronze/my-scans'
    archived = folder / first['bronze_file']
    archived.with_suffix('').write_bytes(gzip.decompress(archived.read_bytes()))
    for metadata in folder.glob('*.json'):
        manifest = json.loads(metadata.read_text())
        manifest['bronze_file'] = archived.with_suffix('').name
        manifest.pop('environment')
        metadata.write_text(json.dumps(manifest))
    # Recover a valid raw collection whose run failed before its derived writes finished.
    extra = write_scans(tmp_path / 'new.lua', scan('recovered', FINISHED + 2, [listing(4, 2, 30)]))
    recovered = import_scans(addon, extra, now=NOW)
    metadata = folder / f"{recovered['snapshot_id']}.json"
    manifest = json.loads(metadata.read_text())
    manifest.pop('scans')
    manifest['status'] = 'failed'
    metadata.write_text(json.dumps(manifest))
    before = {p.relative_to(data): p.read_bytes() for p in data.rglob('*') if p.is_file()}
    outputs = [tmp_path / 'one', tmp_path / 'two']
    # Current settings must not relabel historic scans or use today's clock for freshness.
    addon['environment'] = 'beta'
    addon['market_id'] += '-beta'
    addon['machine'] = 'different-machine'
    for output in outputs:
        assert rebuild([tsm, other, addon], output) == [f'Rebuilt 6/6 collections into {output}']
        with duckdb.connect(str(output / 'brownstone.duckdb')) as db:
            assert db.execute('SELECT count(*) FROM market_snapshots').fetchone()[0] == 5
            assert db.execute('SELECT count(*) FROM addon_scans').fetchone()[0] == 3
            assert db.execute('SELECT count(*) FROM scan_listings').fetchone()[0] == 4
            assert db.execute("SELECT priced FROM addon_scans WHERE scan_id='partial'").fetchone() == (False,)
            assert db.execute("SELECT min_buyout FROM market_snapshots WHERE item_id=1 AND source_id='my-scans'"
                              ).fetchone() == (4,)
            assert db.execute("SELECT min_buyout FROM market_snapshots WHERE item_id=2").fetchone() == (0,)
            assert db.execute('SELECT DISTINCT environment, machine FROM addon_scans').fetchall() == [('live', 'mac')]
            with duckdb.connect(str(data / 'brownstone.duckdb'), read_only=True) as original:
                for (table,) in db.execute('SHOW TABLES').fetchall():
                    assert db.execute(f'SELECT * FROM "{table}" ORDER BY ALL').fetchall() == original.execute(
                        f'SELECT * FROM "{table}" ORDER BY ALL').fetchall()
    with duckdb.connect(str(outputs[0] / 'brownstone.duckdb')) as a, \
            duckdb.connect(str(outputs[1] / 'brownstone.duckdb')) as b:
        for (table,) in a.execute('SHOW TABLES').fetchall():
            assert a.execute(f'SELECT * FROM "{table}" ORDER BY ALL').fetchall() == b.execute(
                f'SELECT * FROM "{table}" ORDER BY ALL').fetchall()
    left = {p.relative_to(outputs[0]): p.read_bytes() for p in (outputs[0] / 'silver').rglob('*.parquet')}
    right = {p.relative_to(outputs[1]): p.read_bytes() for p in (outputs[1] / 'silver').rglob('*.parquet')}
    assert left == right
    assert {p.relative_to(data): p.read_bytes() for p in data.rglob('*') if p.is_file()} == before
    with pytest.raises(FileExistsError):
        rebuild([tsm, other, addon], outputs[0])
    with pytest.raises(ValueError, match='outside bronze'):
        rebuild([tsm, other, addon], data / 'bronze/new')


def test_rebuild_reports_house_mismatch_and_drops_failed_silver(tmp_path, monkeypatch):
    from test_scans import FINISHED, NOW, addon_source, listing, scan, write_scans

    from brownstone import rebuild as replay
    from brownstone.pipeline import import_scans

    data = tmp_path / 'data'
    addon = addon_source(data)
    import_scans(addon, write_scans(tmp_path / 'scan.lua', scan('full', FINISHED, [listing(1, 1, 10)])), now=NOW)
    moved = {**addon, 'scan_evidence': {**addon['scan_evidence'], 'zone': 'Ironforge'}}
    lines = replay.rebuild([moved], tmp_path / 'house')
    assert lines[0].startswith('Rebuilt 0/1') and 'does not match the configured market' in lines[1]
    tsm = make_source(data, source_id='tsm', allow_missing_updated_at=True)
    path = tmp_path / 'input.csv'
    path.write_bytes(csv([(1, 100, 50, 100, 100, '')]))
    run(tsm, path)

    def fail(*args):
        raise duckdb.Error('load failed')
    monkeypatch.setattr(replay, 'load_snapshot', fail)
    output = tmp_path / 'load'
    assert 'load failed' in replay.rebuild([addon, tsm], output)[1]
    assert not list((output / 'silver/tsm').iterdir())
