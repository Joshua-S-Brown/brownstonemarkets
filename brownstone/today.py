"""Today: transparent batch estimates and one funded plan reserving listings and holdings.

Routes retain the board’s team-aware choices. Prefix ladders price complete stacks in O(log n),
without expanding units; the clock and all scoped evidence are supplied by the caller.
"""
from bisect import bisect_left
from collections import Counter
from decimal import Decimal

from . import sales, today_holdings
from .action_board import catalog_for_row, compatible_catalogs, rank_catalogs
from .crafting import basis_prices
from .deposits import auction_deposit
from .freshness import assess
from .markets import MARKET_KEYS
from .recipe_graph import RecipeGraph, route_catalog
from .today_characters import filter_candidates, project_recipes, team_makeable
from .today_confidence import confidence, purchase_confidence, route_notes
from .today_settings import TodaySettings
from .today_warnings import PRICE_NOTE, base_signals, price_caps, warning_fields

TODAY_VERSION = 12
ROW_LIMIT = 10


class Ladder:
    def __init__(self, listings):
        self.units = [0]
        self.costs = [0]
        self.prices = [0]
        for quantity, buyout, unit in sorted(listings, key=lambda row: (row[2], row[0], row[1])):
            if quantity > 0 and buyout > 0 and unit > 0:
                self.units.append(self.units[-1] + quantity)
                self.costs.append(self.costs[-1] + buyout)
                self.prices.append(unit)

    def quote(self, quantity, start=0):
        end = bisect_left(self.units, self.units[start] + quantity)
        if end >= len(self.units):
            return None
        return {"cost_copper": self.costs[end] - self.costs[start], "end": end,
                "purchased_units": self.units[end] - self.units[start], "highest_unit_copper": self.prices[end]}


def _net(price, quantity, auction_cut):
    return int(Decimal(price * quantity) * (Decimal(1) - Decimal(str(auction_cut))))


def _quote(choices, batch, ladders, reserved, holdings=None, row=None):
    return _held_quote(choices, batch, ladders, reserved, holdings, row)[0]


def _held_quote(choices, batch, ladders, reserved, holdings=None, row=None):
    """Quote with the route steps left after holdings, so a chosen size needs no second allocation."""
    needs, result, steps = today_holdings.requirements(row, batch, holdings) if holdings and row else ({}, [], None)
    for choice in choices:
        item_id = choice["item_id"]
        quantity = needs.get(item_id, choice["quantity"] * batch)
        if not quantity:
            continue
        if ladders is None or choice["method"] == "vendor":
            unit = choice["unit_cost_copper"]
            quote = {"cost_copper": unit * quantity, "purchased_units": quantity,
                     "highest_unit_copper": unit, "end": 0}
        else:
            ladder = ladders.get(item_id)
            quote = ladder.quote(quantity, reserved.get(item_id, 0)) if ladder else None
        if quote is None:
            return None, steps
        result.append({**choice, **quote, "quantity": quantity})
    return result, steps


def _relevant(row, holdings):
    """Holdings matter to a row only when it uses a held item; other rows keep the pruned search."""
    items = {c["item_id"] for c in [*row["shopping_choices"], *row.get("holding_steps", [])]}
    return holdings if holdings and any(holdings.get(item, 0) > 0 for item in items) else None


def _largest(choices, cap, ladders, reserved, funds, holdings=None, row=None):
    low, high = 0, cap
    while low < high:
        middle = (low + high + 1) // 2
        quote = _quote(choices, middle, ladders, reserved, holdings, row)
        if quote is not None and today_holdings.gold_cost(quote) <= funds:
            low = middle
        else:
            high = middle - 1
    return low


