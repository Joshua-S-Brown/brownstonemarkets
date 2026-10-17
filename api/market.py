"""Market adapters: projections own all calculations and scope."""
import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from brownstone import item_history
from brownstone import market_explorer as me

from . import context
from .models import Activity, BestUse, Chain, History, Item, Ladder, Market, SearchHit

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
    items = [SearchHit(kind='item', name=r['item_name'], item_id=r['item_id'], quality=quality(r), role=r.get('role'),
                        variant_state=r['variant_state'], variant_id=r['variant_id'])
             for r in rows[:SEARCH_LIMIT]]
    characters = [SearchHit(kind='character', name=identity[0], character=identity)
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
def item(item_id: int, source: str = '', variant: str = ''):
    chosen = context.resolve(source)
    result = context.explorer(chosen)
    page = me.item_page(result, item_id)
    summary = me.item_summary(chosen, result, page, datetime.now(UTC))
    selected = None
    if variant:
        try:
            selected = json.loads(variant)
            if (not isinstance(selected, list) or len(selected) != 2 or
                    selected[0] not in ('base', 'variant', 'unresolved', None) or
                    not isinstance(selected[1], (str, type(None)))):
                raise ValueError('Unknown identity')
        except (ValueError, TypeError) as error:
            raise HTTPException(400, 'Choose an identity from search.') from error
    observed, signal, metrics = me.chosen_identity(page, summary, selected)
    summary = summary | {'signal': signal}
    if selected is not None and selected[0] in ('variant', 'unresolved'):
        summary = summary | {'held': None, 'at_least': False}
        summary = summary | {k: {'recipe': None, 'reason': 'Separate identity; base-item routes excluded'}
                             for k in ('made_from', 'used_in')}
    return Item(item_id=item_id, name=observed.get('item_name') or page['name'], quality=quality(observed),
                price_copper=observed.get('min_buyout'),
                typical_copper=signal.get('overshoot', {}).get('typical_copper'),
                units=metrics.get('units'), listings=metrics.get('listings'),
                vendor_buy=page['vendor_buy'], vendor_sell=page['vendor_sell'], held=summary['held'],
                at_least=summary['at_least'], crowding=signal.get('crowding'),
                overshoot=signal.get('overshoot', {}).get('label'), used_in=best_use(summary['used_in']),
                made_from=best_use(summary['made_from']), evidence=context.evidence(chosen, result['snapshot'] or {}),
                details={k: summary[k] for k in ('captures', 'holdings', 'holdings_warning',
                                               'floods_error', 'signal')} |
                {'catalog_errors': result['catalog_errors'], 'identities': page['observed'],
                 'catalogs': [c['catalog_id'] for c in result['catalogs']],
                 'incompatible': [c['catalog_id'] for c in result['incompatible']],
                 'rules_version': chosen.get('rules_version'), 'variant': variant,
                 'floods': {k: summary['floods'].get(k)
                            for k in ('settings', 'scan', 'freshness', 'note')}})


@router.get('/market', response_model=Market)
def market(source: str = ''):
    chosen = context.resolve(source)
    result = context.explorer(chosen)
    return jsonable_encoder(result['market'] | {'evidence': context.evidence(chosen, result['snapshot'] or {})})


def read_history(chosen, item_id):
    try:
        return item_history.load_history(chosen, item_id)
    except Exception as error:
        raise HTTPException(503, f'Unable to read item history: {error}. Use Data, then reopen this item.') from error


@router.get('/items/{item_id}/history', response_model=History)
def history(item_id: int, source: str = ''):
    chosen = context.resolve(source)
    result = read_history(chosen, item_id)
    try:
        removals, error = me.item_removals(chosen, item_id), None
    except Exception as failure:
        removals, error = {}, f'Unable to read removed listings: {failure}. Use Data, then reopen this item.'
    return jsonable_encoder({k: result[k] for k in ('scans', 'points', 'other_identities', 'note')} |
                            {'removals': removals, 'removals_error': error})


@router.get('/items/{item_id}/ladder', response_model=Ladder)
def ladder(item_id: int, source: str = '', scan: str = ''):
    chosen = context.resolve(source)
    evidence = read_history(chosen, item_id)
    selected = scan or (evidence['scans'][0]['scan_id'] if evidence['scans'] else '')
    try:
        result = item_history.load_ladder(chosen, item_id, evidence, selected)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        raise HTTPException(503, f'Unable to read ladder: {error}. Use Data, then reopen this item.') from error
    return jsonable_encoder(result | {'zoom_copper': item_history.zoom_end(result['rows'])})


@router.get('/items/{item_id}/chain', response_model=Chain)
def chain(item_id: int, source: str = ''):
    return jsonable_encoder(me.item_chain(context.explorer(context.resolve(source)), item_id))


@router.get('/items/{item_id}/activity', response_model=Activity)
def activity(item_id: int, source: str = ''):
    chosen = context.resolve(source)
    result = context.explorer(chosen)
    return jsonable_encoder(me.item_activity(chosen, result, item_id, datetime.now(UTC)))
