"""URL-only return destinations and page-local link updates."""
from urllib.parse import urlencode

from nicegui import ui

TABS = ('Plan', 'Shopping list', 'Sell', 'Queue', 'Extras')
VIEWS = ('Today plan', 'This session')


def read_origin(place, tab, view, item, name):
    if place == 'Today' and tab in TABS and view in VIEWS:
        return {'origin_place': place, 'origin_tab': tab, 'origin_view': view}
    if (place == 'Market' and item.isascii() and item.isdecimal() and len(item) <= 10
            and 0 < int(item) < 2**32 and name.strip()):
        return {'origin_place': place, 'origin_item': item, 'origin_name': name[:200]}
    return {}


def back_link(config, origin):
    if not origin:
        return
    values = {'game': config['game_version'], 'source': config['source_id'], 'place': origin['origin_place']}
    if values['place'] == 'Today':
        values.update(tab=origin['origin_tab'], view=origin['origin_view'])
        label = 'This session' if origin['origin_view'] == 'This session' else origin['origin_tab']
    else:
        values['item'] = origin['origin_item']
        label = origin['origin_name']
    ui.link(f"← Back to {values['place']} · {label}", '/?' + urlencode(values)).classes(
        'min-h-[44px] inline-flex items-center underline').mark('back-link')


def today_location(config, tab=None, view=None):
    origin = config['_origin']
    if tab is not None:
        origin['origin_tab'] = tab
    if view is not None:
        origin['origin_view'] = view
    for update in config['_location_updates']:
        update()
    ui.navigate.history.replace('/?' + urlencode({
        'game': config['game_version'], 'source': config['source_id'], 'place': 'Today',
        'tab': origin['origin_tab'], 'view': origin['origin_view']}))


def set_href(link, target):
    link._props['href'] = target
    link.update()


def today_config(config, tab, session):
    return {**config, '_origin': {'origin_place': 'Today', 'origin_tab': tab,
                                 'origin_view': session.get('view', 'Today plan')}, '_location_updates': []}


def market_url(config, item_id=None, origin=None):
    return '/app/market?' + urlencode({'source': config['source_id'],
        **({'inspect': item_id} if item_id is not None else {}),
        **(origin if origin is not None else config.get('_origin', {}))})


def item_url(config, item_id, origin=None):
    return market_url(config, item_id, origin)


def item_link(config, item_id, name, origin=None):
    link = ui.link(name, item_url(config, item_id, origin)).classes(
        'min-h-[44px] inline-flex items-center underline').style('color:var(--brand)')
    if '_location_updates' in config:
        config['_location_updates'].append(lambda: set_href(link, item_url(config, item_id, origin)))
    return link
