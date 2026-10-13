"""Team roster and progression; per-tab controls, shared evidence and calculations."""
from contextlib import contextmanager
from datetime import UTC, datetime

from nicegui import app, ui

from brownstone.characters import build_characters
from brownstone.money import format_money
from brownstone.progression import build_progression
from brownstone.recipe_catalogs import learning_label
from brownstone.today_characters import available_characters
from brownstone.today_loading import load_today, load_today_characters
from brownstone.today_settings import TodaySettings
from views import nicegui_theme as theme
from views.nicegui_today import freshness_caption, table

HONESTY = ('Cost to reach is an estimate, with no credit for selling results. Current-scan profit, not a forecast; '
           'sales speed and demand unknown; beta prices; yellow skill-up chances are estimates.')


def money(value):
    return format_money(value) if value is not None else 'unknown'


def estimate_text(estimate):
    return money(estimate['cost_copper']) if estimate['complete'] else 'incomplete: ' + '; '.join(estimate['reasons'])


def next_step(group):
    if group['note']:
        return group['note']
    best = group['best']
    if best is None:
        return 'no valued recipe in reach'
    return f"{best['name']} · +{best['points_needed']} points · {estimate_text(best['estimate'])}"


def roster_card(card, progression, *, selected=False, on_select=None):
    with ui.card().classes('bs-person' + (' selected' if selected else '')).mark('team-character') as person:
        if on_select:
            person.on('click', on_select)
            person.on('keydown.enter', on_select)
            person.on('keydown.space', on_select)
            person.props('tabindex=0 role=button aria-label="Select ' + card['name'] + '" '
                         f'aria-pressed={str(selected).lower()}')
        ui.label(card['name']).classes('text-xl font-semibold')
        ui.label(card['last_seen_relative']).classes('bs-note')
        ui.label(f"Level {card['level'] if card['level'] is not None else 'unknown'} · "
                 f"Gold {money(card['gold_copper'])}")
        for row in card['professions']:
            ui.label(f"{row['name']} · {row['rank'] if row['rank'] is not None else 'unknown'} / "
                     f"{row['max_rank'] if row['max_rank'] is not None else 'unknown'}")
            ui.label(f"Known recipes: {row['known_count'] if row['known_count'] is not None else 'unknown'}").classes(
                'bs-note')
            if row['progress'] is not None:
                ui.linear_progress(row['progress'], show_value=False)
            if row['at_cap']:
                theme.badge('at cap: train the next tier', 'warn')
        if not card['professions']:
            ui.label('No profession reported yet.').classes('bs-note')
            ui.label("Next: learn a profession to see what's in reach").classes('bs-next')
        groups = progression['professions'] or [
            {'profession': r['name'], 'note': 'current scan unavailable', 'best': None} for r in card['professions']]
        for group in groups:
            ui.label(f"Next step · {group['profession']}: {next_step(group)}").classes('bs-next')


def character_evidence(card):
    with ui.expansion('Character evidence'):
        ui.label(f"{card['realm']} · {card['faction']} · {card['machine'] or 'machine unknown'}")
        ui.label(f"Last seen {card['last_seen_relative']} · {card['last_seen_utc']}")
        ui.label(f"Level {card['level'] if card['level'] is not None else 'unknown'} · "
                 f"Gold {money(card['gold_copper'])}")
        ui.label(('stale · ' if card['stale'] else '') + card['skills_status'])
        if card['bags_at'] is None:
            ui.label('No readable bags snapshot')
        for row in card['professions']:
            ui.label(f"{row['name']} · {row['rank'] if row['rank'] is not None else 'unknown'} / "
                     f"{row['max_rank'] if row['max_rank'] is not None else 'unknown'}")
            if row['progress'] is not None:
                ui.linear_progress(row['progress'], show_value=False)
            if row['at_cap']:
                ui.label('at cap: train the next tier')
            ui.label(f"Known recipes: {row['known_count'] if row['known_count'] is not None else 'unknown'} · "
                     f"{row['recipe_source']} · Window list: {row['recipes_at']}")
            if row['possibly_incomplete']:
                ui.label('possibly incomplete')
            if row['seen_at']:
                ui.label(f"Seen crafted: {row['seen_at']}")
    with ui.expansion('Progress over time'):
        if card['history']:
            series = sorted({r['Series'] for r in card['history']})
            ui.echart({'xAxis': {'type': 'time'}, 'yAxis': {'type': 'value'},
                       'legend': {'data': series}, 'tooltip': {'trigger': 'axis'},
                       'series': [{'name': name, 'type': 'line', 'data': [
                           [r['UTC'], r['Value']] for r in card['history'] if r['Series'] == name]}
                                  for name in series]}).classes('w-full h-64')
            table(card['history'], label='History')
        else:
            ui.label('No readable level or rank history yet.')

