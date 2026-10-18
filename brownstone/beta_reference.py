"""Display-only UI-11 evidence from an explicitly paired beta market (STORY-102)."""
from . import flood_signals
from .navigation import source_label
from .scan_changes import eligible_scans


def read(db, reference, identities):
    """Use the beta's own newest clock and scope; pair only exact identities."""
    scans = eligible_scans(db, reference)
    newest = scans[0]['finished_at'] if scans else None
    block = {'source_id': reference['source_id'], 'label': reference.get('label') or source_label(reference),
             'market_id': reference['market_id'], 'newest_scan': newest}
    if newest is None:
        return block, {}
    signals = flood_signals.signals(db, reference, sorted({key[0] for key in identities}), newest)
    rows = {}
    for row in signals['rows']:
        key = row['item_id'], row['variant_id'], row['variant_state']
        if key in identities:
            rows[key] = {k: row['overshoot'][k] for k in ('typical_copper', 'days', 'scans')}
    return block, rows


def project(evidence, price, live_typical):
    """Null quotes never become free; fade only when this live identity has a typical."""
    typical = evidence.get('typical_copper') if evidence else None
    usable = price is not None and price > 0 and typical is not None and typical > 0
    visible = usable and live_typical is None
    return {'beta_typical_copper': typical if visible else None, 'beta_faded': live_typical is not None,
            'beta_ratio': {'numerator': price, 'denominator': typical} if visible else None}
