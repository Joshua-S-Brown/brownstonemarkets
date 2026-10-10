"""Today v4: transparent batch estimates and one funded, supply-reserved plan.

Routes remain catalog-local board choices. Prefix ladders price complete stacks in O(log n),
without expanding units; the clock and all scoped evidence are supplied by the caller.
"""
from bisect import bisect_left
from collections import Counter
from decimal import Decimal

from .action_board import catalog_for_row, compatible_catalogs, rank_catalogs
from .freshness import assess
from .markets import MARKET_KEYS
from .today_characters import filter_candidates, project_recipes
from .today_confidence import confidence, purchase_confidence, route_notes
from .today_settings import TodaySettings

TODAY_VERSION = 4
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


def _quote(choices, batch, ladders, reserved):
    result = []
    for choice in choices:
        item_id = choice["item_id"]
        quantity = choice["quantity"] * batch
        if ladders is None or choice["method"] == "vendor":
            unit = choice["unit_cost_copper"]
            quote = {"cost_copper": unit * quantity, "purchased_units": quantity,
                     "highest_unit_copper": unit, "end": 0}
        else:
            ladder = ladders.get(item_id)
            quote = ladder.quote(quantity, reserved.get(item_id, 0)) if ladder else None
        if quote is None:
            return None
        result.append({**choice, **quote, "quantity": quantity})
    return result


def _largest(choices, cap, ladders, reserved, funds):
    low, high = 0, cap
    while low < high:
        middle = (low + high + 1) // 2
        quote = _quote(choices, middle, ladders, reserved)
        if quote is not None and sum(q["cost_copper"] for q in quote) <= funds:
            low = middle
        else:
            high = middle - 1
    return low


def _profit_peaks(choices, largest, ladders, reserved):
    """Batch sizes where profit can peak: the largest, or the last size before any input needs another listing.

    Between those sizes every input's cost is constant while revenue rises, so no other size can be better.
    """
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


def _batch(row, settings, ladders, reserved, funds):
    choices = row["shopping_choices"]
    largest = _largest(choices, settings.max_crafts, ladders, reserved, funds)
    if not largest:
        first = _quote(choices, 1, ladders, reserved)
        return None, "insufficient listed materials" if first is None else "one craft exceeds funds"
    quotes = {size: _quote(choices, size, ladders, reserved)
              for size in _profit_peaks(choices, largest, ladders, reserved)}
    profits = {size: row["net_revenue_copper"] * size - sum(q["cost_copper"] for q in quote)
               for size, quote in quotes.items()}
    size = max(profits, key=lambda s: (profits[s], -s))  # Equal profit: the smaller batch spends less.
    if size < largest:
        limit = "more crafts lower profit"
    elif size == settings.max_crafts:
        limit = "per-item cap"
    else:
        limit = "listed materials" if _quote(choices, size + 1, ladders, reserved) is None else "gold available"
    profit = profits[size]
    return {**row, "batch_size": size, "batch_cost_copper": row["net_revenue_copper"] * size - profit,
            "batch_profit_copper": profit, "profit_per_craft_copper": profit // size,
            "limiting_factor": limit, "feasible_size": largest, "purchases": quotes[size]}, None


def _candidates(catalogs, observations, market, snapshot, now, max_age_hours, auction_cut, projection):
    selected = compatible_catalogs(catalogs, market)
    if not selected:
        return [], Counter()
    board = rank_catalogs(selected, observations, market, snapshot, now=now,
                          max_age_hours=max_age_hours, auction_cut=auction_cut)
    filtered, hidden = filter_candidates(board["rows"], projection)
    rows = []
    for row in filtered:
        if not row["valid"]:
            hidden[row["action"]] += 1
            continue
        catalog = catalog_for_row(selected, row)
        recipe = catalog["recipes_by_id"][row["recipe_id"]]
        rows.append({**row, "output_quantity": recipe["output_quantity"],
                     "material_names": {p["item_id"]: catalog["items_by_id"][p["item_id"]]["name"]
                                        for p in row["shopping_choices"]},
                     "recipe_source": recipe["source_url"], "catalog_version": catalog["catalog_version"],
                     "availability": recipe.get("availability", "available"),
                     "evidence_notes": route_notes(catalog, recipe, row)})
    return rows, hidden


def _sort(rows):
    return sorted(rows, key=lambda r: (-r["batch_profit_copper"], r["recipe_id"], r["catalog_id"]))


def _feasible(rows, settings, ladders, reserved, funds):
    feasible, hidden = [], Counter()
    for row in rows:
        sized, reason = _batch(row, settings, ladders, reserved, funds)
        if sized is None:
            hidden[reason] += 1
        elif sized["batch_profit_copper"] <= 0 or sized["batch_profit_copper"] < settings.minimum_gain:
            hidden["below minimum gain"] += 1
        else:
            feasible.append(sized)
    return _sort(feasible), hidden


