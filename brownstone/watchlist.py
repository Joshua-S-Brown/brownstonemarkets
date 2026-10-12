"""Local target preferences and read-only base-item watchlist evidence."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .action_board import compatible_catalogs
from .config import ADDON_PROVIDER
from .freshness import assess
from .metrics import units_below_price
from .money import format_money, parse_money
from .storage import latest_snapshot, scope_predicate
from .today_data import read_skillup_market


@dataclass(frozen=True)
class Entry:
    item_id: int
    buy_copper: int | None = None
    sell_copper: int | None = None
    note: str = ''

    def __post_init__(self):
        if type(self.item_id) is not int or self.item_id <= 0:
            raise ValueError('Item ID must be a positive integer')
        targets = (self.buy_copper, self.sell_copper)
        if not any(value is not None for value in targets):
            raise ValueError('At least one target is required')
        if any(value is not None and (type(value) is not int or value <= 0) for value in targets):
            raise ValueError('Targets must be positive integer copper')
        if not isinstance(self.note, str):
            raise ValueError('Note must be text')


def parse_entry(item_id: int, buy: str, sell: str, note: str = '') -> Entry:
    return Entry(item_id, parse_money(buy) if buy.strip() else None,
                 parse_money(sell) if sell.strip() else None, note)


def watchlist_path(data_dir: Path, source_id: str) -> Path:
    return data_dir / f'watchlist.{source_id}.local.json'


def _validate(entries: list[Entry]) -> None:
    if len({entry.item_id for entry in entries}) != len(entries):
        raise ValueError('One entry per item ID is allowed')


def load_entries(path: Path) -> list[Entry]:
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise ValueError("Watchlist must be a JSON list")
    entries = [Entry(**row) for row in rows]
    _validate(entries)
    return entries


def save_entries(path: Path, entries: list[Entry]) -> None:
    # Recheck at save time: a file damaged since the page opened must also be preserved.
    load_entries(path)
    _validate(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps([asdict(entry) for entry in entries], indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def catalog_names(catalogs, config) -> dict[int, str]:
    return {i: item['name'] for c in compatible_catalogs(catalogs, config)
            for i, item in c['items_by_id'].items() if item.get('name')}


def known_names(db, config, catalogs) -> dict[int, str]:
    """Pick labels from this source/market's base observations and compatible catalogs only."""
    names = catalog_names(catalogs, config)
    predicate, parameters = scope_predicate(config)
    # Newest name per item; market snapshots override scan listings, as both override catalogs.
    for table, order in (('scan_listings', 'scan_id, listing_index'),
                         ('market_snapshots', 'collected_at, snapshot_id')):
        rows = db.execute(f"SELECT item_id, arg_max(item_name, row({order})) FROM {table} WHERE {predicate} "
                          "AND variant_id IS NULL AND (variant_state IS NULL OR variant_state='base') "
                          "AND item_name IS NOT NULL AND item_name <> '' AND item_name <> concat('Item ', item_id) "
                          "GROUP BY item_id", parameters).fetchall()
        names.update(dict(rows))
    return names


def build_watchlist(entries, context, snapshot, now, max_age_hours, buy_units=None):
    """Return plain rows; missing prices never become zero or hits."""
    freshness = assess(snapshot, now, max_age_hours) if snapshot else None
    rows = []
    for entry in entries:
        market = context.get(entry.item_id, {}) if snapshot else {}
        price = market.get('min_buyout')
        price = price if price and price > 0 else None
        buy_hit = price is not None and entry.buy_copper is not None and price <= entry.buy_copper
        sell_hit = price is not None and entry.sell_copper is not None and price >= entry.sell_copper
        rows.append({'entry': entry, 'price': price, 'units': market.get('units'),
                     'buy_units': (buy_units or {}).get(entry.item_id), 'buy_hit': buy_hit, 'sell_hit': sell_hit,
                     'buy_state': _state(entry.buy_copper, buy_hit, price, freshness),
                     'sell_state': _state(entry.sell_copper, sell_hit, price, freshness)})
    return {'rows': rows, 'freshness': freshness}


def _state(target, hit, price, freshness):
    if target is None:
        return '—'
    if freshness is None:
        return 'no snapshot'
    state = 'not listed' if price is None else 'hit' if hit else 'not hit'
    return state + (' · stale' if freshness['stale'] else '')


def hit_text(row: dict, names: dict[int, str]) -> str:
    """One current-hit line naming only the sides that hit; shared by both apps' panels."""
    states = []
    if row['buy_hit']:
        units = (f"{row['buy_units']} units at or below target" if row['buy_units'] is not None
                 else 'units not available for this source')
        states.append(f"Buy {row['buy_state']} · {units}")
    if row['sell_hit']:
        states.append(f"Sell {row['sell_state']}")
    item = row['entry'].item_id
    return f"{names.get(item, 'Unknown item')} ({item}) · {format_money(row['price'])} · {'; '.join(states)}"


def read_watchlist(db, config, entries, now):
    snapshot, sid, _ = latest_snapshot(config)
    ids = [entry.item_id for entry in entries]
    context = read_skillup_market(db, config, sid, ids) if snapshot else {}
    units = {}
    if snapshot and config['provider'] == ADDON_PROVIDER:
        for entry in entries:
            if entry.buy_copper is not None:
                counts = [units_below_price(db, config, sid, entry.item_id, entry.buy_copper + 1,
                                           variant_state=state) for state in (None, 'base')]
                units[entry.item_id] = None if any(n is None for n in counts) else sum(counts)
    return build_watchlist(entries, context, snapshot, now, config['max_age_hours'], units)
