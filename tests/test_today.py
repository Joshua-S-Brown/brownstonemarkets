"""Offline Today v1 fixtures independent of locally selected professions."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from brownstone.crafting import parse_recipe_catalog
from brownstone.money import format_money, parse_money
from brownstone.today import Ladder, build_today
from brownstone.today_settings import TodaySettings, load_settings, save_settings, settings_path

NOW = datetime(2026, 10, 6, tzinfo=UTC)
MARKET = {"source_id": "fixture", "market_id": "classic-us-mankrik-alliance", "game_version": "classic",
          "region": "us", "scope": "house", "realm": "mankrik", "server_type": "", "faction": "alliance",
          "environment": "live", "rules_version": "fixture-v1"}
SNAPSHOT = {**MARKET, "collected_at": NOW.isoformat(), "snapshot_id": "fixture", "scan_id": "scan"}


def catalog():
    items = [{"item_id": i, "name": f"Fixture {i}", "role": role, "source_url": "https://example.com/item"}
             for i, role in [(1, "material"), (2, "vendor_material"), (3, "finished")]]
    items[1]["vendor_price_copper"] = 10
    recipe = {"recipe_id": 30, "name": "Fixture craft", "profession": "tailoring", "output_item_id": 3,
              "output_quantity": 1, "source_url": "https://example.com/recipe", "required_skill": 1,
              "inputs": [{"item_id": 1, "quantity": 2}, {"item_id": 2, "quantity": 1}]}
    return parse_recipe_catalog({"schema_version": 1, "game_version": "classic", "rules_version": "fixture-v1",
                                 "profession": "tailoring", "catalog_version": "1", "catalog_id": "fixture",
                                 "status": "fixture", "items": items, "recipes": [recipe]})



def output_catalog(item_id, identity):
    c = deepcopy(catalog())
    c["catalog_id"] = identity
    output = c["items_by_id"].pop(3)
    output["item_id"] = item_id
    c["items_by_id"][item_id] = output
    c["recipes_by_id"][30]["output_item_id"] = item_id
    c["recipe_for_output"] = {item_id: 30}
    return c

def plan(settings=None, **overrides):
    args = dict(catalogs=[catalog()], observations={1: {"min_buyout": 10, "market_value": 20},
                                                  3: {"min_buyout": 200, "market_value": 200}},
                market=MARKET, snapshot=SNAPSHOT, settings=settings or TodaySettings(10000, 1, "fixed"),
                now=NOW, listings={1: [(2, 20, 10), (4, 80, 20), (20, 600, 30)]},
                metrics={1: {"unit_buyout_p25": 30}, 3: {"min_buyout": 200, "listings": 3,
                                                       "units": 8, "largest_stack_units": 3}})
    return build_today(**{**args, **overrides})


@pytest.mark.parametrize("value,expected", [("12g 50s", 125000), ("75s", 7500), ("1g5s20c", 10520),
                                           ("0c", 0), ("1,234g 99s", 12349900), ("100s", 10000),
                                           (" 2G 4C ", 20004), ("-3s", -300)])
def test_money_units(value, expected):
    assert parse_money(value) == expected


@pytest.mark.parametrize("value", ["12", "", "1.2g", "12gold", "1g 2g", "+1g", "1g nonsense", "1,23g"])
def test_money_rejects_ambiguous_or_malformed_text(value):
    with pytest.raises(ValueError):
        parse_money(value)


@pytest.mark.parametrize("amount", [0, 1, 99, 100, 10520, 10000000, -12345678])
def test_money_display_round_trip(amount):
    assert parse_money(format_money(amount)) == amount


@pytest.mark.parametrize("funds,expected", [(5000, 1000), (1000000, 10000), (10000000, 100000), (100001, 1001)])
def test_scaled_gain_floor_and_integer_ceiling(funds, expected):
    assert TodaySettings(funds).minimum_gain == expected
    assert TodaySettings(funds, 123, "fixed").minimum_gain == 123


@pytest.mark.parametrize("changes", [{"gold_copper": -1}, {"gold_copper": True}, {"mode": "other"},
                                     {"max_crafts": 0}, {"max_crafts": 1001}, {"percent_basis_points": 10001}])
def test_settings_reject_invalid_values(changes):
    with pytest.raises(ValueError):
        TodaySettings(**changes)


def test_settings_atomic_persistence_and_missing_defaults(tmp_path):
    path = tmp_path / "settings" / "today.json"
    assert load_settings(path) == TodaySettings()
    settings = TodaySettings(10000, 500, "fixed", 250, 8)
    save_settings(path, settings)
    assert load_settings(path) == settings and not list(path.parent.glob("*.tmp"))
    path.write_text('{"mode":"unknown"}')
    with pytest.raises(ValueError):
        load_settings(path)


def test_settings_are_per_source_in_a_shared_data_directory(tmp_path):
    forever, classic = settings_path(tmp_path, "forever"), settings_path(tmp_path, "classic")
    save_settings(forever, TodaySettings(1000000))
    assert load_settings(classic) == TodaySettings() and load_settings(forever).gold_copper == 1000000
    assert forever.name == "today-settings.forever.local.json"


def test_ladder_costs_whole_listings_without_crediting_surplus():
    ladder = Ladder([(2, 20, 10), (4, 80, 20), (10, 300, 30), (0, 0, 0)])
    assert ladder.quote(3) == {"cost_copper": 100, "end": 2, "purchased_units": 6, "highest_unit_copper": 20}
    assert ladder.quote(1, 2)["cost_copper"] == 300
    assert ladder.quote(17) is None


def test_per_item_cap_and_listing_costs_explain_batch():
    result = plan(TodaySettings(1000, 1, "fixed", max_crafts=3))
    row = result["craft"][0]
    assert (row["batch_size"], row["batch_cost_copper"], row["batch_profit_copper"]) == (3, 130, 440)
    assert row["limiting_factor"] == "per-item cap"
    assert row["profit_per_craft_copper"] == 146  # Rounded down presentation, batch is exact.
    assert result["shopping_total_copper"] == 130
    material = next(r for r in result["buy"] if r["item_id"] == 1)
    assert (material["quantity"], material["purchased_units"], material["highest_unit_copper"]) == (6, 6, 20)
    assert material["cheap_now"]
    assert not next(r for r in result["buy"] if r["method"] == "vendor")["cheap_now"]


def test_funds_limit_and_depth_limit():
    row = plan(TodaySettings(130, 1, "fixed"))["craft"][0]
    assert row["batch_size"] == 3 and row["limiting_factor"] == "gold available"
    row = plan(listings={1: [(4, 40, 10)]})["craft"][0]
    assert row["batch_size"] == 2 and row["limiting_factor"] == "listed materials"


def test_batch_stops_before_listings_that_lose_money():
    # One craft earns 160c; every further craft needs a 2,000c listing and loses money.
    expensive = {1: [(2, 20, 10), *[(2, 2000, 1000)] * 4]}
    row = plan(listings=expensive)["craft"][0]
    assert (row["batch_size"], row["batch_profit_copper"]) == (1, 160)
    assert row["limiting_factor"] == "more crafts lower profit"
    assert row["purchases"][0]["purchased_units"] == 2


def test_batch_sizing_looks_past_a_whole_stack_dip():
    # Craft 2 opens a 20-unit stack (a loss); by craft 5 that stack has paid for itself.
    row = plan(listings={1: [(2, 20, 10), (20, 600, 30)]})["craft"][0]
    assert (row["batch_size"], row["batch_profit_copper"], row["limiting_factor"]) == (5, 280, "per-item cap")


def test_hidden_reason_precedence_missing_unsupported_funds_depth_gain():
    assert plan(TodaySettings(1, 1, "fixed"))["hidden"] == {"one craft exceeds funds": 1}
    assert plan(TodaySettings(10000, 10000, "fixed"))["hidden"] == {"below minimum gain": 1}
    assert plan(listings={})["hidden"] == {"insufficient listed materials": 1}
    assert plan(observations={})["hidden"] == {"missing prices": 1}
    cyclic = catalog()
    cyclic["recipe_for_output"][1] = 30
    assert plan(catalogs=[cyclic])["hidden"] == {"unsupported recipe": 1}


@pytest.mark.parametrize("count,units,largest,expected", [(2, 100, 1, True), (3, 10, 5, True),
                                                        (3, 10, 4, False)])
def test_thin_market_exact_boundaries(count, units, largest, expected):
    row = plan(metrics={3: {"min_buyout": 200, "listings": count, "units": units,
                           "largest_stack_units": largest}})["sell"][0]
    assert row["thin"] is expected
    assert row["undercut_copper"] == 199
    assert row["undercut_batch_profit_copper"] == 189 * row["batch_size"] - plan()["craft"][0]["batch_cost_copper"]


def test_no_positive_undercut_and_cheap_now_is_strict():
    result = plan(metrics={1: {"unit_buyout_p25": 10}, 3: {"min_buyout": 1, "listings": 1,
                                                         "units": 1, "largest_stack_units": 1}})
    assert result["sell"][0]["undercut_copper"] is None
    assert result["sell"][0]["undercut_batch_profit_copper"] is None
    assert not result["buy"][0]["cheap_now"]


def test_vendor_aside_uses_observed_sell_price_and_strict_listing_threshold():
    result = plan(vendor_prices={1: 21, 2: 10, 99: 100}, settings=TodaySettings(10000, 26, "fixed"))
    row = result["below_vendor"][0]
    assert (row["gain_copper"], row["listings"], row["purchased_units"]) == (26, 2, 6)
    assert not plan(vendor_prices={1: 21}, settings=TodaySettings(10000, 27, "fixed"))["below_vendor"]
    assert plan(vendor_prices={1: 20})["below_vendor"][0]["listings"] == 1


@pytest.mark.parametrize("offset", [timedelta(hours=-25), timedelta(minutes=16)])
def test_stale_and_future_remain_inspectable_but_never_actionable(offset):
    result = plan(snapshot={**SNAPSHOT, "updated_at": (NOW + offset).isoformat()}, vendor_prices={1: 21})
    assert result["freshness"]["stale"]
    for name in ("craft", "buy", "sell", "below_vendor"):
        assert result[name]
        assert all(row["stale"] and not row["actionable"] for row in result[name])


def test_tsm_only_funds_and_cap_and_missing_zero_never_free():
    result = plan(listings=None, metrics=None)
    assert result["craft"][0]["batch_size"] == 5
    assert result["craft"][0]["batch_cost_copper"] == 250  # cautious aggregate inputs
    assert not result["listing_evidence_available"]
    assert result["sell"][0]["thin"] is None and result["sell"][0]["lowest_copper"] is None
    assert not result["below_vendor"] and not any(r["cheap_now"] for r in result["buy"])
    assert plan(listings=None, metrics=None, settings=TodaySettings(100, 1, "fixed"))["craft"][0]["batch_size"] == 2
    assert plan(observations={1: {"min_buyout": 0, "market_value": 0}})["hidden"] == {"missing prices": 1}


def test_shared_plan_reserves_funds_and_each_whole_listing_once():
    first = catalog()
    second = output_catalog(4, "second")
    observations = {1: {"min_buyout": 10, "market_value": 20},
                    3: {"min_buyout": 200, "market_value": 200},
                    4: {"min_buyout": 200, "market_value": 200}}
    result = plan(catalogs=[second, first], observations=observations,
                  settings=TodaySettings(260, 1, "fixed", max_crafts=2),
                  listings={1: [(4, 40, 10), (4, 80, 20)]})
    assert [r["catalog_id"] for r in result["craft"]] == ["fixture", "second"]
    assert [r["batch_cost_copper"] for r in result["craft"]] == [60, 100]
    assert result["shopping_total_copper"] == 160
    assert len(result["sell"]) == 2
    assert result["hidden"] == {}
    limited = plan(catalogs=[second, first], observations=observations,
                   settings=TodaySettings(60, 1, "fixed", max_crafts=2),
                   listings={1: [(4, 40, 10), (4, 80, 20)]})
    assert len(limited["craft"]) == 1
    assert limited["hidden"] == {"one craft exceeds funds": 1}


def test_caps_rest_counts_ties_and_no_compatible_catalogs():
    catalogs = [output_catalog(3 + i, f"c{i:02}") for i in range(12)]
    observations = {1: {"min_buyout": 10, "market_value": 20},
                    **{3 + i: {"min_buyout": 200, "market_value": 200} for i in range(12)}}
    result = plan(catalogs=catalogs, observations=observations, listings=None, metrics=None,
                  settings=TodaySettings(100000, 1, "fixed"))
    assert len(result["craft"]) == 10 and result["remaining"]["craft"] == 2
    assert len(result["sell"]) == 10
    assert result["shopping_total_copper"] == 2500
    assert [r["catalog_id"] for r in result["craft"]] == [f"c{i:02}" for i in range(10)]
    assert not plan(catalogs=[{**catalog(), "rules_version": "other"}])["craft"]


def test_rules_market_scope_and_catalog_identity_are_enforced():
    with pytest.raises(ValueError, match="different market"):
        plan(snapshot={**SNAPSHOT, "environment": "beta"})
    with pytest.raises(ValueError, match="identities"):
        plan(catalogs=[catalog(), catalog()])


def test_display_only_evidence_flags_survive():
    c = catalog()
    c["recipes_by_id"][30].update(output_quantity_verified=False, availability="post-launch")
    c["items_by_id"][2]["vendor_verified"] = False
    row = plan(catalogs=[c])["craft"][0]
    assert row["availability"] == "post-launch" and len(row["evidence_notes"]) == 3


def test_duplicate_outputs_choose_best_catalog_once_and_cap_is_per_item():
    second = {**deepcopy(catalog()), "catalog_id": "second"}
    result = plan(catalogs=[second, catalog()])
    # One batch of the most profitable size (3 crafts: 440c; 5 would earn 200c), not one per catalog.
    assert len(result["craft"]) == 1 and result["craft"][0]["batch_size"] == 3
    assert result["hidden"] == {"output already planned": 1}
    assert len(result["sell"]) == 1


def test_remaining_craft_count_counts_outputs_not_routes():
    catalogs = [output_catalog(3 + i, f"c{i:02}") for i in range(11)]
    catalogs.append(output_catalog(13, "c99"))  # A second route to the eleventh output.
    observations = {1: {"min_buyout": 10, "market_value": 20},
                    **{3 + i: {"min_buyout": 200, "market_value": 200} for i in range(11)}}
    result = plan(catalogs=catalogs, observations=observations, listings=None, metrics=None,
                  settings=TodaySettings(100000, 1, "fixed"))
    assert len(result["craft"]) == 10 and result["remaining"]["craft"] == 1


@pytest.mark.parametrize("key,value", [("source_id", "other"), ("rules_version", "other")])
def test_today_rejects_snapshot_source_or_rules_mismatch(key, value):
    with pytest.raises(ValueError, match=key):
        plan(snapshot={**SNAPSHOT, key: value})


def test_cheap_now_changes_only_annotation_and_independent_aside_caps():
    ordinary = plan()
    cheaper = plan(metrics={1: {"unit_buyout_p25": 1000},
                            3: {"min_buyout": 200, "listings": 3, "units": 8, "largest_stack_units": 3}})
    assert ordinary["craft"] == cheaper["craft"]
    listings = {i: [(2, 20, 10)] for i in range(20, 32)}
    result = plan(listings=listings, vendor_prices={i: 100 for i in listings})
    assert len(result["below_vendor"]) == 10 and result["remaining"]["below_vendor"] == 2
    assert result["hidden"] == {"insufficient listed materials": 1}


def test_batch_revenue_retains_board_rounding_and_full_stack_surplus():
    result = plan(settings=TodaySettings(1000, 1, "fixed", max_crafts=1), listings={1: [(20, 200, 10)]})
    assert not result["craft"] and result["hidden"] == {"below minimum gain": 1}
    result = plan(settings=TodaySettings(1000, 1, "fixed", max_crafts=1), listings={1: [(20, 100, 5)]})
    row = result["craft"][0]
    assert row["batch_cost_copper"] == 110 and row["batch_profit_copper"] == 80
    bought = next(r for r in result["buy"] if r["item_id"] == 1)
    assert bought["quantity"] == 2 and bought["purchased_units"] == 20
    assert not row["stale"] and row["actionable"]


def test_shopping_cap_counts_full_cost_of_unshown_materials():
    c = catalog()
    for item_id in range(10, 22):
        c['items_by_id'][item_id] = {'item_id': item_id, 'name': f'Vendor {item_id}',
                                   'role': 'vendor_material', 'vendor_price_copper': 10,
                                   'source_url': 'https://example.com/vendor'}
    c['recipes_by_id'][30]['inputs'] = [{'item_id': i, 'quantity': 1} for i in range(10, 22)]
    result = plan(catalogs=[c], listings=None, metrics=None)
    assert len(result['buy']) == 10 and result['remaining']['buy'] == 2
    assert result['shopping_total_copper'] == 600
    assert result['craft'][0]['batch_cost_copper'] == 600


def test_final_profit_order_survives_budget_resizing_and_hidden_tail():
    # Expensive later stacks make one craft more profitable than any larger batch, so it ranks first.
    first = output_catalog(4, "vendor-only")
    first["recipes_by_id"][30]["inputs"] = [{"item_id": 2, "quantity": 6}]
    hidden = output_catalog(5, "unprofitable")
    hidden["recipes_by_id"][30]["inputs"] = [{"item_id": 2, "quantity": 1}]
    observations = {1: {"min_buyout": 10, "market_value": 100},
                    3: {"min_buyout": 200, "market_value": 200},
                    4: {"min_buyout": 85, "market_value": 85},
                    5: {"min_buyout": 1, "market_value": 1}}
    result = plan(catalogs=[catalog(), first, hidden], observations=observations,
                  settings=TodaySettings(1000, 1, "fixed"), listings={1: [(2, 20, 10), (8, 800, 100)]})
    assert [r["batch_profit_copper"] for r in result["craft"]] == [160, 100]
    assert [r["batch_size"] for r in result["craft"]] == [1, 5]
    assert result["hidden"] == {"below minimum gain": 1}


def test_craft_details_reserved_costs_reconcile_across_crafts_and_vendor(monkeypatch):
    from brownstone.today import craft_details

    second = output_catalog(4, 'second')
    second['items_by_id'][1]['name'] = 'Second catalog material'
    result = plan(catalogs=[catalog(), second],
                  observations={1: {'min_buyout': 10, 'market_value': 20},
                                3: {'min_buyout': 200}, 4: {'min_buyout': 200}},
                  settings=TodaySettings(1000, 1, 'fixed', max_crafts=1),
                  listings={1: [(3, 30, 10), (4, 80, 20)]})
    def fail(*args, **kwargs):
        raise AssertionError('Details must not re-quote listings')
    monkeypatch.setattr(Ladder, 'quote', fail)
    totals = {}
    for craft in result['craft']:
        details = craft_details(craft)
        assert sum(r['cost_copper'] for r in details['materials']) == craft['batch_cost_copper']
        assert not details['intermediate_steps']
        expected_name = 'Fixture 1' if craft['catalog_id'] == 'fixture' else 'Second catalog material'
        assert details['materials'][0]['item_name'] == expected_name
        vendor = next(r for r in details['materials'] if r['method'] == 'vendor')
        assert (vendor['quantity'], vendor['purchased_units'], vendor['cost_copper'],
                vendor['highest_unit_copper']) == (1, 1, 10, 10)
        for r in details['materials']:
            assert type(r['cost_copper']) is int
            key = (r['item_id'], r['method'])
            entry = totals.setdefault(key, {'quantity': 0, 'purchased_units': 0, 'cost_copper': 0,
                                           'highest_unit_copper': 0})
            for field in ('quantity', 'purchased_units', 'cost_copper'):
                entry[field] += r[field]
            entry['highest_unit_copper'] = max(entry['highest_unit_copper'], r['highest_unit_copper'])
    for buy in result['buy']:
        assert totals[(buy['item_id'], buy['method'])] == {field: buy[field] for field in totals[(1, 'buy')]}
    assert [craft_details(r)['materials'][0]['cost_copper'] for r in result['craft']] == [30, 80]
    assert result['today_version'] == 4


def chain_catalog():
    c = catalog()
    for item_id in (5, 6):
        c['items_by_id'][item_id] = {'item_id': item_id, 'name': f'Intermediate {item_id}',
                                   'role': 'intermediate', 'source_url': 'https://example.com/item'}
    for recipe_id, output, inputs in [(50, 5, [(6, 2)]), (60, 6, [(1, 3)])]:
        c['recipes_by_id'][recipe_id] = {**c['recipes_by_id'][30], 'recipe_id': recipe_id,
                                       'output_item_id': output,
                                       'inputs': [{'item_id': i, 'quantity': q} for i, q in inputs]}
        c['recipe_for_output'][output] = recipe_id
    c['recipes_by_id'][30]['inputs'] = [{'item_id': 5, 'quantity': 2}, {'item_id': 2, 'quantity': 1}]
    c['items'] = list(c['items_by_id'].values())
    c['recipes'] = list(c['recipes_by_id'].values())
    return c


def test_craft_details_nested_chosen_catalog_steps_and_bought_intermediate():
    from brownstone.today import craft_details

    args = {'catalogs': [chain_catalog()], 'settings': TodaySettings(10000, 1, 'fixed', max_crafts=2),
            'listings': {1: [(30, 300, 10)]}}
    craft = plan(**args)['craft'][0]
    details = craft_details(craft)
    assert [(r['item_id'], r['quantity'], r['crafts'], r['depth'])
            for r in details['intermediate_steps']] == [(5, 4, 4, 1), (6, 8, 8, 2)]
    assert details['materials'][0]['quantity'] == 24
    assert details['materials'][0]['purchased_units'] == 30
    assert sum(r['cost_copper'] for r in details['materials']) == craft['batch_cost_copper'] == 320
    # A cheaper bought intermediate stops the chain, even though catalog recipes exist for it.
    result = plan(**{**args, 'observations': {1: {'min_buyout': 10}, 5: {'min_buyout': 1},
                                            3: {'min_buyout': 200}}, 'listings': {5: [(4, 4, 1)]}})
    details = craft_details(next(r for r in result['craft'] if r['output_item_id'] == 3))
    assert not details['intermediate_steps']
    assert {r['item_id'] for r in details['materials']} == {2, 5}


def test_craft_details_stale_and_full_material_tail():
    from brownstone.today import craft_details

    c = catalog()
    for i in range(10, 22):
        c['items_by_id'][i] = {**c['items_by_id'][2], 'item_id': i, 'name': f'Vendor {i}'}
    c['recipes_by_id'][30]['inputs'] = [{'item_id': i, 'quantity': 1} for i in range(10, 22)]
    result = plan(catalogs=[c], snapshot={**SNAPSHOT, 'updated_at': (NOW - timedelta(hours=25)).isoformat()})
    details = craft_details(result['craft'][0])
    assert len(details['materials']) == 12 and len(result['buy']) == 10 and result['remaining']['buy'] == 2
    assert all(r['stale'] and not r['actionable'] for r in details['materials'])
    assert sum(r['cost_copper'] for r in details['materials']) == result['shopping_total_copper'] == 600


def choice(row, size):
    return {key: row[key] for key in ('catalog_id', 'recipe_id')} | {'batch_size': size}


def two_plan(**overrides):
    return plan(catalogs=[catalog(), output_catalog(4, 'second')],
                observations={1: {'min_buyout': 10}, 3: {'min_buyout': 200}, 4: {'min_buyout': 150}},
                **overrides)


def test_choose_untick_with_and_without_refill():
    args = dict(settings=TodaySettings(130, 1, 'fixed', max_crafts=3),
                listings={1: [(2, 20, 10), (4, 80, 20), (6, 180, 30)]})
    initial = two_plan(**args)
    assert len(initial['craft']) == 1
    choices = [choice(initial['craft'][0], None)]
    exact = two_plan(**args, choices=choices, refill=False)
    refilled = two_plan(**args, choices=choices)
    assert exact['craft'] == exact['buy'] == exact['sell'] == []
    assert exact['shopping_total_copper'] == 0
    assert exact['remaining']['craft'] == 1 and not refilled['dropped_choices']
    assert [r['output_item_id'] for r in refilled['craft']] == [4]
    assert refilled['shopping_total_copper'] <= 130


def test_choose_shrink_grow_and_profit_best_size():
    args = dict(settings=TodaySettings(1000, 1, 'fixed'), listings={1: [(2, 20, 10), (8, 800, 100)]})
    initial = plan(**args)
    row = initial['craft'][0]
    assert row['batch_size'] == 1 and row['feasible_size'] == 5
    grown = plan(**args, choices=[choice(row, 5)], refill=False)['craft'][0]
    assert grown['batch_size'] == 5 and grown['batch_profit_copper'] < row['batch_profit_copper']
    assert grown['limiting_factor'] == 'chosen batch'
    kept = plan(**args, choices=[choice(row, 1)], refill=False)['craft'][0]
    assert kept['limiting_factor'] == row['limiting_factor'] == 'more crafts lower profit'
    assert kept['batch_profit_copper'] == row['batch_profit_copper']
    original = plan()['craft'][0]
    small = plan(choices=[choice(original, 1)], refill=False)['craft'][0]
    assert small['batch_profit_copper'] == 160 < original['batch_profit_copper']
    assert small['batch_cost_copper'] == 30


@pytest.mark.parametrize('size', [0, -1, 6, True, 1.5, '2'])
def test_choose_rejects_infeasible_sizes_without_resizing(size):
    row = plan()['craft'][0]
    result = plan(choices=[choice(row, size)], refill=False)
    assert not result['craft'] and len(result['dropped_choices']) == 1
    assert result['dropped_choices'][0]['batch_size'] == size


def test_choose_reserves_in_plan_order_and_rejects_unaffordable_later_choice():
    args = dict(settings=TodaySettings(200, 1, 'fixed', max_crafts=1),
                listings={1: [(3, 30, 10), (4, 80, 20)]})
    initial = two_plan(**args)
    rows = sorted(initial['craft'], key=lambda r: r['plan_order'], reverse=True)
    result = two_plan(**args, choices=[choice(r, 1) for r in rows], refill=False)
    ordered = sorted(result['craft'], key=lambda r: r['plan_order'])
    assert [r['output_item_id'] for r in ordered] == [r['output_item_id'] for r in rows]
    assert [r['purchases'][0]['cost_copper'] for r in ordered] == [30, 80]
    assert [r['purchases'][0]['end'] for r in ordered] == [1, 2]
    result = two_plan(**{**args, 'settings': TodaySettings(100, 1, 'fixed', max_crafts=1)},
                      choices=[choice(r, 1) for r in rows], refill=False)
    assert len(result['craft']) == 1 and len(result['dropped_choices']) == 1


def test_choose_drop_reasons_name_row_limit_duplicate_and_missing_recipe(monkeypatch):
    args = dict(settings=TodaySettings(200, 1, 'fixed', max_crafts=1), listings={1: [(3, 30, 10), (4, 80, 20)]})
    rows = sorted(two_plan(**args)['craft'], key=lambda r: r['plan_order'])
    missing = {'catalog_id': 'gone', 'recipe_id': 99, 'batch_size': 1}
    monkeypatch.setattr('brownstone.today.ROW_LIMIT', 1)
    result = two_plan(**args, choices=[choice(rows[0], 1), choice(rows[0], 1), choice(rows[1], 1), missing],
                      refill=False)
    assert [d['reason'] for d in result['dropped_choices']] == [
        'Output is already planned; dropped, not resized.', 'Plan already has 1 crafts; dropped, not resized.',
        "Recipe is no longer in today's candidates; dropped, not resized."]


def test_choose_new_scan_drops_supply_missing_and_missing_recipe():
    row = plan()['craft'][0]
    for changes in ({'listings': {}}, {'catalogs': []}, {'settings': TodaySettings(0, 1, 'fixed')}):
        result = plan(**changes, choices=[choice(row, 5)], refill=False)
        assert not result['craft'] and result['dropped_choices']


def test_queue_route_order_totals_and_no_requotes(monkeypatch):
    from brownstone.today import session_queue

    result = plan(catalogs=[chain_catalog()], settings=TodaySettings(10000, 1, 'fixed', max_crafts=2),
                  listings={1: [(30, 300, 10)]})
    def fail(*args, **kwargs):
        raise AssertionError('Queue must not quote reserved purchases again')
    monkeypatch.setattr(Ladder, 'quote', fail)
    queue = session_queue(result['craft'], result['buy'], result['sell'])
    assert queue == result['queue']
    assert [r['stage'] for r in queue['lines']] == ['auction house', 'vendor', 'craft', 'craft', 'craft', 'post']
    assert [r['recipe_id'] for r in queue['lines'] if r['stage'] == 'craft'] == [60, 50, 30]
    assert [r['batch_size'] for r in queue['lines'] if r['stage'] == 'craft'] == [8, 4, 2]
    assert queue['gold_needed_copper'] == result['shopping_total_copper']
    assert queue['expected_profit_copper'] == sum(r['undercut_batch_profit_copper'] for r in result['sell'])
    assert queue['lines'][-1]['unit_copper'] == result['sell'][0]['undercut_copper']


def test_queue_complete_buy_tail_and_missing_undercut():
    c = catalog()
    for i in range(10, 22):
        c['items_by_id'][i] = {**c['items_by_id'][2], 'item_id': i, 'name': f'Vendor {i}'}
    c['recipes_by_id'][30]['inputs'] = [{'item_id': i, 'quantity': 1} for i in range(10, 22)]
    result = plan(catalogs=[c], metrics=None)
    assert len(result['buy']) == 10
    assert len([r for r in result['queue']['lines'] if r['stage'] == 'vendor']) == 12
    assert result['queue']['gold_needed_copper'] == 600
    assert result['queue']['expected_profit_copper'] is None


def test_choose_shrink_refills_without_growing_explicit_batch_or_duplicate_route():
    args = dict(settings=TodaySettings(130, 1, 'fixed', max_crafts=3),
                listings={1: [(2, 20, 10), (4, 80, 20), (6, 180, 30)]})
    row = two_plan(**args)['craft'][0]
    choices = [choice(row, 1)]
    exact = two_plan(**args, choices=choices, refill=False)
    refilled = two_plan(**args, choices=choices)
    assert len(exact['craft']) == 1 and exact['shopping_total_copper'] == 30
    assert {r['output_item_id']: r['batch_size'] for r in refilled['craft']} == {3: 1, 4: 2}
    assert refilled['shopping_total_copper'] == 130
    assert [r['purchases'][0]['end'] for r in sorted(refilled['craft'], key=lambda r: r['plan_order'])] == [1, 2]
    duplicate = output_catalog(3, 'duplicate')
    assert not plan(catalogs=[catalog(), duplicate], choices=[choice(row, None)])['craft']


def test_queue_preserves_sibling_catalog_route_order():
    from brownstone.today import _route_order

    steps = [{'recipe_id': recipe, 'depth': depth} for recipe, depth in
             [(10, 1), (11, 2), (12, 2), (13, 3), (20, 1), (21, 2)]]
    assert [s['recipe_id'] for s in _route_order(steps)] == [11, 13, 12, 10, 21, 20]
