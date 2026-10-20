"""Today-only price and removal warnings over supplied UI-10/11 evidence."""

PRICE_NOTE = 'priced at the typical earlier price, not the current lowest'


def base_signals(result):
    """Catalog outputs use base/legacy only; variant and unresolved evidence never pools."""
    rows = sorted((result or {}).get('rows', []), key=lambda r: r['variant_state'] != 'base')
    indexed = {}
    for row in rows:
        if row['variant_id'] is None and row['variant_state'] in (None, 'base'):
            indexed.setdefault(row['item_id'], row)
    return indexed


def price_caps(signals):
    return {item_id: row['overshoot']['typical_copper'] for item_id, row in signals.items()
            if row['overshoot']['label'] == 'high' and row['overshoot']['typical_copper']}


def warning_fields(row):
    return {key: row[key] for key in ('signal', 'price_cap_copper', 'price_note', 'early_removals') if key in row}
