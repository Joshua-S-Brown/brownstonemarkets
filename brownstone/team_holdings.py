"""Scoped bags and bank holdings, read from captured evidence and shared by Stock and Today."""
import re

from . import character_snapshots, variants
from .scans import _list, _utc


def _usable(slot):
    return slot.get('item_id') is not None and slot.get('count') is not None


def holdings(data, now):
    """Each location's capture is the shared latest readable one (``character_snapshots.latest_data``).

    Totals are keyed by exact ADDON-08 identity ``(item_id, variant_id, variant_state)``: variants and
    unresolved links are never pooled with the base item.
    """
    totals, names, captures, units = {}, {}, [], []
    for key, state in sorted(data.items()):
        for kind in ('bags', 'bank'):
            record, machine = state.get(kind) or (None, None)
            slots = _list(record.get('slots'), 'slots') if record else []
            captured = _utc(record['captured_at'], record.get('captured_at_utc'), 'captured_at') if record else None
            captures.append({'character': key[0], 'realm': key[1], 'faction': key[2], 'kind': kind,
                             'captured_at': captured,
                             'age_hours': (now - captured).total_seconds() / 3600 if captured else None,
                             'snapshot_id': record['snapshot_id'] if record else None,
                             'units': sum(s['count'] for s in slots if _usable(s)) if record else None,
                             'machine': machine, 'unknown': record is None,
                             # Readable but incomplete (unsized or unreadable containers, unread slots).
                             'partial': record is not None and (not character_snapshots._complete(record)
                                                                or not all(map(_usable, slots))),
                             'excluded': sum(character_snapshots.unreadable_backpack(r)
                                             for r, _ in state['observations'] if r['kind'] == kind)})
            _add_slots(slots, key, kind, totals, names, units)
    return totals, names, captures, units


def _add_slots(slots, key, kind, totals, names, units):
    counts: dict[tuple, int] = {}
    for slot in filter(_usable, slots):
        identity = (slot['item_id'], *variants.identity(slot['item_id'], slot.get('item_link')))
        totals[identity] = totals.get(identity, 0) + slot['count']
        counts[identity] = counts.get(identity, 0) + slot['count']
        label = re.search(r'\|h\[([^\]]+)\]\|h', slot.get('item_link') or '')
        if label:  # the exact identity's own link name; base names also label the item ID
            names[identity] = label[1]
            if identity[2] == 'base':
                names[identity[0]] = label[1]
    units.extend({'key': identity, 'item_id': identity[0], 'character': key[0], 'realm': key[1],
                  'faction': key[2], 'kind': kind, 'units': count} for identity, count in counts.items())
