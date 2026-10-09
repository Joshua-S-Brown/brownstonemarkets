"""Skill-up expectations, with optional read-only market context."""
import streamlit as st

from brownstone.action_board import compatible_catalogs
from brownstone.money import to_gold
from brownstone.skillups import build_skillups, material_totals
from brownstone.today_data import read_skillup_market
from views.common import gold_columns, load_latest, read_db, show_context, show_freshness


def render(config, catalogs):
    st.subheader('Skill-ups')
    show_context(config)
    st.caption('Expectation from catalog data and an assumed number of crafts per recipe, not observed demand '
               'or a forecast. Real levellers craft some recipes more and skip others. Unknown skill-up ranges '
               'are placed by learned level only. CRAFT-10: orange inclusive to green exclusive; '
               '25-point bands; each recipe counted once in totals; routes stay within each catalog.')
    selected = compatible_catalogs(catalogs, config)
    if not selected:
        st.info('No compatible catalogs. Add or update a profession on Recipe catalogs.')
        return
    professions = sorted({c['profession'] for c in selected})
    chosen = st.multiselect('Professions', professions, default=professions,
                            key=f"skillups-professions-{config['source_id']}")
    n = st.number_input('N crafts per recipe', min_value=1, max_value=50, value=5, step=1, key='skillups-n')
    include = st.toggle('Include post-launch recipes in totals', value=False, key='skillups-post-launch')
    plan = build_skillups([c for c in selected if c['profession'] in chosen], n, include)
    context = _market(config, plan)
    assumption = f'assuming {n} crafts of each recipe'
    qualifier = ' · only the catalog’s recipes' if plan['partial'] else ''
    st.markdown(f"### Totals across shown professions — {assumption}{qualifier}")
    st.caption(f"{plan['excluded']} post-launch recipes left out of totals")
    errors = sum(row['error'] is not None for group in plan['groups'] for row in group['recipes'])
    if errors:
        st.warning(f'{errors} recipes could not expand; their raw units are omitted. See errors in the bands.')
    _materials(plan, context, n)
    for group in plan['groups']:
        catalog = group['catalog']
        title = catalog['profession'].replace('-', ' ').title()
        st.markdown(f"### {title} — {assumption}")
        st.caption(group['coverage'])
        st.caption(f"Catalog {catalog.get('catalog_id', catalog['profession'])} · "
                   f"version {catalog['catalog_version']} · {group['excluded']} post-launch recipes left out")
        qualifier = ' · only the catalog’s recipes' if group['partial'] else ''
        st.markdown(f"#### Profession totals — {assumption}{qualifier}")
        _materials(group, context, n)
        for band in group['bands']:
            with st.expander(f"{title} {band['label']} — {assumption}"):
                if band['recipes']:
                    st.dataframe([_recipe_row(catalog, row) for row in band['recipes']], hide_index=True)
                else:
                    st.caption('No catalog recipes in this band.')
                for row in band['recipes']:
                    if row['error']:
                        st.error(f"{row['recipe']['name']}: {row['error']}; no raw units added")
                tables = {kind: material_totals([{'catalog': catalog, 'recipes': band['recipes']}], kind)
                          for kind in ('direct', 'raw')}
                _materials(tables, context, n)


def _market(config, plan):
    manifest, sid, _ = load_latest(config, 'No imported snapshot; market columns are absent.')
    if manifest is None:
        return None
    freshness = show_freshness(config, manifest)
    st.caption(f"Market context · snapshot {sid} · {freshness['observed_at'].isoformat()} · "
               f"{freshness['basis']} · {'stale' if freshness['stale'] else 'fresh'} · display only")
    item_ids = {item for group in plan['groups'] for item in group['catalog']['items_by_id']}
    try:
        with read_db(config) as db:
            return read_skillup_market(db, config, sid, item_ids)
    except Exception as error:
        st.warning(f'Market context unavailable: {error}')
        return None


def material_rows(rows, context):
    result = []
    for row in rows:
        display = {'Material': row['name'], 'Item ID': row['item_id'], 'Units': row['units'],
                   'Professions': ', '.join(row['professions']), 'Bands': ', '.join(row['bands'])}
        if context is not None:
            market = context.get(row['item_id'], {})
            display['Units listed'] = (market['units'] if market.get('units') is not None
                                       else market.get('units_note', 'not available for this source'))
            price = market.get('min_buyout')
            display['Lowest unit buyout (g)'] = to_gold(price) if price and price > 0 else None
        result.append(display)
    return result


def _materials(tables, context, n):
    for kind in ('direct', 'raw'):
        st.markdown(f"**{kind.title()} materials — assuming {n} crafts of each recipe**")
        rows = material_rows(tables[kind], context)
        if rows:
            st.dataframe(rows, hide_index=True, column_config=gold_columns('Lowest unit buyout (g)'))
        else:
            st.caption('No material units in this selection.')


def _markers(record):
    flags = [f"{key.removesuffix('_verified')} unconfirmed" for key, value in record.items()
             if key.endswith('_verified') and value is False]
    if record.get('availability') == 'post-launch':
        flags.append('post-launch')
    return flags


def _recipe_row(catalog, row):
    recipe = row['recipe']
    flags = _markers(recipe)
    for ingredient in recipe['inputs']:
        item = catalog['items_by_id'][ingredient['item_id']]
        flags.extend(f"{item['name']} ({item['item_id']}): {flag}" for flag in _markers(item))
    return {'Recipe': recipe['name'], 'Recipe ID': recipe['recipe_id'], 'Learned at': recipe.get('required_skill'),
            **dict(zip(('Orange', 'Yellow', 'Green', 'Grey'), recipe.get('skillup_colors', [None] * 4), strict=True)),
            'Range': row['label'], 'Markers': '; '.join(flags), 'Raw expansion error': row['error']}
