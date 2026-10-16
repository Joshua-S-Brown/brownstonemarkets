"""Market adapters: projections own all calculations and scope."""
from datetime import UTC, datetime

from fastapi import APIRouter

from brownstone import market_explorer as me

from . import context
from .models import BestUse, Item, SearchHit

router = APIRouter()


def quality(row):
    return row.get('quality') if row else None


SEARCH_LIMIT = 50  # The palette lists names; a one-letter query on real data matches thousands.


def closeness(row, query):
    """Palette order only: exact item ID, then names starting with the query, then the rest by name."""
    name = row['item_name'].casefold()
    return (str(row['item_id']) != query, not name.startswith(query), name)


@router.get('/search', response_model=list[SearchHit])
def search(source: str = '', q: str = ''):
    result = context.explorer(context.resolve(source))
    rows = sorted(me.search_items(result, q), key=lambda r: closeness(r, q.strip().casefold()))
    items = [SearchHit(kind='item', name=r['item_name'], item_id=r['item_id'], quality=quality(r),
                        variant_state=r['variant_state'], variant_id=r['variant_id'])
             for r in rows[:SEARCH_LIMIT]]
    characters = [SearchHit(kind='character', name=' · '.join(identity))
                  for identity in result['characters'] if q.casefold() in ' · '.join(identity).casefold()]
    return items + characters


def best_use(choice):
    row = choice['recipe']
    if row is None:
        return BestUse(reason=choice['reason'])
    item_id = row['recipe']['output_item_id']
    return BestUse(item_id=item_id, name=row['catalog']['items_by_id'][item_id]['name'],
                   profit_copper=row['value']['profit_copper'], reason=row['value']['action'])


@router.get('/items/{item_id}', response_model=Item)
def item(item_id: int, source: str = ''):
    chosen = context.resolve(source)
    result = context.explorer(chosen)
    page = me.item_page(result, item_id)
    summary = me.item_summary(chosen, result, page, datetime.now(UTC))
    observed, signal = summary['observed'] or {}, summary['signal'] or {}
    return Item(item_id=item_id, name=page['name'], quality=quality(observed),
                price_copper=observed.get('min_buyout'),
                typical_copper=signal.get('overshoot', {}).get('typical_copper'),
                units=summary['metrics'].get('units'), listings=summary['metrics'].get('listings'),
                vendor_buy=page['vendor_buy'], vendor_sell=page['vendor_sell'], held=summary['held'],
                at_least=summary['at_least'], crowding=signal.get('crowding'),
                overshoot=signal.get('overshoot', {}).get('label'), used_in=best_use(summary['used_in']),
                made_from=best_use(summary['made_from']), evidence=context.evidence(chosen, result['snapshot'] or {}),
                details={k: summary[k] for k in ('captures', 'holdings', 'holdings_warning',
                                               'floods_error', 'signal')} |
                {'catalog_errors': result['catalog_errors']})