def _profit_peaks(choices, largest, ladders, reserved, holdings=None):
    """Batch sizes where profit can peak: the largest, or the last size before any input needs another listing.

    Without holdings, costs between these sizes are constant while revenue rises. With holdings,
    compare every bounded feasible size to include nested whole-craft depletion boundaries.
    """
    if holdings:
        return range(1, largest + 1)
    sizes = {largest}
    for choice in choices:
        ladder = None if ladders is None or choice["method"] == "vendor" else ladders.get(choice["item_id"])
        if ladder is None:
            continue
        start = reserved.get(choice["item_id"], 0)
        for units in ladder.units[start + 1:]:
            crafts = (units - ladder.units[start]) // choice["quantity"]
            if crafts >= largest:
                break
            if crafts:
                sizes.add(crafts)
    return sorted(sizes)


def _batch(row, settings, ladders, reserved, funds, holdings=None):
    choices, holdings = row["shopping_choices"], _relevant(row, holdings)
    largest = _largest(choices, settings.max_crafts, ladders, reserved, funds, holdings, row)
    if not largest:
        first = _quote(choices, 1, ladders, reserved, holdings, row)
        return None, "insufficient listed materials" if first is None else "one craft exceeds funds"
    quoted = {size: _held_quote(choices, size, ladders, reserved, holdings, row)
              for size in _profit_peaks(choices, largest, ladders, reserved, holdings)}
    quotes = {size: quote for size, (quote, _) in quoted.items()}
    profits = {size: row["net_revenue_copper"] * size - sum(q["cost_copper"] for q in quote)
               for size, quote in quotes.items()}
    size = max(profits, key=lambda s: (profits[s], -s))  # Equal profit: the smaller batch spends less.
    if size < largest:
        limit = "more crafts lower profit"
    elif size == settings.max_crafts:
        limit = "per-item cap"
    else:
        limit = ("listed materials" if _quote(choices, size + 1, ladders, reserved, holdings, row) is None
                 else "gold available")
    profit = profits[size]
    return {**row, "batch_size": size, "batch_cost_copper": row["net_revenue_copper"] * size - profit,
            "batch_profit_copper": profit, "profit_per_craft_copper": profit // size,
            "limiting_factor": limit, "feasible_size": largest, "purchases": quotes[size],
            **_held_batch(*quoted[size])}, None


def _held_batch(purchases, steps):
    if steps is None:
        return {}
    return {"gold_cost_copper": today_holdings.gold_cost(purchases), "reserved_steps": steps}


def _candidates(catalogs, observations, market, snapshot, now, max_age_hours, auction_cut, projection, makers, signals):
    selected = compatible_catalogs(catalogs, market)
    if not selected:
        return [], Counter(), []
    graph = RecipeGraph(selected, makers, market) if makers is not None else None
    caps = price_caps(signals)
    board = rank_catalogs(selected, observations, market, snapshot, now=now,
                          max_age_hours=max_age_hours, auction_cut=auction_cut, recipe_graph=graph,
                          sell_price_caps=caps)
    filtered, hidden = filter_candidates(board["rows"], projection)
    prices, sales = basis_prices(observations, "cautious")
    rows = []
    for row in filtered:
        if not row["valid"]:
            hidden[row["action"]] += 1
            continue
        catalog = catalog_for_row(selected, row)
        catalog = route_catalog(catalog, row["recipe_id"], prices, graph)
        recipe = catalog["recipes_by_id"][row["recipe_id"]]
        if makers is not None:
            makes = projection["character"] and row.get("craft_status") in ("Known", "Train now")
            row["made_by"] = projection["character"][0] if makes else next(iter(row.get("who_can_make_it", [])), None)
        row = {**row, 'holding_steps': today_holdings.route_evidence(catalog, prices, row),
               'holding_consumers': today_holdings.consumers(catalog, row)}
        for choice in [*row['shopping_choices'], *row['holding_steps']]:
            price = sales.get(choice['item_id'])
            choice['held_unit_copper'] = _net(price, 1, auction_cut) if price else choice['unit_cost_copper']
        rows.append({**row, "output_quantity": recipe["output_quantity"],
                     "material_names": {p["item_id"]: catalog["items_by_id"][p["item_id"]]["name"]
                                        for p in [*row["shopping_choices"], *row["holding_steps"]]},
                     "recipe_source": recipe["source_url"], "catalog_version": catalog["catalog_version"],
                     "availability": recipe.get("availability", "available"),
                     "evidence_notes": route_notes(catalog, recipe, row),
                     "signal": signals.get(row["output_item_id"]),
                     "price_cap_copper": caps.get(row["output_item_id"])})
    return rows, hidden, board.get("catalog_warnings", [])


