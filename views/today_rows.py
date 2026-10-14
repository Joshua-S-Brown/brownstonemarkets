"""Framework-free Today table projections and wording for the app; copper conversion uses money.py."""
from datetime import UTC, datetime

from brownstone.money import format_money, to_gold

ROW_LIMIT_NOTE = "more rows outside this list's 10-row limit"
SETTINGS_NOTE = "One funded plan · whole auction stacks are bought; surplus is shown · sales speed is unknown"
MISSING_CHARACTER = "Saved character is no longer present in this source and market; showing Our team."
ZERO_GOLD_HINT = "Enter the gold you have available to size the plan. Use explicit units, for example 12g 50s."
NO_SNAPSHOT = "Refresh or import a scan for this market to inspect Today."
NO_LISTINGS = ("Individual listings, thin markets, cheap now, undercuts and below-vendor listings: "
               "not available for this source. Batches use funds and the per-item cap; costs are aggregate estimates.")
PLAN_RESET = ("Scan, settings or catalog evidence changed: session choices and queue ticks reset. "
              "Previous choices were dropped, not resized; a fresh default plan is shown.")
VENDOR_ASIDE = "Independent aside, not part of the craft budget."


def state(row):
    return "stale — inspect only" if row["stale"] else "potential gain"


def unreadable_settings(error):
    return f"Could not read Today settings: {error}. Defaults are shown; save to replace this file."


def provenance(result, config, manifest, snapshot_id):
    freshness = result["freshness"]
    return (f"Today rules v{result['today_version']} · cautious output price · "
            f"{config['auction_cut']:.0%} auction cut · source {config['source_id']} · "
            f"market {config['market_id']} · snapshot {snapshot_id} · "
            f"scan {manifest.get('scan_id', 'not available for this source')} · "
            f"evidence {freshness['observed_at']} (UTC) · time basis {freshness['basis']}")


def hidden_line(counts):
    return "Hidden recipes: " + ("; ".join(f"{reason}: {count}" for reason, count in sorted(counts.items())) or "0")


def shopping_line(result):
    return (f"Whole shopping list: {format_money(result['shopping_total_copper'])}. "
            "Cheap now means average paid is strictly below scan p25; informational only. Vendor stock is unknown.")


def craft_row(row, sell):
    return {"Item": row["output_name"], "Profession": row["profession"].title(), "Catalog": row["catalog_id"],
            "Recipe": row["recipe_id"], "Batch": row["batch_size"], "Limited by": row["limiting_factor"],
            "Material cost (g)": to_gold(row["batch_cost_copper"]),
            "Batch profit (g)": to_gold(row["batch_profit_copper"]),
            "Profit per craft (g)": to_gold(row["profit_per_craft_copper"]),
            "Cautious output unit (g)": to_gold(row["sale_price_copper"]), "Listings": sell["listings"],
            "Units": sell["units"], "Thin": sell["thin"], "Availability": row["availability"],
            "Evidence notes": "; ".join(row["evidence_notes"]), "Recipe source": row["recipe_source"],
            **_character_columns(row), **_confidence_columns(row), "State": state(row)}


def _character_columns(row):
    if "craft_status" not in row:
        return {"Who can make it": ", ".join(row.get("who_can_make_it", [])) or "unknown"}
    learning = row["character_reason"]
    if row["craft_status"] == "Train now":
        cost = row["training_cost_copper"]
        learning = "Training: " + (format_money(cost) if cost is not None else "cost unknown")
    team = {"Who can make it": ", ".join(row.get("who_can_make_it", [])) or "unknown"} if row.get("team") else {}
    return team | {"Can make": row["craft_status"], "Learning": learning}


def sell_row(row):
    return {"Output": row["output_name"], "Catalog": row["catalog_id"], "Recipe": row["recipe_id"],
            "Batch": row["batch_size"], "Lowest competing unit (g)": to_gold(row["lowest_copper"]),
            "Listings": row["listings"], "Units": row["units"], "Largest stack units": row["largest_stack_units"],
            "Undercut unit (g)": to_gold(row["undercut_copper"]), "Price step": row.get("price_step", "1c"),
            "Profit at undercut for batch (g)": to_gold(row["undercut_batch_profit_copper"]),
            "Thin": row["thin"], **_confidence_columns(row), "State": state(row)}


def _confidence_columns(row):
    return {"Confidence": row["confidence"], "Reasons": ", ".join(row["confidence_reasons"])}


def _name(names, item_id):
    return names.get(item_id, f"Item {item_id}")


def buy_row(row, names, *, item_id=False, used_for=None):
    """Project item identity and the crafts purchased units are for."""
    result = {"Material": _name(names, row["item_id"]), **({"Item ID": row["item_id"]} if item_id else {}),
              "Route": row["method"]}
    if used_for is not None:
        result["For"] = used_for
    return result | {"Required units": row["quantity"], "Purchased units": row["purchased_units"],
                     "Cost (g)": to_gold(row["cost_copper"]),
                     "Highest unit price (g)": to_gold(row["highest_unit_copper"]),
                     "Scan p25 (g)": to_gold(row["p25_copper"]), "Cheap now": row["cheap_now"], "State": state(row)}