def _select(rows, settings, ladders, *, funds=None, reserved=None, shown=None):
    funds = settings.gold_copper if funds is None else funds
    reserved = {} if reserved is None else reserved
    shown = [] if shown is None else shown
    duplicates = Counter()
    while rows and len(shown) < ROW_LIMIT:
        feasible, hidden = _feasible(rows, settings, ladders, reserved, funds)
        if not feasible:
            return _sort(shown), hidden + duplicates, 0
        best = feasible[0]
        best["plan_order"] = len(shown)
        shown.append(best)
        funds -= best["batch_cost_copper"]
        _reserve(best, ladders, reserved)
        duplicates["output already planned"] += sum(
            row["output_item_id"] == best["output_item_id"] for row in rows) - 1
        rows = [row for row in rows if row["output_item_id"] != best["output_item_id"]]
    feasible, hidden = _feasible(rows, settings, ladders, reserved, funds)
    # Each output is selected at most once, so other routes to the same output are not extra rows.
    return _sort(shown), hidden + duplicates, len({row["output_item_id"] for row in feasible})


def _reserve(row, ladders, reserved):
    for purchase in row["purchases"]:
        if purchase["method"] != "vendor" and ladders is not None:
            reserved[purchase["item_id"]] = purchase["end"]


def _chosen_batch(row, size, largest, settings, ladders, reserved, funds):
    if type(size) is not int or not 1 <= size <= largest:
        return None
    recommended, _ = _batch(row, settings, ladders, reserved, funds)
    if recommended is not None and recommended["batch_size"] == size:
        return recommended  # An unchanged size keeps its real limiting factor.
    purchases = _quote(row["shopping_choices"], size, ladders, reserved)
    cost = sum(p["cost_copper"] for p in purchases)
    profit = row["net_revenue_copper"] * size - cost
    return {**row, "batch_size": size, "feasible_size": largest, "batch_cost_copper": cost,
            "batch_profit_copper": profit, "profit_per_craft_copper": profit // size,
            "limiting_factor": "chosen batch", "purchases": purchases}


def _choose(rows, choices, settings, ladders, refill):
    """Reserve exact choices in supplied plan order, then refill only untouched outputs."""
    indexed = {(r["catalog_id"], r["recipe_id"]): r for r in rows}
    funds, reserved, shown, excluded, dropped = settings.gold_copper, {}, [], set(), []
    limits = {}
    for choice in choices:
        row = indexed.get((choice["catalog_id"], choice["recipe_id"]))
        if row is not None:
            excluded.add(row["output_item_id"])
        limits[(choice["catalog_id"], choice["recipe_id"])] = (
            _largest(row["shopping_choices"], settings.max_crafts, ladders, reserved, funds) if row else 0)
        size = choice["batch_size"]
        if size is None:
            continue
        sized, reason = _chosen(row, size, limits[(choice["catalog_id"], choice["recipe_id"])], settings,
                                ladders, reserved, funds, shown)
        if sized is None:
            dropped.append({**choice, "reason": f"{reason}; dropped, not resized."})
            continue
        sized["plan_order"] = len(shown)
        shown.append(sized)
        funds -= sized["batch_cost_copper"]
        _reserve(sized, ladders, reserved)
    remaining = [r for r in rows if r["output_item_id"] not in excluded]
    if refill:
        crafts, hidden, rest = _select(remaining, settings, ladders, funds=funds, reserved=reserved, shown=shown)
    else:
        feasible, hidden = _feasible(remaining, settings, ladders, reserved, funds)
        crafts, rest = _sort(shown), len({row["output_item_id"] for row in feasible})
    return crafts, hidden, rest, dropped, limits


def _chosen(row, size, largest, settings, ladders, reserved, funds, shown):
    if row is None:
        return None, "Recipe is no longer in today's candidates"
    if row["output_item_id"] in {r["output_item_id"] for r in shown}:
        return None, "Output is already planned"
    if len(shown) >= ROW_LIMIT:
        return None, f"Plan already has {ROW_LIMIT} crafts"
    sized = _chosen_batch(row, size, largest, settings, ladders, reserved, funds)
    return sized, "Choice is no longer feasible"


def _shopping(rows, metrics):
    grouped = {}
    for row in rows:
        for purchase in row["purchases"]:
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


def _sell(row, metrics, auction_cut):
    metric = (metrics or {}).get(row["output_item_id"], {})
    lowest = metric.get("min_buyout")
    undercut = lowest - 1 if lowest is not None and lowest > 1 else None
    profit = (_net(undercut, row["output_quantity"], auction_cut) * row["batch_size"] - row["batch_cost_copper"]
              if undercut else None)
    thin = (metric["listings"] < 3 or metric["largest_stack_units"] * 2 >= metric["units"]) if metric else None
    return {"output_item_id": row["output_item_id"], "output_name": row["output_name"],
            "catalog_id": row["catalog_id"], "recipe_id": row["recipe_id"], "batch_size": row["batch_size"],
            "lowest_copper": lowest, "listings": metric.get("listings"), "units": metric.get("units"),
            "largest_stack_units": metric.get("largest_stack_units"), "thin": thin,
            "undercut_copper": undercut, "undercut_batch_profit_copper": profit}


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


