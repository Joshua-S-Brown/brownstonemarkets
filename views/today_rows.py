"""Framework-free Today table projections and wording shared by both apps; copper conversion uses money.py."""
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
            "Undercut unit (g)": to_gold(row["undercut_copper"]),
            "Profit at undercut for batch (g)": to_gold(row["undercut_batch_profit_copper"]),
            "Thin": row["thin"], **_confidence_columns(row), "State": state(row)}


def _confidence_columns(row):
    return {"Confidence": row["confidence"], "Reasons": ", ".join(row["confidence_reasons"])}


def _name(names, item_id):
    return names.get(item_id, f"Item {item_id}")


def buy_row(row, names, *, item_id=False, used_for=None):
    """Streamlit shows the item ID after the name; the new app shows which crafts the units are for."""
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
