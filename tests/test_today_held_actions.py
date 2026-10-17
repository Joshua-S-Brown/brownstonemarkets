"""STORY-095: held actions explain their allocated purpose without changing the plan."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_today import catalog, output_catalog, plan
from test_today_holdings import evidence
from test_today_web import browser, request

from brownstone import today_holdings, today_session
from brownstone.today_settings import TodaySettings

browser = browser


@pytest.fixture
def named_maker(monkeypatch):
    from brownstone import today
    original = today._candidates
    def named(*args):
        rows, *rest = original(*args)
        for row in rows:
            row['made_by'] = 'Maker'
        return rows, *rest
    monkeypatch.setattr(today, '_candidates', named)


def second_catalog():
    result = output_catalog(4, 'second')
    result['items_by_id'][4]['name'] = 'Fixture 4'
    return result


def scenario():
    held = evidence((1, 1, 'Maker', 'bags'), (1, 1, 'Maker', 'bank'),
                    (1, 1, 'Other', 'bags'), (1, 1, 'Other', 'bank'))
    held[2].sort(key=lambda row: (row['character'], row['kind']))
    return plan(TodaySettings(1000, 1, 'fixed', max_crafts=1),
                catalogs=[catalog(), second_catalog()],
                observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 100}},
                holdings_data=held)


def projected(result):
    funds = SimpleNamespace(settings=TodaySettings(gold_override=True), origin='entered amount')
    queue = today_session.queue_with_gold(result, {}, funds)
    return queue, today_session.route_stops(queue, result['craft'], {})


def test_own_bags_note_and_byte_identical_plan(named_maker):
    result = scenario()
    before = json.loads((Path(__file__).parent / 'fixtures/today_story095_before.json').read_text())
    # Exact serialized build_today outputs, excluding only Queue lines (the changed presentation).
    def reserved(value):
        value = deepcopy(value)
        value['queue'].pop('lines')
        return json.dumps(value, sort_keys=True, default=str)
    assert reserved(result) == reserved(before)
    assert not any(line['stage'] == 'take' and line['kind'] == 'bags' for line in result['queue']['lines'])
    craft = next(line for line in result['queue']['lines'] if line['stage'] == 'craft')
    assert 'uses 1 Fixture 1 you hold' in today_session.queue_line_text(craft)
    old_tail = [line for line in before['queue']['lines'] if line['stage'] not in ('take', 'mail')]
    new_tail = [{k: v for k, v in line.items() if k != 'own_bags'}
                for line in result['queue']['lines'] if line['stage'] not in ('take', 'mail')]
    assert json.dumps(new_tail, sort_keys=True) == json.dumps(old_tail, sort_keys=True)
    old_state = today_session.queue_state(before['queue'], {'context': 'same'})
    old_state['ticks'] = {'0': True}
    changed = today_session.queue_state(projected(result)[0], old_state)
    assert not changed['ticks'] and changed['queue_identity'] != old_state['queue_identity']


def test_bank_self_and_other_take_then_mail_same_stop(named_maker):
    queue, stops = projected(scenario())
    bank = [s for s in stops if s['place'] == 'bank']
    assert [(s['character'], [line['evidence']['stage'] for line in s['lines']]) for s in bank] == [
        ('Maker', ['take']), ('Other', ['take', 'mail'])]
    text = [line['text'] for s in bank for line in s['lines']]
    assert text[0].startswith('Maker: take 1 Fixture 1 out of the bank, for Fixture 3 (step ')
    assert 'then mail them to Maker' in text[1]
    assert text[2].startswith('Other: mail 1 Fixture 1 to Maker, for Fixture 4 (step ')
    assert not any(line['stage'] == 'take' and line['kind'] == 'bags' for line in queue['lines'])


def test_shared_material_mail_purposes_and_first_stop(named_maker):
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1),
                  catalogs=[catalog(), second_catalog()],
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 100}},
                  holdings_data=evidence((1, 4, 'Other', 'bags')))
    queue, stops = projected(result)
    mails = [line for line in queue['lines'] if line['stage'] == 'mail']
    assert len(mails) == 1 and mails[0]['units'] == 4
    assert not any(line['stage'] == 'take' for line in queue['lines'])
    first = next(i for i, s in enumerate(stops, 1) if s['stage'] == 'craft')
    assert today_session.queue_line_text(mails[0]) == (
        f'Other: mail 4 Fixture 1 to Maker, for Fixture 3 and Fixture 4 (step {first})')
    old = {'queue_identity': today_session.digest({'queue': {'lines': []}, 'context': None}), 'ticks': {'0': True}}
    changed = today_session.queue_state(queue, old)
    assert changed['ticks'] == {} and changed['queue_identity'] != old['queue_identity']
    changed['ticks'] = {'0': True}
    assert today_session.queue_state(queue, changed)['ticks'] == {'0': True}


def test_copy_route_and_display_suffix_match(browser, monkeypatch):
    from test_today_characters import state
    monkeypatch.setattr('brownstone.professions.latest_data',
                        lambda config: {('Maker', 'realm', 'alliance'): state(learned=True)})
    monkeypatch.setattr('brownstone.today_loading._load_holdings',
                        lambda *a: (evidence((1, 2, 'Other', 'bags')), None))
    payload = request(browser).json()
    for stop in payload['stops']:
        for line in stop['lines']:
            assert line['text'] in payload['copy_text']
            assert line['display']['action_note'] == today_session.held_note(line['evidence'])
    mail = payload['stops'][0]['lines'][0]
    assert mail['text'].startswith('Other: mail 2 Fixture 1 to Maker, for Fixture 3 (step ')
    crafts = payload['plan']['craft']
    first = next(i for i, s in enumerate(payload['stops'], 1) if s['stage'] == 'craft')
    assert mail['evidence']['purpose_step'] == first
    assert crafts[0]['held_allocations'][0]['units'] == 2


def test_cross_profession_own_note_on_recipient_only():
    row = dict(material_names={1: 'Ore'}, held_allocations=[dict(
        kind='bags', character='Miner', to='Miner', item_id=1, units=2)])
    assert today_holdings.own_bags(row, 'Miner') == [{'units': 2, 'name': 'Ore'}]
    assert today_holdings.own_bags(row, 'Smith') == []


def test_unknown_crafter_keeps_bags_take():
    result = plan(TodaySettings(1000, 1, 'fixed', max_crafts=1),
                  catalogs=[catalog(), second_catalog()],
                  observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 100}},
                  holdings_data=evidence((1, 4, 'B', 'bags')))
    take = [line for line in result['queue']['lines'] if line['stage'] == 'take']
    assert [(t['character'], t['kind'], t['units']) for t in take] == [('B', 'bags', 4)]
    assert today_session.queue_line_text(take[0]) == 'B: take 4 Fixture 1 from the bags, for Fixture 3 and Fixture 4'
