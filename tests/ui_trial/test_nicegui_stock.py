"""Offline Stock page navigation, cached controls, draft edits and evidence."""
import pytest
from nicegui import ui
from test_stock import fixture

from brownstone import stock

pytestmark = pytest.mark.asyncio


def stock_app(tmp_path, monkeypatch):
    config = fixture(tmp_path)
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config])
    monkeypatch.setattr('brownstone.recipe_catalogs.parse_catalogs', lambda *args: ([], []))
    return config


async def test_stock_navigation_cached_search_chains_info_and_drafts(user, tmp_path, monkeypatch):
    config = stock_app(tmp_path, monkeypatch)
    path = stock.targets_path(config['data_dir'], config['source_id'])
    stock.save_entries(path, [stock.Entry(2589, 20, buy_copper=30)])
    count = []
    original = stock.load_stock
    def load(*args):
        count.append(1)
        return original(*args)
    monkeypatch.setattr(stock, 'load_stock', load)
    await user.open('/?place=Stock')
    await user.should_see('What do we hold, and what should we restock?')
    await user.should_see('Cara · bank unknown')
    await user.should_see('unreadable capture(s) excluded')
    await user.should_see('Stale')
    widget = next(iter(user.find(marker='stock-table').elements))
    assert widget.rows[0]['Short'] == 'at most 9'
    user.find(marker='stock-search').type('not found')
    assert widget.rows == []
    user.find(marker='stock-search').clear().type('2589')
    assert len(widget.rows) == 1
    user.find(marker='stock-chains').click()
    assert widget.rows == [] and len(count) == 1
    user.find(marker='page-info').click()
    await user.should_see('Stock evidence')
    await user.should_see('Cautious value')
    user.find('Close').click()
    user.find(marker='stock-targets').click()
    user.find(marker='stock-item-id').type('2589')
    user.find(marker='stock-units').type('bad')
    user.find(marker='stock-draft').click()
    await user.should_see('Draft rejected')
    user.find(marker='stock-units').clear().type('30')
    user.find(marker='stock-draft').click()
    await user.should_see('Draft updated; Save to keep it.')
    assert stock.load_entries(path)[0].target_units == 20
    user.find('Close').click()
    await user.open('/?place=Stock')
    await user.should_see('What needs restocking')
    user.find(marker='stock-targets').click()
    await user.should_see('Linen Cloth (2589): 20 units')  # known names shown beside the ID
    user.find(marker='stock-item-id').type('2589')
    user.find(marker='stock-units').type('30')
    user.find(marker='stock-draft').click()
    user.find(marker='stock-save').click()
    assert stock.load_entries(path) == [stock.Entry(2589, 30)]
    await user.open('/?place=Stock')
    await user.should_see('What needs restocking')
    widget = next(iter(user.find(marker='stock-table').elements))
    assert widget.rows[0]['Target'] == 30


async def test_empty_error_missing_limits_and_rejected_save(user, tmp_path, monkeypatch):
    config = stock_app(tmp_path, monkeypatch)
    path = stock.targets_path(config['data_dir'], config['source_id'])
    stock.save_entries(path, [stock.Entry(9999, 10, buy_percent=80)])
    await user.open('/?place=Stock')
    await user.should_see('Market value missing · buy limit unknown · wait')
    await user.should_see('Unlisted units have no fill price')
    widget = next(iter(user.find(marker='stock-table').elements))
    assert widget.rows[0]['item_id'] == 9999  # Short target comes before held Linen Cloth.
    assert widget.rows[0]['Unlisted units'] == 10
    assert widget.rows[0]['Fill cost'] == 'insufficient listings'
    user.find(marker='stock-targets').click()
    user.find('Remove target from draft').click()
    await user.should_see('Enter an item ID to remove')
    user.find(marker='stock-item-id').type('9999')
    user.find('Remove target from draft').click()
    path.write_text('{}')
    user.find(marker='stock-save').click()
    await user.should_see('Save rejected')
    assert path.read_text() == '{}'
    user.find('Close').click()
    await user.open('/?place=Stock')
    await user.should_see('Unable to read Stock evidence')
    monkeypatch.setattr('brownstone.config.read_sources', lambda *args: [config | {'source_id': 'empty'}])
    await user.open('/?place=Stock')
    await user.should_see('No complete scan · import in Data')
    await user.should_see('No character captures')
    user.find(marker='page-info').click()
    await user.should_see('Stock evidence')
    assert any(e.text == 'Stock' for e in user.find(ui.button).elements)


async def test_gold_cached_totals_reconciliation_and_entry_evidence(user, tmp_path, monkeypatch):
    from test_ledger import bags, burst

    from brownstone import ledger
    stock_app(tmp_path, monkeypatch)
    rows = burst()
    at = rows[0]['captured_at']
    data = ledger.project(rows, [bags(at - 2, 0), bags(max(r['captured_at'] for r in rows) + 2, 1075)])
    data['excluded_money'] = 1
    calls = []
    def load(config):
        calls.append(config)
        return data
    monkeypatch.setattr(ledger, 'load', load)
    await user.open('/?place=Stock')
    await user.should_see('Where did our gold come from and go?')
    await user.should_see('Incomplete evidence')
    widget = next(iter(user.find(marker='gold-totals').elements))
    assert {r['Category'] for r in widget.rows} == {'auction sale', 'deposit refund'}
    assert sum(r['In_copper'] for r in widget.rows) == 1023
    assert all(c['sortable'] for c in widget.columns if c['name'].endswith('copper'))
    reconciliation = next(iter(user.find(marker='gold-reconciliation').elements))
    assert reconciliation.rows[0]['Unexplained_copper'] == 52
    user.find('Gold movements and evidence').click()
    movements = next(iter(user.find(marker='gold-movements').elements))
    assert movements.rows[0]['Entry ID'] == data['movements'][0]['entry_id']
    assert movements.rows[0]['Machine'] == 'fixture'
    assert movements.rows[0]['Change_copper'] == 268
    assert next(c for c in movements.columns if c['name'] == 'Change_copper')['sortable']
    assert 'auction sale' in movements.rows[0]['Allocation']
    user.find(marker='stock-search').type('2589')
    assert len(calls) == 1


async def test_gold_failure_keeps_stock_visible(user, tmp_path, monkeypatch):
    from brownstone import ledger
    stock_app(tmp_path, monkeypatch)

    def broken(config):
        raise ValueError('bad journal')
    monkeypatch.setattr(ledger, 'load', broken)
    await user.open('/?place=Stock')
    await user.should_see('Unable to read gold evidence: bad journal')
    await user.should_see('Items held')
