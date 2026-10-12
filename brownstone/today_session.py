"""Shared session identity and queue prose; no framework state or calculations."""
import hashlib
import json

from brownstone.money import format_money


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def plan_context(arguments):
    # Listings, observations and metrics are read for the snapshot ID, so the snapshot identifies them.
    context = {key: arguments[key] for key in ("catalogs", "market", "snapshot", "settings",
                                              "max_age_hours", "auction_cut")}
    context["character_data"] = sorted(arguments.get("character_data", {}).items())
    return digest(context)


def queue_line(line):
    text = queue_line_text(line)
    if "confidence" in line:
        reasons = ", ".join(line["confidence_reasons"])
        text += f" · {line['confidence']} confidence" + (f" ({reasons})" if reasons else "")
    return text


def queue_line_text(line):
    stage, name = line["stage"], line["name"]
    if stage in ("auction house", "vendor"):
        return (f"Buy at {stage}: {name} · {line['purchased_units']} units · "
                f"highest unit {format_money(line['highest_unit_copper'])} · total {format_money(line['cost_copper'])}")
    if stage == "craft":
        return f"Craft: {name} · recipe {line['recipe_id']} ({line['catalog_id']}) · {line['batch_size']} crafts"
    price = format_money(line["unit_copper"]) if line["unit_copper"] is not None else "unavailable"
    profit = format_money(line["profit_copper"]) if line["profit_copper"] is not None else "unavailable"
    return f"Post: {name} · {line['quantity']} units · undercut unit {price} · profit {profit}"