def _sort(rows):
    return sorted(rows, key=lambda r: (-r["batch_profit_copper"], r["recipe_id"], r["catalog_id"]))


def _feasible(rows, settings, ladders, reserved, funds, holdings=None):
    feasible, hidden = [], Counter()
    for row in rows:
        sized, reason = _batch(row, settings, ladders, reserved, funds, holdings)
        if sized is None:
            hidden[reason] += 1
        elif sized["batch_profit_copper"] <= 0 or sized["batch_profit_copper"] < settings.minimum_gain:
            hidden["below minimum gain"] += 1
        else:
            feasible.append(sized)
    return _sort(feasible), hidden


def _select(rows, settings, ladders, *, funds=None, reserved=None, shown=None, holdings=None):
    funds = settings.gold_copper if funds is None else funds
    reserved = {} if reserved is None else reserved
    shown = [] if shown is None else shown
    holdings = dict(holdings or {})
    duplicates = Counter()
    while rows and len(shown) < ROW_LIMIT:
        feasible, hidden = _feasible(rows, settings, ladders, reserved, funds, holdings)
        if not feasible:
            return _sort(shown), hidden + duplicates, 0
        best = feasible[0]
        best["plan_order"] = len(shown)
        shown.append(best)
        funds -= today_holdings.gold_cost(best["purchases"])
        _reserve(best, ladders, reserved, holdings)
        duplicates["output already planned"] += sum(
            row["output_item_id"] == best["output_item_id"] for row in rows) - 1
        rows = [row for row in rows if row["output_item_id"] != best["output_item_id"]]
    feasible, hidden = _feasible(rows, settings, ladders, reserved, funds, holdings)
    # Each output is selected at most once, so other routes to the same output are not extra rows.
    return _sort(shown), hidden + duplicates, len({row["output_item_id"] for row in feasible})


def _reserve(row, ladders, reserved, holdings=None):
    for purchase in row["purchases"]:
        if purchase['method'] == 'held':
            holdings[purchase['item_id']] -= purchase['quantity']
        elif purchase["method"] != "vendor" and ladders is not None:
            reserved[purchase["item_id"]] = purchase["end"]


def _chosen_batch(row, size, largest, settings, ladders, reserved, funds, holdings=None):
    if type(size) is not int or not 1 <= size <= largest:
        return None
    holdings = _relevant(row, holdings)
    recommended, _ = _batch(row, settings, ladders, reserved, funds, holdings)
    if recommended is not None and recommended["batch_size"] == size:
        return recommended  # An unchanged size keeps its real limiting factor.
    purchases, steps = _held_quote(row["shopping_choices"], size, ladders, reserved, holdings, row)
    cost = sum(p["cost_copper"] for p in purchases)
    profit = row["net_revenue_copper"] * size - cost
    return {**row, "batch_size": size, "feasible_size": largest, "batch_cost_copper": cost,
            "batch_profit_copper": profit, "profit_per_craft_copper": profit // size,
            "limiting_factor": "chosen batch", "purchases": purchases,
            **_held_batch(purchases, steps)}


