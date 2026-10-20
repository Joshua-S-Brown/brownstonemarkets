"""Rule regressions moved from native Today/session/card tests to the web boundary."""
from copy import deepcopy
from unittest.mock import Mock

import pytest
from app_helpers import team_app
from test_today import plan
from test_today_web import TOKEN, arguments, browser, request

from brownstone import farming, sales, today_session
from views import today_rows

# Re-export the shared isolated API fixture.
browser = browser


def test_session_every_character_next_steps_bands_costs_and_rank(browser, tmp_path, monkeypatch):
    _, source, _ = browser
    _, c, data = team_app(tmp_path, monkeypatch)
    result = request(browser, view='level-up').json()
    assert len(result['session']['characters']) == 2
    for ch in result['session']['characters']:
        assert ch['options_text']
        assert ch['professions'][0]['rank'] in (8, 3)
        assert ch['professions'][0]['recipes'][0]['skillup_band']
        estimate = ch['professions'][0]['recipes'][0]['estimate']
        assert estimate['cost_copper'] is None and not estimate['complete']
        assert 'insufficient listings' in estimate['reasons'][0]
    craft_stops = [s for s in result['stops'] if s['stage'] == 'craft']
    assert all('rank unknown' not in s['place'] for s in craft_stops)
    assert result['plan']['today_version'] == 15


@pytest.mark.parametrize('named', [False, True])
def test_farming_top_three_rates_spots_names_links_coin_and_evidence(browser, tmp_path, monkeypatch, named):
    from test_farming import mob_loot, named_window
    _, _, data = team_app(tmp_path, monkeypatch)
    first = next(iter(data.values()))
    first['observations'] = mob_loot(0, 20, item=1) + mob_loot(150, 10, item=3) + mob_loot(300, 20, item=999)
    if named:
        first['observations'] += [named_window(400, 20), named_window(500, 10, 'Other mob')]
    result = request(browser, view='level-up').json()
    history = next(c['farming'] for c in result['session']['characters'] if c['farming']['spots'])
    spot = history['spots'][0]
    assert spot['npc_id'] == 20 and spot['seconds'] == 300 and spot['stretches'] == 1
    assert spot['mob'] == ('Kobold Tunneler (NPC 20)' if named else 'NPC 20')
    assert spot['coin_share'] == 'Coin unavailable'
    assert spot['no_price_items'] == spot['no_price_units'] == 1
    assert spot['also_looted'] == [10]
    assert len(history['rows']) == 3


def test_farming_position_coin_and_vendor_disagreement():
    from test_farming import positioned
    observations = positioned(0, x=.46, y=.71) + positioned(150, x=.48, y=.73) + positioned(300, x=.47, y=.72)
    # Preserve the projection's unknown coin wording and its position-centre rounding.
    history = farming.valued(farming.history(observations), {}, [], .05)
    spot = history['spots'][0]
    assert today_rows.spot_position(spot).startswith('around ')
    assert today_rows.spot_position(spot | {'cell': None}) == '—'
    assert today_rows.spot_coin_share(spot) == 'Coin unavailable'
    assert today_rows.spot_coin_share(spot | {'coin_copper': 20, 'value_copper': 100}) == 'Coin 20%'
    assert today_rows.spot_coin_share(spot | {'coin_copper': 0, 'value_copper': 0}) == 'Coin unknown'


def test_same_profit_reserved_materials_sales_and_vendor_evidence():
    from test_sales import invoice, posted
    from test_today import catalog
    data = sales.project([*posted(item=3, price=18), invoice(count=3, total=54, cut=2)], {3: {'Linen Cloth'}})
    result = plan(sales_data=data)
    sales_row = result['sell'][0]['your_sales']
    assert (sales_row['sold'], sales_row['resolved'], sales_row['average_copper']) == (3, 3, 17)
    c = catalog()
    c['items_by_id'][3]['vendor_price_copper'] = 124
    result = plan(catalogs=[c])
    assert today_rows.vendor_cap_label(result['sell'][0]) == 'capped at vendor price 1s 24c'
    for listings in (True, False):
        result = plan(**({} if listings else {'listings': None, 'metrics': None}))
        original = deepcopy(result)
        craft, sell = result['craft'][0], result['sell'][0]
        headline = today_session.headline_profit(craft, sell)
        assert headline['headline_per_craft_copper'] == headline['headline_profit_copper'] // craft['batch_size']
        assert bool(headline['profit_basis']) is not listings
        assert result == original


def test_cross_profession_queue_postorder_names_and_context_reset():
    from test_action_board import observed
    from test_recipe_graph import TAILOR, chain, evidence
    args = arguments(catalogs=chain(), observations=observed({1:5,2:100,3:1000,4:10000}))
    args.update(character_data=evidence(args['catalogs']))
    args['settings'] = __import__('brownstone.today_settings',fromlist=['TodaySettings']).TodaySettings(
        1000,1,'fixed',max_crafts=1,character=TAILOR)
    result, state, _ = today_session.session_plan(args, {})
    texts = [today_session.queue_line(line) for line in result['queue']['lines'] if line['stage'] == 'craft']
    assert 'Keenagen, Mining' in texts[0] and 'Armorer, Blacksmithing' in texts[1]
    assert 'Basilly, Tailoring' in texts[2]
    state['context'] = 'old'
    state['ticks'] = {'0': True}
    _, changed, note = today_session.session_plan(args,state)
    assert note and changed['choices'] is None and not changed['ticks']


