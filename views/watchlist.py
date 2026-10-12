"""Watchlist editing and concise hit panels; prices remain read-only."""
from datetime import UTC, datetime

import streamlit as st

from brownstone.money import format_money, to_gold
from brownstone.watchlist import (
    Entry,
    build_watchlist,
    catalog_names,
    hit_text,
    known_names,
    load_entries,
    parse_entry,
    read_watchlist,
    save_entries,
    watchlist_path,
)
from views.common import gold_columns, read_db, show_context
from views.navigation import QUESTIONS


def _load(config):
    path = watchlist_path(config['data_dir'], config['source_id'])
    try:
        return path, load_entries(path), False
    except Exception as error:
        st.warning(f'Could not read Watchlist: {error}. Empty read-only list; fix or remove {path.name} before saving.')
        return path, [], True


def _evidence(config, entries, catalogs, with_names=True):
    """Rows and pick names; skip the name scan when the caller only needs hits."""
    if not (config['data_dir'] / 'brownstone.duckdb').exists():
        return build_watchlist(entries, {}, None, datetime.now(UTC), config['max_age_hours']), \
            catalog_names(catalogs, config)
    with read_db(config) as db:
        result = read_watchlist(db, config, entries, datetime.now(UTC))
        hits = any(row['buy_hit'] or row['sell_hit'] for row in result['rows'])
        return result, known_names(db, config, catalogs) if with_names or hits else {}


def render(config, catalogs):
    st.subheader("Watchlist")
    st.caption(QUESTIONS["Watchlist"])
    show_context(config)
    st.caption('Base items only; targets are per unit. Names help pick an item; entries store its ID.')
    path, entries, readonly = _load(config)
    try:
        result, names = _evidence(config, entries, catalogs)
    except Exception as error:
        st.warning(f'Watchlist evidence unavailable: {error}')
        return
    if not readonly:
        with st.expander('Add or edit entries', expanded=not entries):
            _editor(config, path, entries, names)
    _time(result)
    if entries:
        missing = 'not available for this source' if result['freshness'] else 'no snapshot'
        st.dataframe([_row(row, names, missing) for row in result['rows']], hide_index=True,
                     column_config=gold_columns('Buy below (g)', 'Sell above (g)', 'Lowest unit buyout (g)'))
    else:
        st.info('No watchlist entries for this source.')


def _editor(config, path, entries, names):
    chosen = st.selectbox('Entry to edit', [None, *[e.item_id for e in entries]],
                         format_func=lambda i: ('Add new entry' if i is None
                                                else f'{names.get(i, "Unknown item")} ({i})'),
                          key=f"watch-edit-{config['source_id']}")
    current = next((e for e in entries if e.item_id == chosen), None)
    # A new form key after each save starts the next entry from empty fields.
    saves = st.session_state.get(f"watch-saves-{config['source_id']}", 0)
    with st.form(f"watch-entry-{config['source_id']}-{chosen}-{saves}"):
        item_id = chosen or _item_input(names)
        buy = st.text_input('Buy below',
                            value=format_money(current.buy_copper) if current and current.buy_copper else '')
        sell = st.text_input('Sell above',
                             value=format_money(current.sell_copper) if current and current.sell_copper else '')
        note = st.text_input('Note', value=current.note if current else '')
        save = st.form_submit_button('Save entry')
        remove = st.form_submit_button('Remove entry', disabled=current is None)
    if save or remove:
        try:
            updated = [e for e in entries if e.item_id != chosen]
            if save:
                entry = parse_entry(item_id, buy, sell, note)
                if any(e.item_id == entry.item_id for e in updated):
                    raise ValueError('This item already has an entry; select it to edit')
                updated.append(entry)
            save_entries(path, updated)
        except Exception as error:
            st.error(f'Watchlist not saved: {error}')
        else:
            st.session_state[f"watch-saves-{config['source_id']}"] = saves + 1
            st.rerun()


def _item_input(names):
    """New entries only: an edited entry keeps its item ID, so picking can't move it."""
    picked = st.selectbox('Known item (optional)', [None, *sorted(names, key=lambda i: (names[i], i))],
                          format_func=lambda i: 'Use item ID below' if i is None else f'{names[i]} ({i})')
    typed = st.number_input('Item ID', min_value=1, value=1, step=1)
    return picked or int(typed)


def _time(result, warn=True):
    freshness = result['freshness']
    if freshness:
        st.caption(f"Snapshot time: {freshness['observed_at']:%Y-%m-%d %H:%M:%S} UTC · {freshness['basis']}")
        if warn and freshness['stale']:
            st.warning('Watchlist prices are stale or future-dated; inspect before acting.')


def _row(row, names, missing):
    entry: Entry = row['entry']
    return {'Item': names.get(entry.item_id, 'Unknown item'), 'Item ID': entry.item_id,
            'Buy state': row['buy_state'], 'Sell state': row['sell_state'],
            'Buy below (g)': to_gold(entry.buy_copper), 'Sell above (g)': to_gold(entry.sell_copper),
            'Lowest unit buyout (g)': to_gold(row['price']),
            'Units listed': row['units'] if row['units'] is not None else missing,
            'Units at or below buy target': row['buy_units'] if row['buy_units'] is not None
            else missing if entry.buy_copper else '—',
            'Note': entry.note}


def render_hits(config, catalogs=()):
    _, entries, _ = _load(config)
    if not entries:
        return
    try:
        result, names = _evidence(config, entries, catalogs, with_names=False)
    except Exception as error:
        st.warning(f'Watchlist evidence unavailable: {error}')
        return
    hits = [row for row in result['rows'] if row['buy_hit'] or row['sell_hit']]
    if not hits:
        return
    st.markdown('**Watchlist hits**')
    # Hit states already say stale; the host page owns the freshness warning.
    _time(result, warn=False)
    for row in hits:
        st.caption(hit_text(row, names))