def build_today(catalogs, observations, market, snapshot, settings: TodaySettings, *, now,
                listings=None, metrics=None, vendor_prices=None, max_age_hours=24, auction_cut=.05,
                choices=None, refill=True, character_data=None):
    if any(snapshot.get(key) != market.get(key) for key in MARKET_KEYS):
        raise ValueError("The snapshot belongs to a different market")
    for key in ("source_id", "rules_version"):
        if key in snapshot and snapshot[key] != market.get(key):
            raise ValueError(f"The snapshot belongs to a different {key}")
    freshness = assess(snapshot, now, max_age_hours)
    ladders = {i: Ladder(rows) for i, rows in listings.items()} if listings is not None else None
    projection = project_recipes(compatible_catalogs(catalogs, market), character_data or {}, settings.character)
    candidates, hidden = _candidates(catalogs, observations, market, snapshot, now,
                                     max_age_hours, auction_cut, projection)
    dropped, limits = [], {}
    if choices is None:
        crafts, excluded, rest = _select(candidates, settings, ladders)
    else:
        crafts, excluded, rest, dropped, limits = _choose(candidates, choices, settings, ladders, refill)
    hidden.update(excluded)
    hidden = +hidden
    shopping = _shopping(crafts, metrics)
    sells = [_sell(row, metrics, auction_cut) for row in crafts]
    for row, sell in zip(crafts, sells, strict=True):
        label = confidence(row, sell, freshness, max_age_hours, metrics, ladders)
        row.update(label)
        sell.update(label)
    vendors = _vendor(ladders, vendor_prices or {}, settings.minimum_gain)
    evidence = {"stale": freshness["stale"], "actionable": not freshness["stale"],
                "observed_at": freshness["observed_at"], "time_basis": freshness["basis"],
                "source_id": market["source_id"],
                "market_id": market["market_id"], "snapshot_id": snapshot.get("snapshot_id"),
                "scan_id": snapshot.get("scan_id"), "today_version": TODAY_VERSION}
    lists = {"craft": crafts, "buy": shopping, "sell": sells, "below_vendor": vendors}
    return {**{name: [{**row, **evidence} for row in rows[:ROW_LIMIT]] for name, rows in lists.items()},
            "character": projection["character"], "catalog_checks": projection["catalog_checks"],
            "hidden": dict(hidden), "remaining": {**{name: max(0, len(rows) - ROW_LIMIT)
                                                      for name, rows in lists.items()}, "craft": rest},
            "freshness": freshness, "listing_evidence_available": ladders is not None,
            "minimum_gain_copper": settings.minimum_gain, "today_version": TODAY_VERSION,
            "shopping_total_copper": sum(row["cost_copper"] for row in shopping),
            "dropped_choices": dropped, "refill": refill or choices is None,
            "choice_limits": [{"catalog_id": k[0], "recipe_id": k[1], "maximum": v} for k, v in limits.items()],
            "source_id": market["source_id"], "queue": session_queue(crafts, shopping, sells)}


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
    steps = [{**step, "quantity": step["quantity"] * row["batch_size"],
              "crafts": step["crafts"] * row["batch_size"], **evidence}
             for step in row["intermediate_steps"]]
    return {"materials": materials, "intermediate_steps": steps}


def session_queue(crafts, shopping, sells):
    """Complete queue from reserved purchases and retained routes, including the Buy tail."""
    names = {i: name for row in crafts for i, name in row["material_names"].items()}
    lines = []
    for vendor in (False, True):
        for purchase in shopping:
            if (purchase["method"] == "vendor") == vendor:
                lines.append({**{key: purchase[key] for key in ("item_id", "quantity", "purchased_units",
                                                             "cost_copper", "highest_unit_copper")},
                              "stage": "vendor" if vendor else "auction house",
                              "name": names[purchase["item_id"]], **purchase_confidence(crafts, purchase)})
    for row in sorted(crafts, key=lambda r: r["plan_order"]):
        # Retained preorder/depth identifies each branch of the catalog route.
        for step in _route_order(row["intermediate_steps"]):
            lines.append({"stage": "craft", "name": step["item_name"], "recipe_id": step["recipe_id"],
                          "catalog_id": row["catalog_id"], "batch_size": step["crafts"] * row["batch_size"],
                          **_confidence_fields(row)})
        lines.append({"stage": "craft", "name": row["output_name"], "recipe_id": row["recipe_id"],
                      "catalog_id": row["catalog_id"], "batch_size": row["batch_size"], **_confidence_fields(row)})
    for row, sell in zip(crafts, sells, strict=True):
        lines.append({"stage": "post", "name": row["output_name"],
                      "quantity": row["output_quantity"] * row["batch_size"],
                      "unit_copper": sell["undercut_copper"], "profit_copper": sell["undercut_batch_profit_copper"],
                      **_confidence_fields(row)})
    profits = [s["undercut_batch_profit_copper"] for s in sells]
    return {"lines": lines, "gold_needed_copper": sum(p["cost_copper"] for p in shopping),
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