@pytest.mark.parametrize('invalid', [{'gold_text':'12'}, {'max_crafts':1.5}, {'percent_basis_points':10001},
    {'post_duration_hours':12}, {'gold_copper':True}, {'include_unknown':1}])
def test_settings_refusal_keeps_file_and_plan(browser, invalid, monkeypatch):
    from api import today

    # This checks refusal, not freshness changes across an hourly cache rollover.
    fixed_now = today.datetime.now(today.UTC)
    monkeypatch.setattr(today, 'datetime', Mock(now=Mock(return_value=fixed_now)))
    original = request(browser).json()
    before = browser[2].read_bytes()
    response = browser[0].post('/api/today/settings', json={'settings': original['settings'] | invalid}, headers=TOKEN)
    assert response.status_code == 400
    assert browser[2].read_bytes() == before and request(browser).json()['plan'] == original['plan']


def test_settings_explicit_units_scaled_percent_and_source_isolation(browser, monkeypatch):
    source = browser[1]
    saved = request(browser).json()['settings'] | {'gold_text':'12g 50s','minimum_text':'10s',
        'percent_basis_points':250,'mode':'scaled','gold_override':True}
    response = browser[0].post('/api/today/settings',json={'settings':saved},headers=TOKEN)
    assert response.status_code == 200 and response.json()['gold_copper'] == 125000
    assert response.json()['minimum_copper'] == 1000
    monkeypatch.setattr('brownstone.config.read_sources',lambda *a:[source,source | {'source_id':'other'}])
    assert browser[0].post('/api/today/plan', json={}, headers=TOKEN).status_code == 409
    assert request((browser[0],source | {'source_id':'other'},browser[2])).status_code == 409


def test_refill_rows_choices_no_silent_resize_and_full_shopping():
    from test_today import output_catalog
    catalogs=[output_catalog(i,f'route-{i}') for i in range(3,14)]
    args=arguments(catalogs=catalogs,observations={1:{'min_buyout':10},**{i:{'min_buyout':2000} for i in range(3,14)}})
    result,state,_=today_session.session_plan(args,{})
    assert len(result['craft'])==10
    first=state['rows'][0]
    state['choices']=[{k:r[k] for k in ('catalog_id','recipe_id','batch_size')} for r in state['rows']]
    state['choices'][0]['batch_size']=None
    result,changed,_=today_session.session_plan(args,state)
    assert len(result['craft'])==10 and first['output_item_id'] not in [r['output_item_id'] for r in result['craft']]
    assert len(changed['choices'])==11
    result,_,_=today_session.session_plan(args,changed | {'refill':False})
    assert len(result['craft'])==10
    assert sum(r['cost_copper'] for r in result['buy'])==result['shopping_total_copper']


def test_session_lever_ranks_profit_cost_full_character_key_and_profession(monkeypatch):
    from test_session_options import arguments, compose

    from brownstone.session_options import next_steps

    args = arguments()
    options, _, _ = compose(monkeypatch, args)
    template = options['characters'][0]
    candidates = [
        (('Zed', 'Beta', 'Alliance'), 'Tailoring', 101, 100),
        (('Zed', 'Beta', 'Alliance'), 'Tailoring', 100, 1),
        (('Able', 'Alpha', 'Alliance'), 'Alchemy', 100, 10),
        (('Able', 'Alpha', 'Alliance'), 'Tailoring', 100, 10),
        (('Able', 'Alpha', 'Horde'), 'Alchemy', 100, 10),
        (('Able', 'Beta', 'Alliance'), 'Alchemy', 100, 10),
        (('Zed', 'Alpha', 'Alliance'), 'Alchemy', 100, 10),
    ]
    characters = []
    for key, profession, profit, cost in reversed(candidates):
        character = deepcopy(template)
        group = character['professions'][0]
        group['profession'] = profession
        group['best'].update(profit_copper=profit)
        group['best']['estimate'].update(cost_copper=cost)
        character.update(character=key, crafts=[])
        character['next_steps'] = next_steps(character)
        characters.append(character)
    options = options | {'characters': characters}
    original = deepcopy(options)
    for key, profession, profit, cost in candidates:
        display = today_rows.session_display(options, args)
        lever = display['lever']
        assert lever == dict(character=key, profession=profession,
                            reach=characters[-1]['professions'][0]['best']['required_skill'],
                            cost_copper=cost, profit_copper=profit,
                            text=display['characters'][-1]['options_text'][0])
        assert options == original
        characters.pop()
        original = deepcopy(options)
    assert today_rows.session_display(options, args)['lever'] is None