def _choose(rows, choices, settings, ladders, refill, holdings=None):
    """Reserve exact choices in supplied plan order, then refill only untouched outputs."""
    indexed = {(r["catalog_id"], r["recipe_id"]): r for r in rows}
    funds, reserved, shown, excluded, dropped = settings.gold_copper, {}, [], set(), []
    holdings = dict(holdings or {})
    limits = {}
    for choice in choices:
        row = indexed.get((choice["catalog_id"], choice["recipe_id"]))
        if row is not None:
            excluded.add(row["output_item_id"])
        limits[(choice["catalog_id"], choice["recipe_id"])] = (
            _largest(row["shopping_choices"], settings.max_crafts, ladders, reserved, funds,
                     _relevant(row, holdings), row) if row else 0)
        size = choice["batch_size"]
        if size is None:
            continue
        sized, reason = _chosen(row, size, limits[(choice["catalog_id"], choice["recipe_id"])], settings,
                                ladders, reserved, funds, shown, holdings)
        if sized is None:
            dropped.append({**choice, "reason": f"{reason}; dropped, not resized."})
            continue
        sized["plan_order"] = len(shown)
        shown.append(sized)
        funds -= today_holdings.gold_cost(sized["purchases"])
        _reserve(sized, ladders, reserved, holdings)
    remaining = [r for r in rows if r["output_item_id"] not in excluded]
    if refill:
        crafts, hidden, rest = _select(remaining, settings, ladders, funds=funds, reserved=reserved,
                                       shown=shown, holdings=holdings)
    else:
        feasible, hidden = _feasible(remaining, settings, ladders, reserved, funds, holdings)
        crafts, rest = _sort(shown), len({row["output_item_id"] for row in feasible})
    return crafts, hidden, rest, dropped, limits


def _chosen(row, size, largest, settings, ladders, reserved, funds, shown, holdings):
    if row is None:
        return None, "Recipe is no longer in today's candidates"
    if row["output_item_id"] in {r["output_item_id"] for r in shown}:
        return None, "Output is already planned"
    if len(shown) >= ROW_LIMIT:
        return None, f"Plan already has {ROW_LIMIT} crafts"
    sized = _chosen_batch(row, size, largest, settings, ladders, reserved, funds, holdings)
    return sized, "Choice is no longer feasible"


def _shopping(rows, metrics):
    grouped = {}
    for row in rows:
        for purchase in row["purchases"]:
            if purchase["method"] == "held":
                continue
            key = (purchase["item_id"], purchase["method"])
            entry = grouped.setdefault(key, {"item_id": key[0], "method": key[1], "quantity": 0,
                                            "purchased_units": 0, "cost_copper": 0, "highest_unit_copper": 0})
            for field in ("quantity", "purchased_units", "cost_copper"):
                entry[field] += purchase[field]
            entry["highest_unit_copper"] = max(entry["highest_unit_copper"], purchase["highest_unit_copper"])
    for entry in grouped.values():
        metric = (metrics or {}).get(entry["item_id"], {})
        percentile = metric.get("unit_buyout_p25")
        entry["p25_copper"] = percentile
        entry["cheap_now"] = (entry["method"] != "vendor" and percentile is not None
                              and entry["cost_copper"] < percentile * entry["purchased_units"])
    return sorted(grouped.values(), key=lambda r: (-r["cost_copper"], r["item_id"], r["method"]))


SILVER = 100


def undercut_price(lowest, max_stack_size):
    """The highest postable unit price below the lowest; unstackable items post in whole silver (Today → Sell)."""
    if lowest is None or lowest <= 1:
        return None
    if max_stack_size == 1:
        return (lowest - 1) // SILVER * SILVER or None
    return lowest - 1


def _sell(row, metrics, auction_cut):
    metric = (metrics or {}).get(row["output_item_id"], {})
    lowest = metric.get("min_buyout")
    undercut = undercut_price(lowest, metric.get("max_stack_size"))
    cap = row.get('price_cap_copper')
    if cap is not None and undercut is not None:
        step = SILVER if metric.get('max_stack_size') == 1 else 1
        undercut = min(undercut, cap) // step * step or None
    profit = (_net(undercut, row["output_quantity"], auction_cut) * row["batch_size"] - row["batch_cost_copper"]
              if undercut else None)
    thin = (metric["listings"] < 3 or metric["largest_stack_units"] * 2 >= metric["units"]) if metric else None
    return {"output_item_id": row["output_item_id"], "output_name": row["output_name"],
            "catalog_id": row["catalog_id"], "recipe_id": row["recipe_id"], "batch_size": row["batch_size"],
            "lowest_copper": lowest, "listings": metric.get("listings"), "units": metric.get("units"),
            "largest_stack_units": metric.get("largest_stack_units"), "thin": thin,
            "undercut_copper": undercut, "undercut_batch_profit_copper": profit,
            "price_step": "whole silver" if metric.get("max_stack_size") == 1 else "1c",
            **warning_fields(row), "price_note": PRICE_NOTE if cap is not None else None}


