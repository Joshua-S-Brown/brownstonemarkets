"""Read-only Team adapters over the shared character, progression and hiring projections."""
import threading
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_validator

from brownstone import (
    action_board,
    character_snapshots,
    characters,
    earnings,
    hiring,
    journal,
    market_explorer,
    recipe_catalogs,
    team_holdings,
    team_plan,
    team_view,
    today_loading,
)
from brownstone.crafting import basis_prices
from brownstone.ledger_view import day_bounds
from brownstone.today_settings import TodaySettings
from views.today_rows import reach_notes

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
    material_notes: list[str] = Field(default_factory=list, exclude_if=lambda notes: not notes)

    @model_validator(mode='before')
    @classmethod
    def label_materials(cls, value):
        return value | {'material_notes': reach_notes(value)} if isinstance(value, dict) else value


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


class Suggestion(HireRow):
    coverage: Literal['yours', 'uncovered', 'planned', 'held', 'suggested']
    planned_by: list[str]
    gathering: bool


class Member(BaseModel):
    character: tuple[str, str, str]
    card: Card
    progression: Progression
    free_slots: int | None
    suggestions: list[Suggestion]
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


class PlannedTier(BaseModel):
    cap: int
    estimate: Estimate
    best: HireBest | None


class PlannedProfession(BaseModel):
    profession: str
    tiers: list[PlannedTier]


class PlannedMember(BaseModel):
    name: str | None = None
    faction: str
    role: str
    professions: list[PlannedProfession]


class CapitalCharacter(BaseModel):
    character: tuple[str, str, str]
    gold_copper: int | None
    holdings_copper: int
    total_copper: int
    at_least: bool
    unpriced: int
    auctions: int | None


class Capital(BaseModel):
    gold_copper: int
    holdings_copper: int
    total_copper: int
    at_least: bool
    holdings_incomplete: bool
    missing_gold: int
    unpriced: int
    characters: list[CapitalCharacter]


class EarningsRow(BaseModel):
    label: str
    seconds: int
    world_seconds: int
    market_seconds: int
    world_copper: int
    market_copper: int
    loot_copper: int
    unpriced_units: int
    categories: dict[str, int]
    groups: dict[str, dict[str, int]]
    own_mail_copper: int
    quest_xp: int
    other_xp: int
    levels: int
    xp_label: str
    thin: bool
    world_per_hour_copper: int | None
    market_per_hour_copper: int | None
    loot_per_hour_copper: int | None
    xp_per_hour: int | None


class EarningsSession(EarningsRow):
    start: int
    end: int
    login_at: int | None
    machine: str | None
    bands: list[EarningsRow]


class CharacterEarnings(BaseModel):
    character: tuple[str, str, str]
    sessions: list[EarningsSession]
    total: EarningsRow
    bands: list[EarningsRow]


class Earnings(BaseModel):
    characters: list[CharacterEarnings]
    total: EarningsRow
    caveat: str
    excluded_money: int
    unknown_login_entries: int


class Team(BaseModel):
    capital: Capital
    earnings: Earnings
    roster: list[Member]
    planned: list[PlannedMember]
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
    catalog_professions: dict[int, str] = {}
    holdings: Holdings
    evidence: dict[str, Any]
    earnings: CharacterEarnings


class ProfessionHolder(Holder):
    known_count: int | None
    note: str


class ProfessionStatus(BaseModel):
    craft_status: str
    character_reason: str
    training_cost_copper: int | None


class ProfessionMaterial(BaseModel):
    item_id: int
    quantity: int
    name: str


class ProfessionRecipe(BaseModel):
    catalog_id: str
    recipe_id: int
    name: str
    output_item_id: int
    required_skill: int | None
    band: str
    range_text: str
    learn_from: str
    statuses: list[ProfessionStatus]
    profit_copper: int | None
    board_reason: str
    materials: list[ProfessionMaterial]


class ProfessionCatalog(BaseModel):
    catalog_id: str
    catalog_version: str
    coverage: str


class ProfessionRecord(BaseModel):
    profession: str
    holders: list[ProfessionHolder]
    rows: list[ProfessionRecipe]
    catalogs: list[ProfessionCatalog]
    evidence: Evidence


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


def _auctions(chosen):
    """Auction counts are display-only; an unreadable journal leaves every count unknown."""
    try:
        return journal.active_auction_rows(chosen), None
    except Exception as error:
        return [], f'Unable to read active auctions: {error}. Auction counts are unknown.'


