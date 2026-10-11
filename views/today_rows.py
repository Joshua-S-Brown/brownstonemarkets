"""Framework-free Today table projections; copper conversion uses money.py."""
from brownstone.money import format_money, to_gold


def _evidence(row):
    return {"State": "stale — inspect only" if row["stale"] else "potential gain"}



def craft_row(row, sell):
    return {"Item": row["output_name"], "Profession": row["profession"].title(), "Catalog": row["catalog_id"],
            "Recipe": row["recipe_id"], "Batch": row["batch_size"], "Limited by": row["limiting_factor"],
            "Material cost (g)": to_gold(row["batch_cost_copper"]),
            "Batch profit (g)": to_gold(row["batch_profit_copper"]),
            "Profit per craft (g)": to_gold(row["profit_per_craft_copper"]),
            "Cautious output unit (g)": to_gold(row["sale_price_copper"]), "Listings": sell["listings"],
            "Units": sell["units"], "Thin": sell["thin"], "Availability": row["availability"],
            "Evidence notes": "; ".join(row["evidence_notes"]), "Recipe source": row["recipe_source"],
            **_character_columns(row), **_confidence_columns(row), **_evidence(row)}


def _character_columns(row):
    if "craft_status" not in row:
        return {"Who can make it": ", ".join(row.get("who_can_make_it", [])) or "unknown"}
    learning = row["character_reason"]
    if row["craft_status"] == "Train now":
        cost = row["training_cost_copper"]
        learning = "Training: " + (format_money(cost) if cost is not None else "cost unknown")
    return {"Can make": row["craft_status"], "Learning": learning}


def sell_row(row):
    return {"Output": row["output_name"], "Catalog": row["catalog_id"], "Recipe": row["recipe_id"],
            "Batch": row["batch_size"], "Lowest competing unit (g)": to_gold(row["lowest_copper"]),
            "Listings": row["listings"], "Units": row["units"], "Largest stack units": row["largest_stack_units"],
            "Undercut unit (g)": to_gold(row["undercut_copper"]),
            "Profit at undercut for batch (g)": to_gold(row["undercut_batch_profit_copper"]),
            "Thin": row["thin"], **_confidence_columns(row), **_evidence(row)}


def _confidence_columns(row):
    return {"Confidence": row["confidence"], "Reasons": ", ".join(row["confidence_reasons"])}


