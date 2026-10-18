"""Freeze source bronze and compare page headlines under the current code and catalogs."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import duckdb
from fastapi import HTTPException

from brownstone import ledger_view, market_explorer, market_presentation, rebuild, recipe_catalogs, sales_speed
from brownstone.config import Source
from brownstone.scan_changes import eligible_scans
from brownstone.storage import scope_predicate

from . import context, team, today

CORPUS_ROOT = context.ROOT / 'work/beta-corpus'


def hashes(folder: Path) -> dict[str, str]:
    """Hash frozen inputs, excluding the manifest, replaceable expectations and Finder metadata."""
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file() and p.name != '.DS_Store'
            and p.relative_to(folder).as_posix() not in ('manifest.json', 'expected.json')}


def headlines(folder: Path, reference_time: str | None = None) -> tuple[dict, dict]:
    """Replay once, then read the same uncached projections as the pages at one fixed instant."""
    source = cast(Source, json.loads((folder / 'source.json').read_text(encoding='utf-8')) |
                  {'data_dir': folder})
    with TemporaryDirectory(prefix='brownstone-beta-') as temporary:
        output = Path(temporary) / 'data'
        lines = rebuild.rebuild([source], output)
        if len(lines) != 1:
            raise ValueError('\n'.join(lines[1:]))
        shutil.copytree(folder / 'bronze', output / 'bronze')
        for path in folder.glob(f"*.{source['source_id']}.local.json"):
            shutil.copyfile(path, output / path.name)
        source = source | {'data_dir': output}
        with duckdb.connect(str(output / 'brownstone.duckdb'), read_only=True) as db:
            scans = eligible_scans(db, source)
            if not scans:
                raise ValueError('Corpus has no eligible scans')
            predicate, params = scope_predicate(source)
            count = db.execute(f'SELECT count(*) FROM addon_scans WHERE {predicate}', params).fetchone()
            assert count is not None
            scan_count = count[0]
        now = datetime.fromisoformat(reference_time) if reference_time else scans[0]['finished_at']
        catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(context.ROOT / 'config'))
        if errors:
            raise ValueError('\n'.join(errors))
        explorer = market_explorer.load_explorer(source, catalogs, now)
        market = market_presentation.project(explorer['market'], role='levels',
                                            level_ids=market_presentation.level_items(explorer, 25))
        plan, _ = today.build(source, today.PlanRequest(), now)
        roster = team.build(source, 25, now)['payload']['roster']
        ledger = ledger_view.page(ledger_view.load(source, catalogs, now), 'all', now)
        if ledger['errors']:
            raise ValueError(str(ledger['errors']))
        speed = sales_speed.select(sales_speed.load(source, [2589]), 2589, None, 'base', source)
        numbers = {'data.eligible_scans': len(scans), 'data.newest_scan_id': scans[0]['scan_id'],
                   'market.grid_rows': len(market['rows']), 'market.chain_count': market['chain_count'],
                   'today.route_steps': len(plan['stops']),
                   'today.planned_profit_copper': plan['plan']['queue']['expected_profit_copper'],
                   'team.characters': len(roster), 'ledger.team_net_copper': ledger['gold']['team']['net_copper'],
                   'ledger.reconciled_pairs': ledger['gold']['pairs']['reconciled'],
                   'item.2589.daily_units': speed['daily_units'],
                   'item.2589.suggested_units': speed['suggested_units']}
        return numbers, dict(scan_count=scan_count, eligible_scan_count=len(scans), character_count=len(roster),
                             newest_scan_id=scans[0]['scan_id'], reference_time=now.isoformat())


def freeze(folder: Path, source: Source) -> None:
    folder = folder.resolve()
    if not folder.is_relative_to(CORPUS_ROOT.resolve()) or folder == CORPUS_ROOT.resolve():
        raise ValueError('Freeze destination must be under work/beta-corpus/')
    data = Path(source['data_dir']).resolve()
    if folder.is_relative_to(data) or data.is_relative_to(folder):
        raise ValueError('Freeze destination must be separate from data_dir')
    folder.mkdir(parents=True, exist_ok=False)
    try:
        _fill(folder, data, source)
    except BaseException:
        shutil.rmtree(folder)  # Created above; a partial corpus would block the retry.
        raise


def _fill(folder: Path, data: Path, source: Source) -> None:
    shutil.copytree(data / 'bronze' / source['source_id'], folder / 'bronze' / source['source_id'])
    for path in data.glob(f"*.{source['source_id']}.local.json"):
        shutil.copyfile(path, folder / path.name)
    resolved = {k: v for k, v in source.items() if k not in ('scan_path', 'drop_folder', 'data_dir')}
    (folder / 'source.json').write_text(json.dumps(resolved, indent=2) + '\n', encoding='utf-8')
    frozen = hashes(folder)
    numbers, metadata = headlines(folder)
    if hashes(folder) != frozen:
        raise ValueError('Corpus files changed during freeze')
    manifest = metadata | {'file_count': len(frozen), 'sha256': frozen}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (folder / 'expected.json').write_text(json.dumps(numbers, indent=2) + '\n', encoding='utf-8')
    print(f'Frozen {len(frozen)} files into {folder}')


def check(folder: Path, accept: bool = False) -> int:
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    expected = json.loads((folder / 'expected.json').read_text(encoding='utf-8'))
    if hashes(folder) != manifest['sha256']:
        raise ValueError('Corpus hash mismatch: missing, changed or unexpected file')
    differences = []
    try:
        actual, _ = headlines(folder, manifest['reference_time'])
        for name in sorted(expected.keys() | actual.keys()):
            differs = name not in expected or name not in actual or expected[name] != actual[name]
            print(f"{name}: expected={expected.get(name)} actual={actual.get(name)}{' DIFFERENT' if differs else ''}")
            if differs:
                differences.append(name)
    finally:
        if hashes(folder) != manifest['sha256']:
            raise ValueError('Corpus hash mismatch after replay')
    if accept:
        (folder / 'expected.json').write_text(json.dumps(actual, indent=2) + '\n', encoding='utf-8')
        print('Accepted current headline numbers.')
    return int(bool(differences) and not accept)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freezing = commands.add_parser('freeze')
    freezing.add_argument('corpus_dir', type=Path)
    freezing.add_argument('--source', default='forever-us-normal-alliance-addon')
    checking = commands.add_parser('check')
    checking.add_argument('corpus_dir', type=Path)
    checking.add_argument('--accept', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'freeze':
            source = context.resolve(args.source)
            if source['provider'] != 'addon':
                raise ValueError('Beta corpus requires an addon source')
            freeze(args.corpus_dir, source)
            return 0
        return check(args.corpus_dir, args.accept)
    except (OSError, ValueError, KeyError, duckdb.Error, HTTPException) as error:
        print(f'Beta corpus error: {error}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
