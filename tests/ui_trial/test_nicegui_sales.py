"""Offline rendering checks for STORY-073."""
import pytest
from nicegui import ui
from test_sales import invoice, posted
from test_today import plan

from brownstone import sales
from views import nicegui_today, today_rows

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
