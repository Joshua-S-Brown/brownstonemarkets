"""Session wording moved from the retired view to the API boundary."""
from test_today_web import browser as browser
from test_today_web import request


def test_step_text_every_kind(browser, monkeypatch):
    from views.today_rows import step_text
    tier = {'name': 'Journeyman', 'cap': 75, 'required_level': 10, 'level_ok': False}
    group = {'profession': 'Tailoring', 'rank': 8, 'capped': False}
    recipe = {'name': 'Brown Linen Pants', 'required_skill': 30, 'profit_copper': 187,
              'estimate': {'cost_copper': 989, 'cheap_cost_copper': 989}}
    character = {'character': ('Basilly', 'Realm', 'Alliance'), 'level': 6, 'craft_profit_copper': 12501,
                 'crafts': [{'batch_size': 3, 'output_name': 'White Linen Shirt'}]}
    steps = [
        {'kind': 'craft'}, {'kind': 'level_profession', 'group': group, 'recipe': recipe, 'more': 5},
        {'kind': 'level_character', 'group': group, 'tier': tier},
        {'kind': 'train', 'group': group | {'capped': True}, 'tier': tier | {'level_ok': True}},
        {'kind': 'nothing'}, {'kind': 'evidence'}]
    lines = [step_text(s, character, 25) for s in steps]
    assert lines[0] == 'Craft 3 White Linen Shirt · planned profit 1g 25s 1c'
    assert lines[1] == ('Level Tailoring 8 → 30 for 9s 89c, all on materials that are cheap right now · '
                        'unlocks Brown Linen Pants at 1s 87c per craft (+5 more on the way)')
    assert lines[2] == 'Before Tailoring reaches 75: level Basilly 6 → 10 to train Journeyman'
    assert lines[3] == 'Tailoring is capped at 75: train Journeyman Tailoring at a trainer'
    assert 'within 25 points' in lines[4] and 'Gathering is an option' in lines[4]
    assert 'open each profession window' in lines[5]
    capped = step_text({'kind': 'level_character', 'group': group | {'capped': True}, 'tier': tier},
                       character | {'level': None}, 25)
    assert capped == 'Tailoring is capped at 75: level Basilly to 10 (level unknown) to train Journeyman'
    partial = recipe | {'estimate': {'cost_copper': 989, 'cheap_cost_copper': 100}}
    assert '1s of it on cheap auction materials' in step_text(
        {'kind': 'level_profession', 'group': group, 'recipe': partial, 'more': 0}, character, 25)
    none = recipe | {'estimate': {'cost_copper': 989, 'cheap_cost_copper': 0}}
    assert 'no cheap auction materials' in step_text(
        {'kind': 'level_profession', 'group': group, 'recipe': none, 'more': 0}, character, 25)

    options = {'window': 25, 'characters': [character | {'next_steps': steps, 'professions': [],
                                                       'farming': {'spots': []}}]}
    monkeypatch.setattr('api.today.session_options.build_options', lambda *a, **k: options)
    response = request(browser, view='level-up')
    assert response.status_code == 200
    assert response.json()['session']['characters'][0]['options_text'] == lines
