"""Pure Team projections shared by the web adapters and the native migration view."""
from datetime import UTC, datetime

from . import action_board, hiring, progression, recipe_catalogs, skillups, today_characters
from .money import after_cut, format_money
from .today_characters import available_characters
from .today_funds import recorded_balances

BOARD_KEYS = ('observations', 'market', 'snapshot', 'now', 'max_age_hours', 'auction_cut')
HONESTY = ('Cost to reach is an estimate, with no credit for selling results. Current-scan profit, not a forecast; '
           'sales speed and demand unknown; beta prices; yellow skill-up chances are estimates.')
HIRING_LABELS = ('Current-scan prices are not a forecast; listings never sales; sales speed and demand unknown; '
                 'beta prices; estimated yellow chances unconfirmed on Forever. '
                 'Forever tier levels use trainer lists where known, otherwise Classic assumptions. '
                 'Costs give no credit for selling results. No gathering income. Tier fees not included (unknown).')


def training_payback(recipe):
    """Return a status and integer craft count, leaving wording to the view."""
    training, profit = recipe.get('training_cost_copper'), recipe.get('profit_copper')
    if not training:
        return {'status': 'absent', 'crafts': None}
    if profit is None:
        return {'status': 'unknown', 'crafts': None}
    if profit <= 0:
        return {'status': 'never', 'crafts': None}
    return {'status': 'crafts', 'crafts': (training + profit - 1) // profit}


def next_step(group):
    return {'kind': 'note' if group['note'] else 'best' if group['best'] else 'none',
            'note': group['note'], 'best': group['best']}


def alternative_kind(recipe):
    return None if recipe is None else 'learn' if progression.learnable(recipe) else 'hunt'


def gathering(group):
    return group.get('skill_id') in {hiring.SKILL_IDS[n] for n in ('mining', 'herbalism', 'skinning', 'fishing')}


def all_incomplete(rows):
    return bool(rows) and all(not row['estimate']['complete'] for row in rows)


def team_board(catalogs, data, arguments):
    if arguments is None or not data:
        return None
    try:
        return progression.team_board(catalogs, character_data=data, **{k: arguments[k] for k in BOARD_KEYS})
    except ValueError:
        return None


def team_results(catalogs, data, arguments, window, shared=None):
    if arguments is None:
        return {}
    graph, board = shared or (None, None)
    supplies = progression.reach_supplies(arguments.get('holdings_data'), data, arguments['listings'],
                                         arguments['now'], arguments['max_age_hours'], arguments['auction_cut'],
                                         arguments['market'].get('farming_idle_minutes', 10),
                                         arguments['market'].get('farming_cell_percent', 5))
    return {c: progression.build_progression(
        catalogs=catalogs, character_data=data, character=c, window=window, recipe_graph=graph, board=board,
        supplies=supplies,
        **{key: arguments[key] for key in (*BOARD_KEYS, 'listings', 'metrics')}) for c in available_characters(data)}


def roster_step(groups):
    """Best profession action in CRAFT-11 comparison order; keep every step in the record."""
    return min(groups, key=progression.summary_sort, default=None)


GATHERING = ('mining', 'herbalism', 'skinning')
GATHERING_NOTE = "gathering: income not modelled; supplies the team's crafts"
COVERED_NOTE = 'every priced profession is held, planned or suggested for another character'
COVERAGE_ORDER = {'yours': 0, 'uncovered': 1, 'planned': 2, 'held': 2, 'suggested': 2}  # Covered: hire order.


def team_coverage(cards, plan):
    """Who holds (captured skill IDs) and who plans (personal roster) each profession; never names."""
    names = {skill: name for name, skill in hiring.SKILL_IDS.items()}
    held: dict[str, list] = {}
    for card in cards:
        for row in card['professions']:
            if row.get('skill_id') in names:
                held.setdefault(names[row['skill_id']], []).append(
                    {'character': (card['name'], card['realm'], card['faction']),
                     'rank': row['rank'], 'max_rank': row['max_rank']})
    planned: dict[str, list] = {}
    for entry in plan:
        for skill in entry['professions']:
            planned.setdefault(names[skill], []).append(entry)
    return held, planned


def _coverage(name, card, held, planned):
    own = (card['name'].casefold(), card['faction'].lower())
    entries = planned.get(name, [])
    if any(e.get('name') and (e['name'].casefold(), e['faction']) == own for e in entries):
        return 'yours', []
    others = [e.get('name') or e['role'] for e in entries]
    return ('held' if held.get(name) else 'planned' if others else 'uncovered'), others


def profession_suggestions(card, rows, coverage=({}, {})):
    """Order the shared hire rows for one character's free primary slots: their own plan, then professions
    nobody holds or plans, then covered ones in hire order; gathering follows, labelled, never ranked by profit."""
    if card['skills_status'] != 'observed':
        return dict(free_slots=None, suggestions=[], suggestion_note='professions unknown')
    own = {p['skill_id'] for p in card['professions'] if p.get('skill_id') is not None}
    slots = max(0, 2 - len(own & (set(hiring.SKILL_IDS.values()) - hiring.SECONDARY)))
    if not slots:
        return dict(free_slots=0, suggestions=[], suggestion_note='')
    held, planned = coverage
    by_name = {r['profession']: r for r in rows}
    gathering = [by_name.get(name) or dict(profession=name, holders=held.get(name, []), best=None, best_now=None,
                                          estimate=dict(complete=False, cost_copper=None, reasons=[GATHERING_NOTE]))
                 for name in GATHERING]
    options = [r for r in rows if r['profession'] not in GATHERING] + gathering
    annotated = []
    for row in options:
        if hiring.SKILL_IDS.get(row['profession']) in own | hiring.SECONDARY:
            continue
        kind, planned_by = _coverage(row['profession'], card, held, planned)
        annotated.append(row | {'coverage': kind, 'planned_by': planned_by,
                                'gathering': row['profession'] in GATHERING})
    order = sorted(annotated, key=_suggestion_order)
    crafting = [r for r in order if not r['gathering']]
    if not any(r['best'] and r['best']['profit_copper'] > 0 for r in crafting):
        return dict(free_slots=slots, suggestions=[r for r in order if r['gathering']],
                    suggestion_note='no profession has a priced recipe at 300')
    return dict(free_slots=slots, suggestions=order, suggestion_note='')


def _suggestion_order(row):
    return row['gathering'], COVERAGE_ORDER[row['coverage']], hiring.summary_sort(row)


def spread_suggestions(members, shown=3):
    """Characters with free slots, in roster order, get different top picks while an uncovered priced
    profession remains; a pick reads *suggested for* on later cards. Each keeps ``shown`` crafting options
    plus the gathering ones."""
    taken: dict[str, str] = {}
    for member in members:
        options = sorted((r | {'coverage': 'suggested', 'planned_by': [taken[r['profession']]]}
                          if r['coverage'] == 'uncovered' and r['profession'] in taken else r
                          for r in member['suggestions']), key=_suggestion_order)
        priced = [r for r in options if not r['gathering'] and r['best'] and r['best']['profit_copper'] > 0]
        pick = next((r for r in priced if r['coverage'] in ('yours', 'uncovered')), None)
        if pick:
            taken.setdefault(pick['profession'], member['character'][0])
            options = [pick] + [r for r in options if r is not pick]
        elif priced:
            member['suggestion_note'] = COVERED_NOTE
        crafting = [r for r in options if not r['gathering']][:shown]
        member['suggestions'] = crafting + [r for r in options if r['gathering']]
    return members


def path_result(result):
    """Annotate computed decisions, retaining all original calculation evidence."""
    groups = []
    for group in result['professions']:
        def recipe(row):
            return row | {'learn_from': recipe_catalogs.learning_label(row), 'payback': training_payback(row)}
        groups.append(group | {'recipes': [recipe(r) for r in group['recipes']],
                               'best': recipe(group['best']) if group['best'] else None,
                               'alternative': recipe(group['alternative']) if group.get('alternative') else None,
                               'alternative_kind': alternative_kind(group.get('alternative')),
                               'gathering': gathering(group), 'next_step': next_step(group)['kind']})
    return result | {'professions': groups, 'best_step': roster_step(groups)}


def profession_record(catalogs, data, board, profession):
    """Every catalog recipe and exact-skill holder, without new estimates or reach walks."""
    catalogs = [c for c in catalogs if c['profession'] == profession]
    skill_id, holders = hiring.SKILL_IDS.get(profession), []
    for character in sorted(data) if skill_id is not None else []:
        groups, _ = progression._groups([], data[character])
        group = next((g for g in groups.values() if g['skill_id'] == skill_id), None)
        if group is None:
            continue
        listed = any(today_characters._skill_id(r['known_recipes']) == group['skill_id']
                     for r in data[character]['recipes'].values())
        holders.append(dict(character=character, rank=group['rank'], max_rank=group['max_rank'],
                            known_count=0 if listed else None,
                            note='' if listed else 'Recipes unknown; open the profession window.'))
    ranked = {(r['catalog_id'], r['recipe_id']): r for r in board['rows']} if board else {}
    rows = []
    for catalog in catalogs:
        for recipe in catalog['recipes_by_id'].values():
            required = recipe.get('required_skill')
            statuses = [today_characters.recipe_status(recipe, data[h['character']]) if not h['note'] else
                        dict(craft_status='Unknown', character_reason='recipe not listed', training_cost_copper=None)
                        for h in holders]
            row = ranked.get((action_board.catalog_identity(catalog), recipe['recipe_id']), {})
            rows.append(dict(catalog_id=action_board.catalog_identity(catalog), recipe_id=recipe['recipe_id'],
                             name=recipe['name'], output_item_id=recipe['output_item_id'], required_skill=required,
                             band=skillups.band_label(required // 25 * 25) if required is not None else 'skill unknown',
                             range_text=skillups.recipe_placement(recipe)[1],
                             learn_from=recipe_catalogs.learning_label(recipe), statuses=statuses,
                             profit_copper=row.get('profit_copper'),
                             board_reason=row.get('action', 'intermediate: not ranked by the Action Board') if board
                             else 'No snapshot for this source and market.',
                             materials=[i | {'name': catalog['items_by_id'][i['item_id']]['name']}
                                        for i in recipe['inputs']]))
    for index, holder in enumerate(holders):
        if holder['known_count'] is not None:
            holder['known_count'] = sum(r['statuses'][index]['craft_status'] == 'Known' for r in rows)
    return dict(profession=profession, holders=holders,
                rows=sorted(rows, key=lambda r: (r['required_skill'] is None, r['required_skill'] or 0,
                                                r['name'], r['catalog_id'], r['recipe_id'])),
                catalogs=[dict(catalog_id=action_board.catalog_identity(c), catalog_version=c['catalog_version'],
                               coverage=skillups.coverage_line(c)) for c in catalogs])


def character_holdings(items, captures, plan, stops, prices, vendor_prices, auction_cut=.05, uses=None):
    """Value exact held identities like Stock and suggest only evidenced Route uses."""
    rows = []
    for item in items:
        base = item['variant_state'] == 'base'
        price = prices.get(item['item_id']) if base else None
        vendor = vendor_prices.get(item['item_id']) if base else None
        vendor = vendor if vendor is not None and vendor > 0 else None
        own, mail = None, None
        for number, stop in enumerate(stops, 1):
            for line in stop['lines']:
                evidence = line['evidence']
                if any(_same_stack(a, item) for a in evidence.get('held_outputs', [])):
                    own = f'used in tonight’s plan (Route step {number})'
                if evidence.get('stage') == 'mail' and _same_stack(evidence, item):
                    mail = f"mail to {evidence['to']} for " + ' and '.join(p['name'] for p in evidence['purposes'])
                    mail += f' (Route step {number})'
            for craft in plan.get('craft', []):
                if not any(line['evidence'].get('recipe_id') == craft['recipe_id'] and
                           line['evidence'].get('catalog_id') == craft['catalog_id'] for line in stop['lines']):
                    continue
                if any(_same_stack(a, item) and a.get('to') in (None, item['character'])
                       for a in craft.get('held_allocations', [])):
                    own = f'used in tonight’s plan (Route step {number})'
        # Tonight's Route use or mail outranks a best-use suggestion.
        action = own or mail or _best_use((uses or {}).get(item['item_id'], [])) if base else None
        if not action:
            sells = price is not None and vendor is not None and after_cut(price, 1, auction_cut) > vendor
            action = 'sell' if sells else (
                ('vendor it instead' if price is not None else 'vendor') if vendor else 'keep')
        rows.append(item | dict(vendor_copper=vendor, unit_copper=price,
                                value_copper=price * item['units'] if price is not None else None,
                                action=action))
    return dict(items=rows, captures=captures, value_copper=sum(r['value_copper'] or 0 for r in rows),
                at_least=not captures or any(c['unknown'] or c['partial'] for c in captures),
                unpriced=sum(r['unit_copper'] is None for r in rows))


def _best_use(options):
    """UI-09's best known per-unit option when it is a team-makeable craft; selling or vendoring keeps STORY-104."""
    best = next((o for o in options if o['eligible'] and o['value_copper'] is not None), None)
    if best is None or best['action'] in ('sell', 'vendor'):
        return None
    delta = best['over_selling_copper']
    gain = f' · +{format_money(delta)} a unit over selling' if delta is not None and delta > 0 else ''
    return best['action'] + gain


def _same_stack(unit, item):
    """Exact ADDON-08 identity in the same owner's bags or bank; item ID alone never matches."""
    return (unit.get('key') is not None and tuple(unit['key']) == tuple(item['key']) and
            all(unit.get(field) == item[field] for field in ('character', 'realm', 'faction', 'kind')))


def character_gold(data, character, bounds):
    """Filter the ledger's existing UTC day/category totals; a character the ledger never saw stays unknown."""
    seen = [r for r in (data or {}).get('totals', []) if tuple(r['character']) == character]
    if not seen:
        return dict(in_copper=None, out_copper=None, net_copper=None, categories=[])
    rows = [r for r in seen
            if bounds[0] <= int(datetime.fromisoformat(r['day']).replace(tzinfo=UTC).timestamp()) < bounds[1]]
    categories = {}
    for row in rows:
        target = categories.setdefault(row['category'], dict(category=row['category'], in_copper=0, out_copper=0))
        for key in ('in_copper', 'out_copper'):
            target[key] += row[key]
    incoming, outgoing = (sum(r[k] for r in rows) for k in ('in_copper', 'out_copper'))
    return dict(in_copper=incoming, out_copper=outgoing, net_copper=incoming - outgoing,
                categories=sorted(categories.values(), key=lambda r: (-(r['in_copper'] + r['out_copper']),
                                                                      r['category']))[:3])


def capital(data, holdings_data, prices, vendor_prices, auctions, auction_cut):
    """Company value from scoped captured gold and cautious base-stack holdings."""
    _, _, captures, units = holdings_data
    balances = recorded_balances(data)
    incomplete = False
    auction_counts = {(r['Character'], r['Realm'], r['Faction']): r['Auctions'] for r in auctions}
    rows = []
    for key in sorted(data):
        items = [u | {'variant_state': u['key'][2]} for u in units
                 if (u['character'], u['realm'], u['faction']) == key]
        held = character_holdings(items, [c for c in captures
                                  if (c['character'], c['realm'], c['faction']) == key],
                                  {}, [], prices, vendor_prices, auction_cut)
        incomplete |= held['at_least']
        gold = balances.get(key)
        rows.append(dict(character=key, gold_copper=gold, holdings_copper=held['value_copper'],
                         total_copper=(gold or 0) + held['value_copper'], unpriced=held['unpriced'],
                         at_least=gold is None or held['at_least'] or bool(held['unpriced']),
                         auctions=auction_counts.get(key)))
    gold = sum(balances.values())
    value = sum(r['holdings_copper'] for r in rows)
    return dict(gold_copper=gold, holdings_copper=value, total_copper=gold + value,
                at_least=any(r['at_least'] for r in rows), holdings_incomplete=incomplete,
                missing_gold=len(data) - len(balances),
                unpriced=sum(r['unpriced'] for r in rows), characters=rows)