def vendor_row(row, names, *, item_id=False):
    return {"Item": _name(names, row["item_id"]),
            **({"Item ID": row["item_id"], "Listings": row["listings"]} if item_id else {}),
            "Units": row["purchased_units"], "Cost (g)": to_gold(row["cost_copper"]),
            "Vendor pays per unit (g)": to_gold(row["vendor_sell_copper"]),
            "Highest listing unit (g)": to_gold(row["highest_unit_copper"]), "Gain (g)": to_gold(row["gain_copper"]),
            "State": state(row)}


def material_row(row, *, item_id=False):
    """One reserved purchase from ``today.craft_details``."""
    return {"Material": row["item_name"], **({"Item ID": row["item_id"]} if item_id else {}),
            "Route": "vendor" if row["method"] == "vendor" else "auction house",
            "Required units": row["quantity"], "Purchased units": row["purchased_units"],
            "Cost (g)": to_gold(row["cost_copper"]), "Highest unit price (g)": to_gold(row["highest_unit_copper"]),
            "State": state(row)}


def summary_tiles(result, *, hide_low=False):
    """Display totals from the reserved plan, using Sell's undercut profits without re-quoting.

    Hiding Low confidence filters the shown crafts like the cards; gold needed stays the reserved plan's.
    """
    crafts = [r for r in result['craft'] if not (hide_low and r['confidence'] == 'Low')]
    shown = {r['output_item_id'] for r in crafts} if hide_low else None
    sells = [r for r in result['sell'] if shown is None or r['output_item_id'] in shown]
    valued = [r for r in sells if r['undercut_batch_profit_copper'] is not None]
    best = max(valued, key=lambda r: r['undercut_batch_profit_copper'], default=None)
    profit = (format_money(sum(r['undercut_batch_profit_copper'] for r in valued))
              if len(valued) == len(sells) else 'unavailable')
    return [('Crafts', str(len(crafts))), ('Gold needed', format_money(result['shopping_total_copper'])),
            ('Expected profit', profit), ('Best craft',
             f"{best['output_name']} · {format_money(best['undercut_batch_profit_copper'])}"
             if best else 'none valued')]


def empty_sentence(hidden, minimum_copper, gold_copper):
    """Explain the largest exclusions without claiming knowledge or prices we do not have."""
    reasons = sorted(((reason, count) for reason, count in hidden.items() if count),
                     key=lambda entry: (-entry[1], entry[0]))[:2]
    wording = {
        'no character has this profession': 'your team does not have the required professions',
        'rank below required skill': 'profession ranks are below the required skill',
        'below minimum gain': 'profit is below minimum gain',
        'one craft exceeds funds': 'one craft costs more than the available gold',
        'insufficient listed materials': 'there are not enough listed materials',
        'missing prices': 'prices are missing',
    }
    why = ' Most recipes are hidden because ' + ' and '.join(
        wording.get(r, r) for r, _ in reasons) + '.' if reasons else ''
    return (f"No craft meets the {format_money(minimum_copper)} minimum batch gain with "
            f"{format_money(gold_copper)} available.{why} Review your settings or inspect all reasons.")


def scan_status(freshness):
    """Short age chip; unknown upstream time remains explicit."""
    age = freshness['age_hours']
    if age < 0:
        return 'Scan dated in the future'
    basis = 'Scan' if freshness['upstream_known'] else 'Download (price age unknown)'
    return f'{basis} {age:.0f} hours old'


def stale_banner(freshness):
    if freshness['age_hours'] < 0:
        return 'These prices are dated in the future. Check the clock and scan again before you buy.'
    return 'Prices are from an older scan. Treat this plan as a preview; scan again before you buy.'


def planning_label(character, data):
    if character is None or character not in data:
        return 'Planning for Our team'
    from brownstone.today_characters import profession_rank

    skills = []
    for name, record in data[character].get('recipes', {}).items():
        rank, _ = profession_rank(data[character], record)
        skills.append(f"{name} {rank if rank is not None else 'rank unknown'}")
    return 'Planning for ' + character[0] + (' · ' + ', '.join(skills) if skills else '')


def material_card_rows(materials):
    """Reserved purchases in the approved card table, with in-game money and surplus explicit."""
    return [{'Material': r['item_name'], 'Where': 'Vendor' if r['method'] == 'vendor' else 'Auction house',
             'Units': str(r['purchased_units']) + (f" ({r['quantity']} needed)"
                       if r['purchased_units'] != r['quantity'] else ''),
             'Cost': format_money(r['cost_copper']), 'State': state(r)} for r in materials]


def display_hidden(result, hide_low):
    """Display filtering is counted without changing the reserved plan or its hidden reasons."""
    counts = dict(result['hidden'])
    if hide_low:
        counts['low confidence'] = sum(r['confidence'] == 'Low' for r in result['craft'])
    return counts


def recorded_gold_rows(data, character):
    """Captured balances alongside an entered budget; zero/missing captures remain unknown."""
    identities = [character] if character in data else sorted(data)
    rows = []
    for identity in identities:
        bags = data[identity].get('bags', {})
        gold, captured = bags.get('gold_copper'), bags.get('captured_at')
        readable = type(gold) is int and gold > 0 and type(captured) is int
        rows.append({'Character': ' · '.join(identity),
                     'Recorded gold': format_money(gold) if readable else 'unknown',
                     'Captured (UTC)': datetime.fromtimestamp(captured, UTC).strftime('%Y-%m-%d %H:%M UTC')
                     if type(captured) is int else 'unknown'})
    return rows
