"""Today adapters over shared loading, session merge and Queue projections."""
import json
import threading
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Literal

import duckdb
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from brownstone import recipe_catalogs, session_options, today_loading, today_session, today_settings
from brownstone.markets import MARKET_KEYS
from brownstone.money import parse_money
from brownstone.today import apply_removals
from brownstone.today_funds import recorded_balances, resolve_funds
from views import today_rows

from . import context

router = APIRouter()
_lock = threading.Lock()
_cache: dict[str, tuple[tuple, dict]] = {}
PRESENTATION = ('ticks', 'hide_low')


class PlanRequest(BaseModel):
    view: Literal['route', 'opportunities', 'level-up'] = 'route'
    state: dict[str, Any] = Field(default_factory=dict)


class RouteLine(BaseModel):
    index: int
    text: str
    evidence: dict[str, Any]
    warnings: str = ''


class RouteStop(BaseModel):
    stage: str
    character: str
    characters: list[tuple[str, str, str]]
    place: str
    lines: list[RouteLine]


class TodayPlan(BaseModel):
    plan: dict[str, Any]
    stops: list[RouteStop]
    state: dict[str, Any]
    reset_note: str
    empty_reason: str = ''
    evidence: dict[str, Any] = Field(default_factory=dict)
    copy_text: str
    funds_copper: int
    funds_label: str
    settings: dict[str, Any]
    characters: list[list[str]]
    notes: list[str]
    session: dict[str, Any] | None = None


class SettingsRequest(BaseModel):
    settings: dict[str, Any]


def read_settings(chosen):
    try:
        return today_settings.load_settings(today_settings.settings_path(chosen['data_dir'], chosen['source_id'])), []
    except (ValueError, TypeError, OSError) as error:
        return today_settings.TodaySettings(), [f'Unable to read Today settings: {error}; using defaults.']


def build(chosen, request, now):
    saved, notes = read_settings(chosen)
    characters, warning = today_loading.load_today_characters(chosen)
    funds = resolve_funds(saved, characters, now, chosen['max_age_hours'])
    catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(context.ROOT / 'config'))
    manifest, arguments = today_loading.load_today(chosen, catalogs, saved, characters, now, flood=True, holdings=True)
    if manifest is None:
        raise HTTPException(409, 'Refresh or import a scan for this market to inspect Today.')
    result, state, note = today_session.session_plan(arguments, request.state)
    apply_removals(result, today_loading.load_today_removals(chosen, result))
    queue = today_session.queue_with_gold(result, characters, funds)
    state = today_session.queue_state(queue, state)
    result = result | {'queue': queue}
    for row, sell in zip(result['craft'], result['sell'], strict=True):
        row.update(today_session.headline_profit(row, sell))
        row['warnings_text'] = today_rows.warning_text(row | sell)
    text = '\n'.join([queue['mail_note'], *map(today_session.queue_line, queue['lines']),
                      today_session.queue_total(queue)])
    payload = dict(plan=result, stops=today_session.route_stops(queue, result['craft'], characters),
                   state=state, reset_note=note,
                   empty_reason=today_rows.empty_sentence(result['hidden'], funds.settings.minimum_gain,
                                                          funds.settings.gold_copper) if not result['craft'] else '',
                   copy_text=text, funds_copper=funds.settings.gold_copper,
                   funds_label=(saved.character[0] if saved.character in characters else 'Our team')
                   + ' · ' + funds.origin,
                   evidence=plan_evidence(chosen, arguments, characters, funds),
                   settings=asdict(saved), characters=list(characters), notes=notes + list(funds.notes) + errors
                   + [today_rows.capture_label(c) for c in result.get('holdings_captures', [])])
    for stop in payload['stops']:
        for line in stop['lines']:
            line['warnings'] = today_rows.warning_text(line['evidence'])
    if warning:
        payload['notes'].append(warning)
    return json.loads(json.dumps(jsonable_encoder(payload))), arguments


def plan_evidence(chosen, arguments, characters, funds):
    balances = recorded_balances(characters)
    return {'market': {k: chosen.get(k) for k in (*MARKET_KEYS, 'market_id', 'source_id', 'rules_version')},
            'snapshot': {k: arguments['snapshot'].get(k) for k in
                         ('snapshot_id', 'scan_id', 'collected_at', 'updated_at')},
            'auction_cut': arguments['auction_cut'], 'max_age_hours': arguments['max_age_hours'],
            'funds_origin': funds.origin, 'recorded_gold': [
                {'character': list(c), 'gold_copper': balances.get(c),
                 'captured_at': data.get('bags', {}).get('captured_at')} for c, data in sorted(characters.items())]}


@router.post('/today/plan', response_model=TodayPlan)
def plan(request: PlanRequest, source: str = ''):
    chosen = context.resolve(source)
    try:
        return cached_plan(request, chosen)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(503, f'Unable to build Today: {error}. Open Data or retry.') from error


def cached_plan(request, chosen):
    now = datetime.now(UTC)
    path = today_settings.settings_path(chosen['data_dir'], chosen['source_id'])
    # Output state can be sent straight back without rebuilding the same reserved plan.
    key = (*context._inputs(chosen, now), context._stamp(path))
    with _lock:
        cached = _cache.get(chosen['source_id'])
        identity = plan_identity(request.state)
        if cached and cached[0] == key and identity in cached[1]['identities']:
            entry = cached[1]
        else:
            payload, arguments = build(chosen, request, now)
            entry = dict(payload=payload, arguments=arguments,
                         identities={identity, plan_identity(payload['state'])})
            _cache[chosen['source_id']] = (key, entry)
        if request.view == 'level-up' and 'session' not in entry['payload']:
            with duckdb.connect(str(chosen['data_dir'] / 'brownstone.duckdb'), read_only=True) as db:
                options = session_options.build_options(
                    db, chosen, entry['arguments'], entry['payload']['plan'], window=request.state.get('window', 25))
                entry['payload']['session'] = today_rows.session_display(options, entry['arguments'])
        payload = deepcopy(entry['payload'])
        payload['state'] |= presentation(request.state, payload['state'])
        if identity == plan_identity(payload['state']):
            payload['reset_note'] = ''
        if request.view != 'level-up':
            payload.pop('session', None)
        return jsonable_encoder(payload)


def plan_identity(state):
    """Ticks and Hide Low don't change the plan, so they don't force a rebuild."""
    return today_session.digest({k: v for k, v in state.items() if k not in PRESENTATION})


def presentation(requested, built):
    """The request's ticks survive while the Queue identity they were made against is unchanged."""
    if requested.get('context') != built.get('context'):
        return {}  # A reset clears session state, as session_plan does.
    kept = {k: requested[k] for k in PRESENTATION if k in requested}
    if requested.get('queue_identity') != built.get('queue_identity'):
        kept.pop('ticks', None)
    return kept


@router.post('/today/settings', response_model=dict[str, Any])
def settings(request: SettingsRequest, source: str = ''):
    chosen = context.resolve(source)
    try:
        values = dict(request.settings)
        for key in ('gold', 'minimum'):
            if key + '_text' in values:
                values[key + '_copper'] = parse_money(values.pop(key + '_text'))
        saved = today_settings.TodaySettings(**values)
        today_settings.save_settings(today_settings.settings_path(chosen['data_dir'], chosen['source_id']), saved)
    except (ValueError, TypeError) as error:
        raise HTTPException(400, str(error)) from error
    except OSError as error:
        raise HTTPException(409, f'Unable to save Today settings: {error}') from error
    return asdict(saved)