def _vendor(ladders, vendor_prices, minimum):
    rows = []
    for item_id, price in vendor_prices.items():
        ladder = (ladders or {}).get(item_id)
        if ladder is None:
            continue
        end = bisect_left(ladder.prices, price) - 1
        if end < 1:
            continue
        cost, units = ladder.costs[end], ladder.units[end]
        gain = price * units - cost
        if gain > 0 and gain >= minimum:
            rows.append({"item_id": item_id, "purchased_units": units, "cost_copper": cost,
                         "vendor_sell_copper": price, "gain_copper": gain,
                         "highest_unit_copper": ladder.prices[end], "listings": end})
    return sorted(rows, key=lambda r: (-r["gain_copper"], r["item_id"]))


def _public_materials(crafts, holdings):
    for row in crafts:
        if not holdings:
            row['material_names'] = {c['item_id']: row['material_names'][c['item_id']]
                                     for c in row['shopping_choices']}
        row.pop('holding_steps', None)
        if not holdings:
            row.pop('holding_consumers', None)
        for choice in [*row['shopping_choices'], *row['purchases']]:
            choice.pop('held_unit_copper', None)


def _held_evidence(crafts, sells, holdings, units, captures, max_age_hours, auction_cut):
    if holdings:
        today_holdings.allocate(crafts, units, captures, max_age_hours)
        for row in crafts:
            row.pop('holding_consumers', None)
        for row, sell in zip(crafts, sells, strict=True):
            sell.update(held_outputs=row['held_outputs'],
                        held_value_copper=_net(sell['undercut_copper'], sum(u['units'] for u in row['held_outputs']),
                                              auction_cut) if sell['undercut_copper'] else None)
            sell['confidence_reasons'] = row['confidence_reasons']


def _deposits(crafts, sells, vendor_prices, stack_sizes, metrics, hours, faction):
    """Every posted unit, held ones included; stack size from the scan's item references, any listing."""
    for craft, sell in zip(crafts, sells, strict=True):
        item = sell['output_item_id']
        quantity = craft['output_quantity'] * craft['batch_size'] + sum(
            u['units'] for u in sell.get('held_outputs', []))
        stack = (stack_sizes or {}).get(item, metrics.get(item, {}).get('max_stack_size'))
        sell['post_duration_hours'] = hours
        sell['deposit_copper'] = auction_deposit(vendor_prices.get(item), quantity, stack, hours, faction)


