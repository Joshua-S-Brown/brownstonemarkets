"""Read-only Team adapters over the shared character, progression and hiring projections."""
import threading
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from brownstone import character_snapshots, characters, hiring, recipe_catalogs, team_holdings, team_view, today_loading
from brownstone.crafting import basis_prices
from brownstone.ledger_view import day_bounds
from brownstone.today_settings import TodaySettings

from . import context, ledger, today
from .models import Evidence

router = APIRouter()
_lock = threading.Lock()
_cache: dict[tuple, tuple[tuple, dict]] = {}


class Facts(BaseModel):
    model_config = ConfigDict(extra='allow')


class Estimate(Facts):
    complete: bool
    cost_copper: int | None = None
    reasons: list[str] = []
    steps: list[dict[str, Any]] = []


class Payback(BaseModel):
    status: Literal['absent', 'unknown', 'never', 'crafts']
    crafts: int | None


class Recipe(Facts):
    name: str
    output_item_id: int
    required_skill: int | None
    points_needed: int
    profit_copper: int | None
    training_cost_copper: int | None = None
    estimate: Estimate
    learn_from: str
    payback: Payback


class Profession(Facts):
    profession: str
    rank: int | None
    max_rank: int | None
    note: str
    recipes: list[Recipe]
    best: Recipe | None
    alternative: Recipe | None
    alternative_kind: Literal['learn', 'hunt'] | None
    gathering: bool
    next_step: Literal['note', 'best', 'none']


class Progression(Facts):
    best_step: Profession | None = None
    professions: list[Profession]


class Skill(Facts):
    name: str
    rank: int | None
    max_rank: int | None
    at_cap: bool
    known_count: int | None
    recipe_source: str
    recipes_at: str
    possibly_incomplete: bool | None
    seen_at: str | None


class Card(Facts):
    name: str
    realm: str
    faction: str
    machine: str | None
    last_seen_relative: str
    last_seen_utc: str
    level: int | None
    gold_copper: int | None
    stale: bool
    skills_status: str
    known_recipes: int
    recipes_at_least: bool
    professions: list[Skill]
    history: list[dict[str, Any]]


class Holder(BaseModel):
    character: tuple[str, str, str]
    rank: int | None
    max_rank: int | None


class HireBest(Facts):
    output_name: str
    output_item_id: int
    profit_copper: int | None


class HireRow(BaseModel):
    profession: str
    holders: list[Holder]
    best: HireBest | None
    best_now: HireBest | None
    estimate: Estimate


class Member(BaseModel):
    character: tuple[str, str, str]
    card: Card
    progression: Progression
    free_slots: int | None
    suggestions: list[HireRow]
    suggestion_note: str


class ComparisonBest(Facts):
    estimate: Estimate | None = None
    name: str
    profit_copper: int | None


class ComparisonProfession(BaseModel):
    profession: str
    best: ComparisonBest | None


class Comparison(BaseModel):
    character: tuple[str, str, str]
    professions: list[ComparisonProfession]


class Team(BaseModel):
    roster: list[Member]
    hires: list[HireRow]
    no_catalog: list[str]
    comparisons: list[Comparison]
    all_incomplete: bool
    notes: list[str]
    evidence: Evidence
    labels: str
    hiring_labels: str


class Holdings(BaseModel):
    items: list[dict[str, Any]]
    captures: list[dict[str, Any]]
    value_copper: int = 0
    at_least: bool = True
    unpriced: int = 0


class CharacterRecord(Member):
    holdings: Holdings
    evidence: dict[str, Any]


class NextRequest(today.PlanRequest):
    character: tuple[str, str, str]
    window: int = Field(25, ge=5, le=100)


class CharacterStop(today.RouteStop):
    number: int


class CharacterNext(BaseModel):
    stops: list[CharacterStop]
    holdings: Holdings
    gold: dict[str, Any]


class HireDetail(Facts):
    profession: str
    needs_pattern: int
    unknown_source: int
    tiers: list[dict[str, Any]]


def build(chosen, window, now):
    data, warning = today_loading.load_today_characters(chosen)
    catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(context.ROOT / 'config'))
    cards = characters.build_characters(chosen, data=data, now=now)
    manifest, arguments = today_loading.load_today(chosen, catalogs, TodaySettings(), data, now)
    shared = team_view.team_board(catalogs, data, arguments)
    results = team_view.team_results(catalogs, data, arguments, window, shared)
    notes = errors + ([warning] if warning else [])
    hire_context, summaries = None, {'rows': [], 'no_catalog': [], 'comparisons': []}
    if arguments is not None:
        try:
            hire_context = hiring.prepare(catalogs=catalogs, character_data=data, shared=shared,
                                          **{k: arguments[k] for k in team_view.BOARD_KEYS})
            summaries = hiring.summaries(hire_context, window=window)
        except ValueError as error:
            notes.append(f'Unable to compare new hires: {error}')
    else:
        notes.append('No snapshot for this source and market. Import a current scan to compare new hires.')
    roster = []
    for card in cards:
        key = (card['name'], card['realm'], card['faction'])
        result = results.get(key, {'professions': []})
        roster.append(dict(character=key, card=card, progression=team_view.path_result(result),
                           **team_view.profession_suggestions(card, summaries['rows'])))
    payload = dict(roster=roster, hires=summaries['rows'], no_catalog=summaries['no_catalog'],
                   comparisons=summaries['comparisons'], all_incomplete=team_view.all_incomplete(summaries['rows']),
                   notes=notes, labels=team_view.HONESTY, hiring_labels=team_view.HIRING_LABELS,
                   evidence=context.evidence(chosen, arguments['snapshot'] if arguments else manifest or {}))
    return dict(payload=payload, hiring=hire_context, details={}, records={}, data=data, now=now)


