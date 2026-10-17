"""Read-only source resolution and existing projection access."""
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException

from brownstone import config, market_explorer, navigation, recipe_catalogs
from brownstone.config import Source
from brownstone.freshness import assess
from brownstone.storage import latest_snapshot

from .models import Evidence, SourceOption

ROOT = Path(__file__).resolve().parents[1]
CACHE_MINUTES = 60  # Freshness, floods and movement depend on the clock; recompute at least this often.
_cache: dict[str, tuple[tuple, dict]] = {}
_lock = threading.Lock()


def enabled() -> list[Source]:
    sources = [s for s in config.read_sources(ROOT / 'config/market.toml',
                                            ROOT / 'config' / config.LOCAL_OVERRIDES) if s['enabled']]
    order = navigation.experiences(sources)
    return sorted(sources, key=lambda s: order.index(s['game_version']))


def resolve(source: str, sources: list[Source] | None = None) -> Source:
    options = enabled() if sources is None else sources
    if source:
        chosen = next((s for s in options if s['source_id'] == source), None)
        if chosen is None:
            raise HTTPException(404, 'Source unavailable. Choose an enabled source.')
        return chosen
    if len(options) == 1:
        return options[0]
    raise HTTPException(409, 'Choose a source. Sources are never merged.')


def option(source: Source) -> SourceOption:
    return SourceOption(source_id=source['source_id'], label=source.get('label') or navigation.source_label(source),
                        short_label=navigation.source_label(source), game_version=source['game_version'])


def evidence(source: Source, snapshot: dict | None = None) -> Evidence:
    if snapshot is None:
        manifest, sid, _ = latest_snapshot(source)
        snapshot = {**manifest, 'snapshot_id': sid} if manifest else {}
    return Evidence(source_id=source['source_id'], market_id=source['market_id'],
                    scan_id=snapshot.get('scan_id') or snapshot.get('snapshot_id'),
                    finished_at=snapshot.get('updated_at') or snapshot.get('collected_at'),
                    freshness=assess(snapshot, datetime.now(UTC), source['max_age_hours']) if snapshot else None)


def _stamp(path: Path) -> tuple:
    stat = path.stat() if path.exists() else None
    return (stat.st_mtime_ns, stat.st_size) if stat else ()


def _inputs(source: Source, now: datetime) -> tuple:
    """Everything load_explorer reads: the source, its database, the config folder and the clock bucket."""
    config_files = sorted(p for p in (ROOT / 'config').rglob('*') if p.is_file())
    return (repr(sorted(source.items(), key=lambda kv: kv[0])),
            _stamp(Path(source['data_dir']) / 'brownstone.duckdb'),
            _stamp(Path(source['data_dir']) / 'brownstone.duckdb.wal'),  # Unflushed imports.
            tuple((p.as_posix(), _stamp(p)) for p in config_files),
            int(now.timestamp() // (CACHE_MINUTES * 60)))


def explorer(source: Source) -> dict:
    """The Market explorer projection, reused until its inputs change (about 3 s to build on real data).

    Callers only read the result, so one copy is shared between requests."""
    now = datetime.now(UTC)
    key = _inputs(source, now)
    with _lock:  # One build at a time; concurrent requests wait for it rather than repeat it.
        cached = _cache.get(source['source_id'])
        if cached and cached[0] == key:
            return cached[1]
        catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(ROOT / 'config'))
        result = market_explorer.load_explorer(source, catalogs, now)
        result['catalog_errors'] = errors
        _cache[source['source_id']] = (key, result)
        return result