def build_today(catalogs, observations, market, snapshot, settings: TodaySettings, *, now,
                listings=None, metrics=None, vendor_prices=None, stack_sizes=None, max_age_hours=24, auction_cut=.05,
                choices=None, refill=True, character_data=None, flood_evidence=None, holdings_data=None,
                holdings_warning=None, sales_data=None):
    if any(snapshot.get(key) != market.get(key) for key in MARKET_KEYS):
        raise ValueError("The snapshot belongs to a different market")
    for key in ("source_id", "rules_version"):
        if key in snapshot and snapshot[key] != market.get(key):
            raise ValueError(f"The snapshot belongs to a different {key}")
    freshness = assess(snapshot, now, max_age_hours)
    ladders = {i: Ladder(rows) for i, rows in listings.items()} if listings is not None else None
    projection = project_recipes(compatible_catalogs(catalogs, market), character_data or {},
                                 settings.character, settings.include_unknown)
    makers = team_makeable(compatible_catalogs(catalogs, market), character_data or {})
    candidates, hidden, warnings = _candidates(catalogs, observations, market, snapshot, now,
                                              max_age_hours, auction_cut, projection, makers,
                                              base_signals(flood_evidence))
    holdings, captures, units = today_holdings.scoped(holdings_data, projection["character"])
    dropped, limits = [], {}
    if choices is None:
        crafts, excluded, rest = _select(candidates, settings, ladders, holdings=holdings)
    else:
        crafts, excluded, rest, dropped, limits = _choose(candidates, choices, settings, ladders, refill, holdings)
    hidden.update(excluded)
    hidden = +hidden
    _public_materials(crafts, holdings)
    shopping = _shopping(crafts, metrics)
    sells = [_sell(row, metrics, auction_cut) for row in crafts]
    for row, sell in zip(crafts, sells, strict=True):
        sell['your_sales'] = sales.combined(sales_data, row['output_item_id'], projection['character'])
        sell['max_expiries'] = market.get('max_expiries', 3)
        label = confidence(row, sell, freshness, max_age_hours, metrics, ladders)
        row.update(label)
        sell.update(label)
    _held_evidence(crafts, sells, holdings, units, captures, max_age_hours, auction_cut)
    _deposits(crafts, sells, vendor_prices or {}, stack_sizes, metrics or {}, settings.post_duration_hours,
              market['faction'])
    vendors = _vendor(ladders, vendor_prices or {}, settings.minimum_gain)
    evidence = {"stale": freshness["stale"], "actionable": not freshness["stale"],
                "observed_at": freshness["observed_at"], "time_basis": freshness["basis"],
                "source_id": market["source_id"],
                "market_id": market["market_id"], "snapshot_id": snapshot.get("snapshot_id"),
                "scan_id": snapshot.get("scan_id"), "today_version": TODAY_VERSION}
    lists = {"craft": crafts, "buy": shopping, "sell": sells, "below_vendor": vendors}
    return {**{name: [{**row, **evidence} for row in rows[:ROW_LIMIT]] for name, rows in lists.items()},
            "character": projection["character"], "character_note": projection["character_note"],
            **({"holdings_captures": captures} if captures else {}),
            **({"holdings_warning": holdings_warning} if holdings_warning else {}),
            "catalog_checks": projection["catalog_checks"],
            "catalog_warnings": warnings,
            "hidden": dict(hidden), "remaining": {**{name: max(0, len(rows) - ROW_LIMIT)
                                                      for name, rows in lists.items()}, "craft": rest},
            "freshness": freshness, "listing_evidence_available": ladders is not None,
            "minimum_gain_copper": settings.minimum_gain, "today_version": TODAY_VERSION,
            "shopping_total_copper": sum(row["cost_copper"] for row in shopping),
            "dropped_choices": dropped, "refill": refill or choices is None,
            "choice_limits": [{"catalog_id": k[0], "recipe_id": k[1], "maximum": v} for k, v in limits.items()],
            "source_id": market["source_id"], "queue": session_queue(crafts, shopping, sells)}


def apply_removals(plan, removals):
    """Attach shown-output UI-10 evidence after selection; never change prices or reservations."""
    if not removals:
        return plan
    for craft, sell in zip(plan["craft"], plan["sell"], strict=True):
        evidence = removals.get(craft["output_item_id"])
        if evidence is None:
            continue
        for row in (craft, sell):
            row["early_removals"] = evidence
            if evidence["pairs"] >= 3 and evidence["units"] == 0:
                reason = f"no early removals in {evidence['pairs']} scan gaps"
                row["confidence"] = "Low"
                row["confidence_reasons"] = list(dict.fromkeys([reason, *row["confidence_reasons"]]))
    # Buy is cut to ROW_LIMIT, so the queue regroups the crafts' complete reserved purchases.
    # Queue lines copy only quantities and costs, so cheap-now metrics are not needed.
    plan["queue"] = session_queue(plan["craft"], _shopping(plan["craft"], None), plan["sell"])
    return plan


def purchase_uses(crafts):
    """Group reserved purchased units by item/route and output, including stack surplus."""
    uses = {}
    for row in crafts:
        for purchase in row['purchases']:
            if purchase['method'] == 'held':
                continue
            outputs = uses.setdefault((purchase['item_id'], purchase['method']), {})
            name = row['output_name']
            outputs[name] = outputs.get(name, 0) + purchase['purchased_units']
    return uses


