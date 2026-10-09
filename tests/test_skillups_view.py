"""Skill-ups page: synthetic catalogs and imported offline snapshots."""
from copy import deepcopy
from pathlib import Path

from test_today import catalog
from test_today_view import app, listing_evidence_app, widget

ROOT = Path(__file__).resolve().parents[1]


def open_skillups(at):
    at.radio[0].set_value('Skill-ups').run()
    assert not at.exception
    assert at.radio[0].options.index('Skill-ups') == at.radio[0].options.index('Recipe catalogs') + 1
    return at


def test_without_snapshot_n_change_profession_filter_and_no_writes(tmp_path, monkeypatch):
    at, source, path = app(tmp_path, monkeypatch)
    # Remove completed manifests through a read seam, never use real data.
    monkeypatch.setattr('views.common.latest_snapshot', lambda *args: (None, None, 0))
    c = catalog()
    other = deepcopy(c)
    other['profession'] = 'engineering'
    other['recipes'][0]['profession'] = 'engineering'
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs',
                        lambda *args: [{'name': 'one', 'catalog': c}, {'name': 'two', 'catalog': other}])
    before = path.read_bytes()
    at = open_skillups(at)
    assert any('No imported snapshot' in i.value for i in at.info)
    table = at.dataframe[0].value
    assert 'Units listed' not in table and table.iloc[0]['Units'] == 20
    widget(at.number_input, 'N crafts per recipe').set_value(1).run()
    assert at.dataframe[0].value.iloc[0]['Units'] == 4
    at.multiselect[0].set_value(['tailoring']).run()
    assert at.dataframe[0].value.iloc[0]['Units'] == 2
    assert path.read_bytes() == before
    assert all(not e.proto.expanded for e in at.expander if 'assuming' in e.label)
    assert any('coverage unknown' in c.value for c in at.caption)
    assert 'not observed demand' in at.caption[2].value or any('not observed demand' in c.value for c in at.caption)
    at.multiselect[0].set_value([]).run()
    assert not at.exception and not at.dataframe


def test_tsm_market_columns_prices_and_units_unavailable(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch, stale=True)
    at = open_skillups(at)
    table = at.dataframe[0].value
    assert set(table['Units listed']) == {'not available for this source'}
    assert table.iloc[0]['Lowest unit buyout (g)'] == 0.001
    assert any('stale' in c.value for c in at.caption)
    assert any('stale' in w.value for w in at.warning)
    assert table.iloc[1]['Lowest unit buyout (g)'] is None or table.iloc[1].isna()['Lowest unit buyout (g)']
    monkeypatch.setattr('views.common.latest_snapshot', lambda *args: (None, None, 0))
    at.run()
    assert at.dataframe[0].value.equals(table.drop(columns=['Units listed', 'Lowest unit buyout (g)']))


def test_addon_metrics_stale_snapshot_market_does_not_change_units(tmp_path, monkeypatch):
    at, _ = listing_evidence_app(tmp_path, monkeypatch, -25)
    at = open_skillups(at)
    table = at.dataframe[0].value
    assert table.iloc[0]['Units'] == 10 and table.iloc[0]['Units listed'] == 6
    assert table.iloc[0]['Lowest unit buyout (g)'] == 0.001
    assert any('stale' in c.value for c in at.caption)


def test_incompatible_catalogs_and_market_read_failure(tmp_path, monkeypatch):
    at, _, _ = app(tmp_path, monkeypatch)
    def fail(*args):
        raise OSError('fixture')
    monkeypatch.setattr('views.skillups.read_skillup_market', fail)
    at = open_skillups(at)
    assert any('Market context unavailable' in w.value for w in at.warning)
    c = catalog()
    c['rules_version'] = 'other'
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [{'name': 'wrong', 'catalog': c}])
    at.run()
    assert any('No compatible catalogs' in i.value for i in at.info)


def test_post_launch_markers_zero_width_errors_and_coverage_render(tmp_path, monkeypatch):
    from test_skillups import chain_catalog
    at, _, _ = app(tmp_path, monkeypatch)
    c = chain_catalog()
    c['recipes'][0]['availability'] = 'post-launch'
    c['recipes'][0]['output_quantity_verified'] = False
    c['items'][0]['vendor_verified'] = False
    c['recipes'][1]['skillup_colors'] = [25, 25, 25, 50]
    c['recipes'][2]['output_quantity'] = 2
    c['page_coverage'] = {'usable': 30, 'no_item': 20, 'unknown_yield': 1}
    c['verified_at'] = '2026-10-08'
    monkeypatch.setattr('brownstone.recipe_catalogs.find_catalogs', lambda *args: [{'name': 'chain', 'catalog': c}])
    at = open_skillups(at)
    assert any('holds 3 of 30' in c.value for c in at.caption)
    assert any('only the catalog’s recipes' in m.value for m in at.markdown)
    assert any('1 post-launch' in c.value for c in at.caption)
    at.toggle[0].set_value(True).run()
    assert any('no raw units added' in e.value for e in at.error)
    recipe_tables = [t.value for t in at.dataframe if 'Recipe' in t.value]
    assert any('post-launch' in str(t['Markers'].tolist()) for t in recipe_tables)
    assert any('no reliable skill-ups' in str(t['Range'].tolist()) for t in recipe_tables)