def build(chosen, window, now):
    data, warning = today_loading.load_today_characters(chosen)
    catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(context.ROOT / 'config'))
    cards = characters.build_characters(chosen, data=data, now=now)
    held, holdings_warning = today_loading.load_holdings(chosen, now)
    held = held or ({}, {}, [], [])
    manifest, arguments = today_loading.load_today(chosen, catalogs, TodaySettings(), data, now,
        item_ids={u['item_id'] for u in held[3]} | earnings.item_ids(data), holdings_data=held)
    _, prices = basis_prices((arguments or {}).get('observations', {}), 'cautious')
    auctions, auctions_warning = _auctions(chosen)
    capital = team_view.capital(data, held, prices, (arguments or {}).get('vendor_prices', {}),
                               auctions, chosen['auction_cut'])
    shared = team_view.team_board(catalogs, data, arguments)
    results = team_view.team_results(catalogs, data, arguments, window, shared)
    notes = errors + [w for w in (warning, holdings_warning, auctions_warning) if w]
    hire_context, summaries = None, {'rows': [], 'no_catalog': [], 'comparisons': []}
    if arguments is not None:
        try:
            hire_context = hiring.prepare(catalogs=catalogs, character_data=data, shared=shared,
                                          **{k: arguments[k] for k in team_view.BOARD_KEYS})
            summaries = hiring.summaries(hire_context, window=window, results=results)
        except ValueError as error:
            notes.append(f'Unable to compare new hires: {error}')
    else:
        notes.append('No snapshot for this source and market. Import a current scan to compare new hires.')
    try:
        plan = team_plan.load(context.ROOT / 'config/team.local.toml')
    except (OSError, ValueError) as error:
        notes.append(f'Unable to read planned roster: {error}')
        plan = []
    coverage = team_view.team_coverage(cards, plan)
    roster = []
    for card in cards:
        key = (card['name'], card['realm'], card['faction'])
        result = results.get(key, {'professions': []})
        roster.append(dict(character=key, card=card, progression=team_view.path_result(result),
                           **team_view.profession_suggestions(card, summaries['rows'], coverage)))
    team_view.spread_suggestions(roster)
    planned = team_plan.roster(plan, cards, hire_context, summaries['rows'])
    measured = earnings.load(chosen, prices, (arguments or {}).get('vendor_prices', {}))
    payload = dict(capital=capital, earnings=measured, roster=roster, planned=planned, hires=summaries['rows'],
                   no_catalog=summaries['no_catalog'],
                   comparisons=summaries['comparisons'], all_incomplete=team_view.all_incomplete(summaries['rows']),
                   notes=notes, labels=team_view.HONESTY, hiring_labels=team_view.HIRING_LABELS,
                   evidence=context.evidence(chosen, arguments['snapshot'] if arguments else manifest or {}))
    return dict(payload=payload, hiring=hire_context, details={}, records={}, data=data, now=now,
                catalogs=action_board.compatible_catalogs(catalogs, chosen),
                board=shared[1] if shared else hire_context['board'] if hire_context else None, professions={})


def current(chosen):
    """Any build of this source in the current input generation; hire detail does not depend on the window."""
    stamp = context.inputs(chosen, datetime.now(UTC))
    return next((entry for (source, _), (seen, entry) in _cache.items()
                 if source == chosen['source_id'] and seen == stamp), None)


def cached(chosen, window):
    now = datetime.now(UTC)
    stamp = context.inputs(chosen, now)
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
            uses = {i: market_explorer.material_uses(context.explorer(chosen), i)
                    for i in {u['item_id'] for u in items if u['variant_state'] == 'base'}}
            held = team_view.character_holdings(items, captures, {}, [], prices, arguments.get('vendor_prices', {}),
                                                 chosen['auction_cut'], uses=uses)
            measured = earnings.character_record(entry['payload']['earnings'], key)
            entry['records'][key] = member | dict(holdings=held, evidence=evidence, earnings=measured,
                catalog_professions={hiring.SKILL_IDS[c['profession']]: c['profession'] for c in entry['catalogs']
                                     if c['profession'] in hiring.SKILL_IDS})
        return jsonable_encoder(entry['records'][key])


@router.get('/team/profession/{profession}', response_model=ProfessionRecord)
def profession(profession: str, source: str = ''):
    chosen = context.resolve(source)
    with _lock:
        entry = current(chosen) or cached(chosen, 25)
        if not any(c['profession'] == profession for c in entry['catalogs']):
            raise HTTPException(404, 'Profession unavailable for this market.')
        if profession not in entry['professions']:
            entry['professions'][profession] = team_view.profession_record(
                entry['catalogs'], entry['data'], entry['board'], profession) | {
                    'evidence': entry['payload']['evidence']}
        return jsonable_encoder(entry['professions'][profession])


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
    uses = {r['item_id']: market_explorer.material_uses(context.explorer(chosen), r['item_id'])
            for r in held['items'] if r['variant_state'] == 'base'}
    held = team_view.character_holdings(held['items'], held['captures'], payload['plan'], payload['stops'],
                                        prices, vendors, chosen['auction_cut'], uses=uses)
    with ledger._lock:
        gold = team_view.character_gold(ledger.cached(chosen).get('gold'), body.character,
                                        day_bounds('7', datetime.now(UTC)))
    return jsonable_encoder(dict(stops=[stop | {'number': number} for number, stop in enumerate(payload['stops'], 1)
                                        if list(body.character) in stop['characters']], holdings=held, gold=gold))
