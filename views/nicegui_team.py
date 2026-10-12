"""Team roster and progression; per-tab controls, shared evidence and calculations."""
from datetime import UTC, datetime

from nicegui import app, ui

from brownstone.characters import build_characters
from brownstone.money import format_money
from brownstone.progression import build_progression
from brownstone.recipe_catalogs import learning_label
from brownstone.today_characters import available_characters
from brownstone.today_loading import load_today, load_today_characters
from brownstone.today_settings import TodaySettings
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


def roster_card(card, progression):
    with ui.card().classes('w-full md:w-[48%]').mark('team-character'):
        ui.label(card['name']).classes('text-xl font-semibold')
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
        groups = progression['professions'] or [
            {'profession': r['name'], 'note': 'current scan unavailable', 'best': None} for r in card['professions']]
        for group in groups:
            ui.label(f"Next step · {group['profession']}: {next_step(group)}")
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
    table(summary_rows(result), label='Profession summary')
    for identity, count in result['unlisted'].items():
        ui.label(f'{identity}: {count} not in a recipe list: open that profession\'s window')
    for group in result['professions']:
        with ui.expansion(group['profession'], value=True).classes('w-full'):
            if group['note']:
                ui.label(group['note'])
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
        ui.label('No characters imported for this source. Use Data → Import.')
        return
    session = app.storage.tab.setdefault('team-' + config['source_id'], {})
    selected = tuple(session.get('character', identities[0]))
    if selected not in identities:
        selected = identities[0]
    session.update(character=list(selected))
    window = session.setdefault('window', 25)
    with ui.row():
        choice = ui.select({str(i): ' · '.join(c) for i, c in enumerate(identities)},
                           value=str(identities.index(selected)), label='Progression character')
        slider = ui.slider(min=5, max=100, step=1, value=window).props('label-always').mark('reach-window')
        ui.label('Points within reach (5–100)')
    area = ui.column().classes('w-full')

    def update():
        session.update(character=list(identities[int(choice.value)]), window=int(slider.value))
        area.clear()
        with area:
            results = team_results(catalogs, data, arguments, int(slider.value))
            ui.label('Who can do what · imported character evidence')
            with ui.row().classes('w-full items-start'):
                for card in cards:
                    key = (card['name'], card['realm'], card['faction'])
                    roster_card(card, results.get(key, {'professions': []}))
            ui.label('Progression').classes('text-h5')
            ui.label(HONESTY)
            if manifest is None:
                ui.label('No snapshot for this source and market. Import a scan to estimate progression.')
            else:
                result = results[identities[int(choice.value)]]
                ui.label(f"Snapshot {arguments['snapshot']['snapshot_id']} · source {config['source_id']} · "
                         f"market {config['market_id']}")
                if result['freshness']:
                    freshness_caption(result['freshness'], config)
                progression_detail(result)

    choice.on_value_change(lambda e: update())
    slider.on_value_change(lambda e: update())
    update()


def team_results(catalogs, data, arguments, window):
    if arguments is None:
        return {}
    keys = ('observations', 'market', 'snapshot', 'now', 'max_age_hours', 'auction_cut', 'listings', 'metrics')
    return {c: build_progression(catalogs=catalogs, character_data=data, character=c, window=window,
                                **{key: arguments[key] for key in keys}) for c in available_characters(data)}
