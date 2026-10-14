"""Shared session identity and queue prose; no framework state or calculations."""
import hashlib
import json

from brownstone.money import format_money
from brownstone.recipe_graph import made_by_label
from brownstone.today import TODAY_VERSION


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def plan_context(arguments):
    # Listings, observations and metrics are read for the snapshot ID, so the snapshot identifies them.
    context = {key: arguments[key] for key in ("catalogs", "market", "snapshot", "settings",
                                              "max_age_hours", "auction_cut")}
    context["today_version"] = TODAY_VERSION
    context["character_data"] = sorted(arguments.get("character_data", {}).items())
    evidence = arguments.get('holdings_data')
    context['holdings_data'] = ([{k: v for k, v in c.items() if k != 'age_hours'}
                                 for c in evidence[2]], evidence[3]) if evidence else None
    return digest(context)


def stable_queue(queue):
    """Queue identity without confidence labels, so age transitions keep ticks."""
    return {**queue, "lines": [{k: v for k, v in line.items() if k not in ("confidence", "confidence_reasons")}
                               for line in queue["lines"]]}


def queue_total(queue):
    profit = queue["expected_profit_copper"]
    return (f"Gold needed: {format_money(queue['gold_needed_copper'])} · "
            f"Expected profit at undercut: {format_money(profit) if profit is not None else 'unavailable'}")


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
    if stage == 'take':
        place = 'bank' if line['kind'] == 'bank' else 'bags'
        return f"{line['character']}: take {line['units']} {name} from the {place}"
    if stage == 'mail':
        return f"{line['character']} mails {line['units']} {name} to {line['to']}"
    if stage == "craft":
        maker = f" · {made_by_label(line)}" if line.get("profession") else ""
        return (f"Craft: {name}{maker} · recipe {line['recipe_id']} ({line['catalog_id']}) · "
                f"{line['batch_size']} crafts")
    price = format_money(line["unit_copper"]) if line["unit_copper"] is not None else "unavailable"
    profit = format_money(line["profit_copper"]) if line["profit_copper"] is not None else "unavailable"
    held = line.get('held_outputs', [])
    if held:
        owners = ', '.join(f"{u['character']} ({u['kind']}): {u['units']}" for u in held)
        value = line.get('held_value_copper')
        return (f"Post: {name} · post {line['quantity']} crafted + {sum(u['units'] for u in held)} held "
                f"({owners}) · undercut unit {price} · profit {profit} · held value "
                f"{format_money(value) if value is not None else 'unavailable'}")
    return f"Post: {name} · {line['quantity']} units · undercut unit {price} · profit {profit}"