def summary_rows(result):
    return [{'Profession': g['profession'], 'Rank/max': f"{g['rank']} / {g['max_rank']}",
             'Best reachable recipe': g['best']['name'] if g['best'] else 'none valued',
             'Points needed': g['best']['points_needed'] if g['best'] else None,
             'Estimated cost': estimate_text(g['best']['estimate']) if g['best'] else g['note'] or 'unavailable',
             'Profit per craft': money(g['best']['profit_copper']) if g['best'] else 'unavailable',
             'Next step': next_step(g)} for g in result['professions']]


def progression_detail(result):
    for group in result['professions']:
        with ui.column().classes('w-full'):
            ui.label(group['profession']).classes('text-xl font-bold')
            best = group['best']
            if best:
                with ui.element('div').classes('bs-tiles'):
                    theme.tile('Best next recipe', best['name'], compact=True,
                               note=f"needs skill {best['required_skill']}")
                    theme.tile('Points to go', str(best['points_needed']))
                    theme.tile('Cost to get there', estimate_text(best['estimate']), note='estimate · no sales credit')
                    theme.tile('Then earns', money(best['profit_copper']), profit=True,
                               note="per craft at today's prices")
            table(reachable_rows(group), label='Reachable recipes')
            if group['note']:
                ui.label(group['note'])
            with ui.expansion('How to get there'):
                recipe_details(group)
    with ui.expansion('Profession comparison'):
        table(summary_rows(result), label='Profession summary')


def reachable_rows(group):
    return [{'Recipe': r['name'], 'Skill': r['required_skill'], 'Points': r['points_needed'],
             'Earns per craft': money(r['profit_copper']), 'Cost to reach': estimate_text(r['estimate']),
             'Status': learning_label(r), 'Confidence': r['confidence']} for r in group['recipes']]


def recipe_details(group):
    for recipe in group['recipes']:
        ui.label(f"{recipe['name']} · skill {recipe['required_skill']} · +{recipe['points_needed']} points · "
                 f"{recipe['craft_status']}"
                 + (' · needs pattern or other source' if recipe['needs_pattern'] else ''))
        if recipe['character_reason']:
            ui.label(recipe['character_reason'])
        ui.label(f"Profit per craft: {money(recipe['profit_copper'])} · {recipe['board_reason']} · "
                 f"{recipe['confidence']} confidence · {'; '.join(recipe['confidence_reasons'])}")
        training = (money(recipe.get('training_cost_copper'))
                    if recipe.get('training_cost_copper') else 'cost unknown')
        ui.label(f"Learning: {learning_label(recipe)} · Training: {training}")
        ui.label(f"Estimated cost: {estimate_text(recipe['estimate'])}")
        with ui.expansion('Cost steps'):
            table(recipe['estimate']['steps'], label='Cost steps')

