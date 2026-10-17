"""Market presentation: exact identities, deterministic groups and UI-11 card order."""
from .market_explorer import identity

SORT_FIELDS = {'name', 'price_copper', 'typical_copper', 'gap_percent', 'listings', 'units', 'signal'}


def sort_rows(rows, sort='gap_percent', descending=True):
    field = sort if sort in SORT_FIELDS else 'gap_percent'
    def value(row):
        v = row['signal']['crowding'] if field == 'signal' and row['signal'] else row.get(field)
        if field == 'name':
            v = v.casefold()
        return abs(v) if field == 'gap_percent' and v is not None else v
    ordered = sorted(rows, key=lambda r: (r['name'].casefold(), r['item_id'],
                                          r['variant_state'] or '', r['variant_id'] or ''))
    known = [r for r in ordered if value(r) is not None]
    unknown = [r for r in ordered if value(r) is None]
    return sorted(known, key=value, reverse=descending) + unknown


def grouped_rows(rows, role='all', q='', sort='gap_percent', descending=True):
    """Pick a base/legacy parent, never aggregate prices or supply; retain all sibling identities."""
    groups: dict[int, list[dict]] = {}
    for row in rows:
        groups.setdefault(row['item_id'], []).append(row)
    parents = []
    for siblings in groups.values():
        ordered = sorted(siblings, key=lambda r: (r['variant_state'] not in ('base', None),
                         r['variant_state'] != 'base', r['variant_state'] or '', r['variant_id'] or ''))
        parent, *variants = ordered
        if any(matches(r, role, q) for r in siblings):
            parents.append(parent | {'variants': variants})
    return sort_rows(parents, sort, descending)


def matches(row, role, q):
    search = q.strip().casefold()
    if search:
        return search in row['name'].casefold() or search in str(row['item_id'])
    if role == 'signal':
        signal = row['signal']
        return bool(row['roles'] and signal and (signal['crowding'] == 'contested' or
                                                signal['overshoot']['label'] in ('cheap', 'high')))
    if role == 'crafts':
        return bool({'crafts', 'intermediates'} & set(row['roles']))
    return bool(row['roles']) if role == 'all' else role in row['roles']


def cards(page):
    """Enrich without reselecting/reordering UI-11 and removal evidence; expose three plus the remainder."""
    indexed = {identity(r): r for r in page['rows']}
    chain_ids = set(page.get('chain_ids', [r['item_id'] for r in page['rows'] if r['roles']]))
    result = {}
    for kind, signals in page['pulse'].items():
        rows = []
        for signal in signals:
            row = indexed.get(identity(signal))
            # A removed identity may no longer be listed: never borrow another identity's current price.
            rows.append({'item_id': signal['item_id'], 'name': signal['item_name'],
                         'variant_id': signal['variant_id'], 'variant_state': signal['variant_state'],
                         'quality': row['quality'] if row else None,
                         'price_copper': row['price_copper'] if row else None,
                         'typical_copper': row['typical_copper'] if row else None,
                         'gap_percent': row['gap_percent'] if row else None,
                         'sparkline': row['sparkline'] if row else [],
                         'outside_chains': not row['roles'] if row else signal['item_id'] not in chain_ids,
                         'removed_units': signal['early']['units'] if kind == 'early' else None})
        result[kind] = {'preview': rows[:3], 'more': rows[3:]}
    return result


def project(page, role='all', q='', sort='gap_percent', descending=True):
    return page | {'rows': grouped_rows(page['rows'], role, q, sort, descending), 'cards': cards(page),
                   'item_count': len({r['item_id'] for r in page['rows']}),
                   'identity_count': len(page['rows']),
                   'listed_chain_count': len({r['item_id'] for r in page['rows'] if r['roles']})}
