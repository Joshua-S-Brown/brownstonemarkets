"""Compact Today line projections; original Queue text and evidence remain intact."""
from brownstone.today_characters import recipe_rank
from views import today_rows


def route_lines(stops, arguments, qualities, crafts):
    posts = iter(crafts)
    for stop in stops:
        for line in stop['lines']:
            row = line['evidence']
            item = row.get('item_id')
            band = ''
            if row['stage'] == 'craft':
                catalog = next(c for c in arguments['catalogs'] if c['catalog_id'] == row['catalog_id'])
                item = catalog['recipes_by_id'][row['recipe_id']]['output_item_id']
                key = tuple(stop['characters'][0]) if len(stop['characters']) == 1 else None
                state = arguments.get('character_data', {}).get(key)
                rank = recipe_rank(state, row['recipe_id']) if state else None
                band = today_rows.recipe_band(row, rank, arguments['catalogs'])
            if row['stage'] == 'post':
                item = next(posts)['output_item_id']
            line['display'] = dict(item_id=item, quality=base_quality(qualities, item), skillup_band=band)
            line['warnings'] = today_rows.warning_text(row)


def base_quality(qualities, item):
    if (item, None, 'base') in qualities:
        return qualities[item, None, 'base']
    matches = [v for (i, _, _), v in qualities.items() if i == item]
    return matches[0] if len(matches) == 1 and (item, None, None) in qualities else None