def craft_details(row):
    """Project a selected batch's reserved purchases and retained route; never quote again.

    Materials are complete (including Buy's hidden tail), with integer copper costs.
    Intermediate steps are quantities only: their base costs already belong to materials.
    """
    evidence = {key: row[key] for key in ("stale", "actionable")}
    fields = ("item_id", "method", "quantity", "purchased_units", "cost_copper", "highest_unit_copper")
    materials = [{**{key: purchase[key] for key in fields},
                  "item_name": row["material_names"][purchase["item_id"]], **evidence}
                 for purchase in row["purchases"]]
    steps = row.get("reserved_steps")
    if steps is None:
        steps = [{**step, "quantity": step["quantity"] * row["batch_size"],
                  "crafts": step["crafts"] * row["batch_size"]}
                 for step in row["intermediate_steps"]]
    steps = [{**step, **evidence} for step in steps if step["crafts"]]
    return {"materials": materials, "intermediate_steps": steps}


def session_queue(crafts, shopping, sells):
    """Complete queue from reserved purchases and retained routes, including the Buy tail."""
    names = {i: name for row in crafts for i, name in row["material_names"].items()}
    lines = today_holdings.queue_lines(crafts)
    for vendor in (False, True):
        for purchase in shopping:
            if (purchase["method"] == "vendor") == vendor:
                lines.append({**{key: purchase[key] for key in ("item_id", "quantity", "purchased_units",
                                                             "cost_copper", "highest_unit_copper")},
                              "stage": "vendor" if vendor else "auction house",
                              "name": names[purchase["item_id"]], **purchase_confidence(crafts, purchase)})
    for row in sorted(crafts, key=lambda r: r["plan_order"]):
        # Retained preorder/depth identifies each branch of the catalog route.
        for step in _route_order(row.get("reserved_steps", row["intermediate_steps"])):
            if not step["crafts"]:
                continue
            lines.append({"stage": "craft", "name": step["item_name"], "recipe_id": step["recipe_id"],
                          "catalog_id": step.get("catalog_id", row["catalog_id"]),
                          "profession": step.get("profession"), "made_by": step.get("made_by"),
                          "batch_size": step["crafts"] * (1 if "reserved_steps" in row else row["batch_size"]),
                          **_confidence_fields(row)})
        lines.append({"stage": "craft", "name": row["output_name"], "recipe_id": row["recipe_id"],
                      "catalog_id": row["catalog_id"], "batch_size": row["batch_size"],
                      "profession": row["profession"],
                      "made_by": row.get("made_by"), **_confidence_fields(row)})
    for row, sell in zip(crafts, sells, strict=True):
        lines.append({"stage": "post", "name": row["output_name"],
                      "quantity": row["output_quantity"] * row["batch_size"],
                      **({"held_outputs": sell["held_outputs"], "held_value_copper": sell["held_value_copper"]}
                         if "held_outputs" in sell else {}),
                      "deposit_copper": sell["deposit_copper"], "post_duration_hours": sell["post_duration_hours"],
                      "unit_copper": sell["undercut_copper"], "profit_copper": sell["undercut_batch_profit_copper"],
                      **_confidence_fields(row), **warning_fields(sell)})
    profits = [s["undercut_batch_profit_copper"] for s in sells]
    deposits = [s["deposit_copper"] for s in sells]
    return {"mail_note": "Mail between characters is not charged; postage is unconfirmed on Forever.",
            "deposits_to_post_copper": sum(deposits) if all(d is not None for d in deposits) else None,
            "lines": lines, "gold_needed_copper": sum(p["cost_copper"] for p in shopping),
            "expected_profit_copper": sum(profits) if all(p is not None for p in profits) else None}


def _route_order(steps):
    ordered, pending = [], []
    for step in steps:
        while pending and pending[-1]["depth"] >= step["depth"]:
            ordered.append(pending.pop())
        pending.append(step)
    return ordered + list(reversed(pending))


def _confidence_fields(row):
    return {key: row[key] for key in ("confidence", "confidence_reasons") if key in row}
