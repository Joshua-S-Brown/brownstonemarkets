"""Replay archived collections into fresh silver and DuckDB, without collecting or archiving."""
import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import cast

import duckdb
import polars as pl
import pyarrow.parquet as pq

from . import addon_records, markets, pipeline, scans
from .config import ADDON_PROVIDER, MARKET_KEYS, Source
from .normalization import normalize
from .storage import load_snapshot, upgrade_database


def rebuild(sources: list[Source], output: Path) -> list[str]:
    """Use recorded identities/times in stable order; retain invalid collections as reported failures."""
    output = output.resolve()
    bronze = Path(sources[0]['data_dir']) / 'bronze'
    if output.is_relative_to(bronze.resolve()):
        raise ValueError('Output must be outside bronze')
    manifests = []
    configured = {source['source_id']: source for source in sources}
    for path in sorted(bronze.glob('*/*.json')):
        manifest = markets.upgrade_legacy(json.loads(path.read_text(encoding='utf-8')))
        if manifest['source_id'] not in configured:
            raise ValueError(f"{path}: source {manifest['source_id']} needs configuration")
        manifests.append((manifest, path))
    manifests.sort(key=lambda entry: (datetime.fromisoformat(entry[0]['collected_at']), str(entry[1])))
    output.mkdir(parents=True, exist_ok=False)
    upgrade_database(output, create=True)
    lines = []
    with duckdb.connect(str(output / 'brownstone.duckdb')) as db:
        for manifest, path in manifests:
            config = cast(Source, {**configured[manifest['source_id']],
                                   **{key: manifest[key] for key in MARKET_KEYS if key in manifest},
                                   'data_dir': output, 'machine': manifest.get('machine'),
                                   'provider': manifest.get('provider', configured[manifest['source_id']]['provider'])})
            db.begin()
            try:
                _replay_collection(db, config, manifest, path)
                db.commit()
            except (ValueError, OSError, EOFError, duckdb.Error, pl.exceptions.PolarsError) as error:
                db.rollback()
                # Silver files are named after their collection; drop a failed one's so silver matches DuckDB.
                for orphan in (output / 'silver' / manifest['source_id']).glob(f"{manifest['snapshot_id']}*"):
                    orphan.unlink()
                lines.append(f'{path.name}: failed: {error}')
    return [f'Rebuilt {len(manifests) - len(lines)}/{len(manifests)} collections into {output}', *lines]


def _replay_collection(db, config: Source, manifest: dict, path: Path) -> None:
    sid = manifest['snapshot_id']
    now = datetime.fromisoformat(manifest['collected_at'])
    addon = config['provider'] == ADDON_PROVIDER
    raw_path = path.parent / manifest.get('bronze_file', f'{sid}.lua' if addon else f'{sid}.csv')
    raw = gzip.decompress(raw_path.read_bytes()) if raw_path.suffix == '.gz' else raw_path.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    if sha256 != manifest['sha256']:
        raise ValueError(f'{raw_path.name}: SHA-256 mismatch')
    silver = Path(config['data_dir']) / 'silver' / config['source_id']
    silver.mkdir(parents=True, exist_ok=True)
    if addon:
        records, non_scans = scans.read_addon_records(raw)
        # Successful reviewed imports can select a subset; failed/unfinished collections retry the raw file.
        # Like an import, a selected scan that is missing or from another house fails the whole collection;
        # an empty file has nothing to recover, so it rebuilds as nothing.
        selected = [scan['scan_id'] for scan in manifest['scans']] if 'scans' in manifest else None
        for record in non_scans:
            addon_records.summarize(record, now)
        records, summaries = pipeline._prepare_scans(records, config, now, selected, required=False)
        pipeline._load_collection(db, config, {'silver': silver}, sid, now, sha256,
                                  records, summaries, records, {}, non_scans)
    else:
        frame = normalize(raw, config['market_id'], sid, now, config['max_age_hours'],
                          config.get('allow_missing_updated_at', False))
        frame = frame.with_columns(
            *[pl.lit(value, dtype=pl.String).alias(key)
              for key, value in pipeline._observation_keys(config).items()],
            pl.lit(sha256).alias('source_sha256'))
        target = silver / f'{sid}.parquet'
        pq.write_table(frame.to_arrow(), target, compression='zstd')
        load_snapshot(db, target, frame, config)