def render(config, catalogs):
    data, warning = load_today_characters(config)
    if warning:
        ui.label(warning)
    try:
        cards = build_characters(config)
        manifest, arguments = load_today(config, catalogs, TodaySettings(), data, datetime.now(UTC))
    except Exception as error:
        ui.label(f'Unable to read Team evidence: {error}')
        return
    identities = available_characters(data)
    if not identities:
        theme.info_button('How these estimates work', lambda: team_info_unavailable(config, cards))
        ui.label('No characters imported for this source. Use Data → Import.')
        return
    session = app.storage.tab.setdefault('team-' + config['source_id'], {})
    selected = tuple(session.get('character', identities[0]))
    if selected not in identities:
        selected = identities[0]
    session.update(character=list(selected))
    window = session.setdefault('window', 25)
    roster = ui.column().classes('w-full gap-4')
    heading = ui.label('').classes('text-2xl font-bold')
    with ui.row().classes('items-center w-full'):
        choice = ui.select({str(i): ' · '.join(c) for i, c in enumerate(identities)},
                           value=str(identities.index(selected)), label='Progression character')
        slider = ui.slider(min=5, max=100, step=1, value=window).props(
            'label-always aria-label="Points within reach"').classes('w-56').mark('reach-window')
        ui.label('Look ahead · points within reach (5–100)').classes('bs-note')
        ui.label('Updates when you let go.').classes('bs-note')
    area = ui.column().classes('w-full')

    def update():
        with route_errors(area):
            session.update(character=list(identities[int(choice.value)]), window=int(slider.value))
            area.clear()
            results = team_results(catalogs, data, arguments, int(slider.value))
            roster.clear()
            heading.set_text(identities[int(choice.value)][0] + "'s next steps")
            with roster:
                with ui.row().classes('gap-3 items-center'):
                    theme.chip(f'{len(cards)} characters')
                    if cards:
                        theme.chip('Last seen ' + cards[0]['last_seen_relative'] +
                                   ' · ' + (cards[0]['machine'] or 'machine unknown'))
                    selected_result = results.get(identities[int(choice.value)])
                    if selected_result and selected_result['freshness']:
                        freshness_caption(selected_result['freshness'], config, banner=False)
                with ui.element('div').classes('bs-roster'):
                    for card in cards:
                        key = (card['name'], card['realm'], card['faction'])
                        roster_card(card, results.get(key, {'professions': []}),
                                    selected=key == identities[int(choice.value)],
                                    on_select=lambda e, k=key: choice.set_value(str(identities.index(k))))
            with area:
                if manifest is None:
                    ui.label('No snapshot for this source and market. Import a scan to estimate progression.')
                else:
                    result = results[identities[int(choice.value)]]
                    info[0] = lambda: estimates_info(result, config, arguments, cards)
                    route_warnings(result)
                    progression_detail(result)

    info = [lambda: team_info_unavailable(config, cards)]
    theme.info_button('How these estimates work', lambda: info[0]())
    choice.on_value_change(lambda e: update())
    slider.on('change', lambda e: update())
    update()


def team_results(catalogs, data, arguments, window):
    if arguments is None:
        return {}
    keys = ('observations', 'market', 'snapshot', 'now', 'max_age_hours', 'auction_cut', 'listings', 'metrics')
    return {c: build_progression(catalogs=catalogs, character_data=data, character=c, window=window,
                                **{key: arguments[key] for key in keys}) for c in available_characters(data)}


def estimates_info(result, config, arguments, cards):
    with theme.dialog('How these estimates work') as popup:
        ui.label(f"Snapshot {arguments['snapshot']['snapshot_id']} · source {config['source_id']} · "
                 f"market {config['market_id']}")
        observed = f"{result['freshness']['observed_at']} UTC" if result['freshness'] else 'scan time unknown'
        ui.label(f"Scan {arguments['snapshot'].get('scan_id', 'not available for this source')} · {observed} · "
                 f"rules {config.get('rules_version', 'not configured')}")
        ui.label(HONESTY)
        for card in cards:
            with ui.expansion(card['name'] + ' evidence'):
                character_evidence(card)
        ui.label('Cost to reach: cheapest usable skill-up craft per point; training paid once; no credit for selling.')
        for identity, count in result['unlisted'].items():
            ui.label(f"{identity}: {count} not in a recipe list: open that profession's window")
    popup.on('hide', popup.delete)
    popup.open()


def team_info_unavailable(config, cards):
    with theme.dialog('How these estimates work') as popup:
        ui.label(f"source {config['source_id']} · market {config['market_id']}")
        ui.label(HONESTY)
        ui.label('Import character and scan evidence to estimate progression.')
        for card in cards:
            with ui.expansion(card['name'] + ' evidence'):
                character_evidence(card)
    popup.on('hide', popup.delete)
    popup.open()


@contextmanager
def route_errors(area):
    try:
        yield
    except ValueError as error:
        with area:
            ui.label(f"Unable to build Team routes: {error}")


def route_warnings(result):
    for warning in result.get("catalog_warnings", []):
        ui.label(warning).classes("bs-note")
