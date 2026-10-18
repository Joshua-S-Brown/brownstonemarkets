"""Scoped team holdings, local targets and depth-aware restock estimates (STORY-061)."""
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from . import character_snapshots, sales_speed
from .action_board import compatible_catalogs
from .crafting import basis_prices
from .freshness import assess
from .scans import _list
from .team_holdings import holdings
from .today import Ladder
from .today_loading import load_today
from .today_settings import TodaySettings
from .watchlist import catalog_names


@dataclass(frozen=True)
class Entry:
    item_id: int
    target_units: int
    buy_copper: int | None = None
    buy_percent: int | None = None

    def __post_init__(self):
        for label, value, minimum in (("Item ID", self.item_id, 1), ("Target units", self.target_units, 0)):
            if type(value) is not int or value < minimum:
                raise ValueError(f'{label} must be an integer >= {minimum}')
        for value in (self.buy_copper, self.buy_percent):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError('Buy limits must be positive integers')
        if self.buy_copper is not None and self.buy_percent is not None:
            raise ValueError('Choose either fixed copper or percentage, not both')


def targets_path(data_dir: Path, source_id: str) -> Path:
    return data_dir / f'stock_targets.{source_id}.local.json'


def _validate(entries):
    if len({entry.item_id for entry in entries}) != len(entries):
        raise ValueError('One entry per item ID is allowed')


def load_entries(path: Path) -> list[Entry]:
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return []
    if not isinstance(raw, list):
        raise ValueError('Stock targets must be a JSON list')
    entries = [Entry(**row) for row in raw]
    _validate(entries)
    return entries


def save_entries(path: Path, entries: list[Entry]) -> None:
    load_entries(path)
    _validate(entries)
    # Reconstruct to validate even a caller's modified draft before touching the file.
    entries = [Entry(**asdict(entry)) for entry in entries]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps([asdict(e) for e in entries], indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def fill(entry, held, listings, observations):
    """``observations`` are the scan's base price observations, which carry ADDON-03 ``market_value``."""
    short = max(0, entry.target_units - held)
    limit = entry.buy_copper
    reference = observations.get(entry.item_id, {}).get('market_value')
    limit_unknown = entry.buy_percent is not None and (reference is None or reference <= 0)
    if entry.buy_percent is not None and reference and reference > 0:
        limit = reference * entry.buy_percent // 100
    ladder = Ladder(listings or [])
    available = ladder.units[-1]
    eligible = sum(q for q, b, p in listings or [] if q > 0 and b > 0 and p > 0 and
                   (limit is None or p <= limit)) if not limit_unknown else 0
    buy = min(short, eligible)
    quote = ladder.quote(buy) if buy else None
    full = ladder.quote(short) if short else None
    return {'short': short, 'limit_copper': limit, 'limit_unknown': limit_unknown,
            'buy_units': buy, 'wait_units': min(short, available) - buy, 'unlisted_units': max(0, short - available),
            'buy_cost_copper': quote['cost_copper'] if quote else 0,
            'purchased_units': quote['purchased_units'] if quote else 0,
            'fill_cost_copper': full['cost_copper'] if full else (0 if short == 0 else None),
            'wait_cost_copper': full['cost_copper'] - (quote['cost_copper'] if quote else 0) if full else None}


VARIANT_LABELS = {'variant': 'variant, not priced', 'unresolved': 'identity unresolved, not priced'}


def build_stock(data, entries, arguments, config, catalogs, now):
    totals, names, captures, units = holdings(data, now)
    names = catalog_names(catalogs, config) | names
    args = arguments or {}
    snapshot = args.get('snapshot')
    observations = args.get('observations', {}) if snapshot else {}
    _, prices = basis_prices(observations, 'cautious')
    # Targets and prices are for the base item; legacy null-state rows never arise from links.
    targets = {(entry.item_id, None, 'base'): entry for entry in entries}
    rows = []
    uncertain = not captures or any(c['unknown'] or c['partial'] for c in captures)
    for key in sorted(totals.keys() | targets.keys(), key=lambda k: (k[0], k[2], k[1] or '')):
        item, _, state = key
        held = totals.get(key, 0)
        price = prices.get(item) if state == 'base' else None
        row = {'key': key, 'item_id': item, 'variant_state': state,
               'name': names.get(key, names.get(item, f'Item {item}'))
               + ('' if state == 'base' else f' ({VARIANT_LABELS[state]})'),
               'held': held, 'unit_copper': price, 'value_copper': held * price if price is not None else None,
               'entry': targets.get(key), 'at_most': uncertain}
        if key in targets:
            row.update(fill(targets[key], held, (args.get('listings') or {}).get(item), observations))
        rows.append(row)
    rows.sort(key=lambda r: (-bool(r.get('short')), r['name'].casefold(), r['item_id'], r['variant_state']))
    return {'config': config, 'snapshot': snapshot, 'captures': captures, 'holdings': units, 'rows': rows,
            'entries': entries, 'chain_ids': {i for c in catalogs for i in c['items_by_id']},
            'freshness': assess(snapshot, now, config['max_age_hours']) if snapshot else None,
            'value_copper': sum(r['value_copper'] or 0 for r in rows),
            'excluded_prices': sum(r['held'] > 0 and r['unit_copper'] is None for r in rows),
            'items_held': len(totals),
            'names': {k: v for k, v in names.items() if isinstance(k, int)},
            'items_short': sum(bool(r.get('short')) for r in rows),
            'buy_cost_copper': sum(r.get('buy_cost_copper', 0) for r in rows)}


def load_stock(config, catalogs, now: datetime):
    """Read each evidence source once; only targets require purchase quotes."""
    data = character_snapshots.latest_data(config)
    entries = load_entries(targets_path(config['data_dir'], config['source_id']))
    catalogs = compatible_catalogs(catalogs, config)
    ids = {s['item_id'] for state in data.values() for r, _ in state['observations']
           for s in _list(r.get('slots'), 'slots') if s.get('item_id') is not None}
    ids.update(e.item_id for e in entries)
    _, arguments = load_today(config, catalogs, TodaySettings(), {}, now, item_ids=ids,
                              holdings_data=holdings(data, now))
    result = build_stock(data, entries, arguments, config, catalogs, now)
    try:
        speeds = sales_speed.load(config, sorted(ids))
    except Exception:  # A removal-speed read failure shows as unavailable and keeps Stock.
        speeds = None
    for row in result['rows']:
        item_id, variant_id, state = row['key']
        row['speed'] = None if speeds is None else sales_speed.select(speeds, item_id, variant_id, state, config)
    return result


def filter_rows(result, query='', chains_only=False):
    query = query.strip().casefold()
    return [r for r in result['rows'] if (not chains_only or r['item_id'] in result['chain_ids']) and
            (not query or query in r['name'].casefold() or query in str(r['item_id']))]
