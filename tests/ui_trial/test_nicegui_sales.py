"""Offline rendering checks for STORY-073."""
import pytest
from nicegui import ui
from test_sales import invoice, posted, returned
from test_today import plan

from brownstone import sales
from views import nicegui_market, nicegui_today, today_rows

pytestmark = pytest.mark.asyncio


async def test_sale_rate_sell_table_and_card_evidence(user):
    data = sales.project([*posted(item=3, price=18), invoice(count=3, total=54, cut=2)], {3: {'Linen Cloth'}})
    result = plan(sales_data=data)

    @ui.page('/sales-today')
    def page():
        nicegui_today.craft_card(result['craft'][0], result['sell'][0])
        nicegui_today.table([today_rows.sell_row(result['sell'][0])], label='Sell')

    await user.open('/sales-today')
    await user.should_see('Your sales · 3 of 3 sold · 17c each after cut')
    table = next(e for e in user.find(ui.table).elements if 'Sell' in e._markers)
    assert 'Your sales' in [c['name'] for c in table.columns]
    assert table.rows[0]['Your sales'] == '3 of 3 sold · 17c each after cut'


async def test_market_per_character_returns_latest_and_unidentified(user):
    data = sales.project([*posted(), invoice(), returned(at=2200), invoice(name='Unknown', at=2300)],
                         {2589: {'Linen Cloth'}})

    @ui.page('/sales-market')
    def page():
        nicegui_market.own_sales({'your_sales': data['items'], 'unidentified_sales': data['unidentified']})

    await user.open('/sales-market')
    await user.should_see('Fixture · Fixture Realm · Alliance: 5 of 6 sold · 22c each after cut')
    await user.should_see('5 posted · 1 expired · 0 cancelled · newest sale 1970-01-01 00:33 UTC')
    await user.should_see('Unidentified seller invoices in this source and market: 1')


async def test_market_empty_and_unavailable(user):
    @ui.page('/sales-empty')
    def page():
        nicegui_market.own_sales(None)
        nicegui_market.own_sales({'your_sales': [], 'unidentified_sales': 0})
        nicegui_market.own_sales({'your_sales': [], 'unidentified_sales': 0, 'sales_error': 'bad journal row'})

    await user.open('/sales-empty')
    await user.should_see('Sales evidence unavailable')
    await user.should_see('Sales evidence unavailable: bad journal row')
    await user.should_see('none resolved yet')