def current(chosen):
    """Any build of this source in the current input generation; hire detail does not depend on the window."""
    stamp = context._inputs(chosen, datetime.now(UTC))
    return next((entry for (source, _), (seen, entry) in _cache.items()
                 if source == chosen['source_id'] and seen == stamp), None)


def cached(chosen, window):
    now = datetime.now(UTC)
    stamp = context._inputs(chosen, now)
    key = (chosen['source_id'], window)
    entry = _cache.get(key)
    if entry and entry[0] == stamp:
        return entry[1]
    try:
        result = build(chosen, window, now)
    except (OSError, ValueError, RuntimeError) as error:
        raise HTTPException(503, f'Unable to read Team evidence: {error}. Open Data or retry.') from error
    # Discard obsolete input generations, retaining windows in the current generation.
    for old in list(_cache):
        if old[0] == key[0] and _cache[old][0] != stamp:
            del _cache[old]
    _cache[key] = (stamp, result)
    return result


@router.get('/team', response_model=Team)
def team(source: str = '', window: int = Query(25, ge=5, le=100)):
    chosen = context.resolve(source)
    with _lock:
        return jsonable_encoder(cached(chosen, window)['payload'])


@router.get('/team/character', response_model=CharacterRecord)
def character(name: str, realm: str, faction: str, source: str = '', window: int = Query(25, ge=5, le=100)):
    chosen = context.resolve(source)
    key = (name, realm, faction)
    with _lock:
        entry = cached(chosen, window)
        member = next((r for r in entry['payload']['roster'] if r['character'] == key), None)
        if member is None:
            raise HTTPException(404, 'Character not in this source and market.')
        if key not in entry['records']:
            try:
                raw = character_snapshots.latest_data(chosen)
                _, names, captures, units = team_holdings.holdings({key: raw[key]} if key in raw else {},
                                                                   entry['now'])
            except (OSError, ValueError, RuntimeError) as error:
                raise HTTPException(503, f'Unable to read holdings: {error}. Open Data or retry.') from error
            items = [u | {'name': names.get(u['key'], f"Item {u['item_id']}"),
                          'variant_id': u['key'][1], 'variant_state': u['key'][2]} for u in units]
            state = entry['data'][key]
            evidence = dict(realm=realm, faction=faction, machine=member['card']['machine'],
                            snapshot_ids=sorted({r['snapshot_id'] for r, _ in state['observations']
                                                 if r.get('snapshot_id')}),
                            skills_status=member['card']['skills_status'], **dict(entry['payload']['evidence']))
            _, arguments = today_loading.load_today(chosen, [], TodaySettings(), {}, entry['now'],
                                                     item_ids={u['item_id'] for u in items})
            arguments = arguments or {}
            _, prices = basis_prices(arguments.get('observations', {}), 'cautious')
            held = team_view.character_holdings(items, captures, {}, [], prices, arguments.get('vendor_prices', {}))
            entry['records'][key] = member | dict(holdings=held, evidence=evidence)
        return jsonable_encoder(entry['records'][key])


@router.get('/team/hire/{profession}', response_model=HireDetail)
def hire(profession: str, source: str = ''):
    chosen = context.resolve(source)
    with _lock:
        entry = current(chosen) or cached(chosen, 25)
        row = next((r for r in entry['payload']['hires'] if r['profession'] == profession), None)
        if row is None:
            raise HTTPException(404, 'Profession unavailable for this market.')
        if profession not in entry['details']:
            entry['details'][profession] = hiring.detail(entry['hiring'], row)
        return jsonable_encoder(entry['details'][profession])


@router.post('/team/character/next', response_model=CharacterNext)
def character_next(body: NextRequest, source: str = ''):
    chosen = context.resolve(source)
    record = character(*body.character, source=source, window=body.window)
    try:
        payload = today.plan(body, source)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        payload = dict(plan={}, stops=[])
    held = record['holdings']
    prices = {r['item_id']: r['unit_copper'] for r in held['items'] if r['variant_state'] == 'base'}
    vendors = {r['item_id']: r['vendor_copper'] for r in held['items'] if r['variant_state'] == 'base'}
    held = team_view.character_holdings(held['items'], held['captures'], payload['plan'], payload['stops'],
                                        prices, vendors)
    with ledger._lock:
        gold = team_view.character_gold(ledger.cached(chosen).get('gold'), body.character,
                                        day_bounds('7', datetime.now(UTC)))
    return jsonable_encoder(dict(stops=[stop | {'number': number} for number, stop in enumerate(payload['stops'], 1)
                                        if list(body.character) in stop['characters']], holdings=held, gold=gold))
