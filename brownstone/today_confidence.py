"""Today v3 display rules over an already reserved plan; no pricing or selection."""

CONFIDENCE_LOW_SHARE_PERCENT = 75
CONFIDENCE_MEDIUM_SHARE_PERCENT = 40
CONFIDENCE_MEDIUM_LISTINGS = 5
CONFIDENCE_AGE_FRACTION = .5
# Catalog markers (`crafting.py`) shown under the story's short reason words.
_MARKER_REASONS = {"output quantity": "yield", "vendor": "vendor price"}


def route_notes(catalog, recipe, row):
    """Include every retained route recipe and item, without inspecting unused alternatives."""
    recipes = {recipe["recipe_id"], *(s["recipe_id"] for s in row["intermediate_steps"])}
    items = {row["output_item_id"], *row["shopping_list"], *(s["item_id"] for s in row["intermediate_steps"])}
    records = [*(catalog["recipes_by_id"][i] for i in sorted(recipes)),
               *(catalog["items_by_id"][i] for i in sorted(items))]
    return [f"{record.get('name', 'Recipe')}: {key.replace('_', ' ')}"
            for record in records for key, value in record.items()
            if (key.endswith("_verified") and value is False) or (key == "availability" and value == "post-launch")]


def confidence(row, sell, freshness, max_age_hours, metrics, ladders):
    low, medium = [], []
    if freshness["stale"]:
        low.append("stale")
    elif freshness["age_hours"] > max_age_hours * CONFIDENCE_AGE_FRACTION:
        medium.append("older scan")
    if ladders is None or metrics is None:
        medium.append("depth not available for this source")
    else:
        _depth_reasons(row, sell, metrics, ladders, low, medium)
    for note in row["evidence_notes"]:
        if note.endswith("verified"):
            marker = note.rsplit(": ", 1)[-1].removesuffix(" verified")
            medium.append(f"unconfirmed {_MARKER_REASONS.get(marker, marker)}")
    return {"confidence": "Low" if low else "Medium" if medium else "High",
            "confidence_reasons": list(dict.fromkeys([*low, *medium]))}


def _depth_reasons(row, sell, metrics, ladders, low, medium):
    if sell["thin"]:
        low.append("thin")
    if sell["lowest_copper"] is None or sell["lowest_copper"] <= 0:
        low.append("no competing listing")
    if (sell["listings"] or 0) < CONFIDENCE_MEDIUM_LISTINGS:
        medium.append("few listings")
    for purchase in row["purchases"]:
        if purchase["method"] == "vendor" or not purchase["purchased_units"]:
            continue
        units = metrics.get(purchase["item_id"], {}).get("units")
        if not units:
            medium.append("depth not available for this source")
            continue
        # The prefix includes earlier rows' reservations; denominator includes no-buyout units.
        bought = ladders[purchase["item_id"]].units[purchase["end"]]
        if bought * 100 > units * CONFIDENCE_LOW_SHARE_PERCENT:
            low.append("material share >75%")
        elif bought * 100 > units * CONFIDENCE_MEDIUM_SHARE_PERCENT:
            medium.append("material share >40%")


def purchase_confidence(crafts, purchase):
    """A merged Queue buy line carries the worst of its contributing Craft labels."""
    rows = [row for row in crafts if any(p["item_id"] == purchase["item_id"]
            and p["method"] == purchase["method"] for p in row["purchases"])]
    labeled = [row for row in rows if "confidence" in row]
    if not labeled:
        return {}
    worst = max(labeled, key=lambda row: {"High": 0, "Medium": 1, "Low": 2}[row["confidence"]])
    return {"confidence": worst["confidence"],
            "confidence_reasons": list(dict.fromkeys(
                reason for row in labeled for reason in row["confidence_reasons"]))}
