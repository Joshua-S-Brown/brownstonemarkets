"""Vendor ceiling labels beside profits in the native views."""
import pytest
from nicegui import ui
from test_today import MARKET, catalog, plan

from views import nicegui_market as market
from views import nicegui_team as team
from views import nicegui_today as today
from views.today_rows import sell_row

pytestmark = pytest.mark.asyncio


async def test_vendor_label_on_today_card_sell_market_and_team(user):
    c = catalog()
    c['items_by_id'][3]['vendor_price_copper'] = 124
    p = plan(catalogs=[c])
    row, sell = p['craft'][0], p['sell'][0]
    @ui.page('/vendor-ceiling')
    def page():
        today.craft_card(row, sell)
        today.table([sell_row(sell)], label='Sell')
        market.recipe_heading(MARKET, {'recipe': c['recipes_by_id'][30], 'value': row, 'catalog': c})
        today.table(team.reachable_rows({'recipes': [dict(name='Fixture', required_skill=1, points_needed=1,
                    profit_copper=row['profit_copper'], vendor_price_cap_copper=124, vendor_capped=True,
                    estimate={'complete': False, 'reasons': ['fixture']}, confidence='Medium')]}), label='Reachable')
    await user.open('/vendor-ceiling')
    await user.should_see('capped at vendor price 1s 24c')
    tables = [t for t in user.find(ui.table).elements if t.rows and 'Vendor ceiling' in t.rows[0]]
    assert len(tables) == 2
    assert all(t.rows[0]['Vendor ceiling'] == 'capped at vendor price 1s 24c' for t in tables)
    sell_table = next(t for t in tables if 'Output' in t.rows[0])
    assert any(col['field'] == 'Vendor ceiling' for col in sell_table.columns)
