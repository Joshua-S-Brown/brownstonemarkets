"""Read-only merchant evidence; never updates catalog prices or analytical prices."""
from datetime import UTC, datetime

from . import addon_records, recipe_catalogs, scans
from .config import MARKET_KEYS, Source


def vendor_prices(records: list[dict], catalogs: list[dict], config: Source) -> dict:
    """Project matching-house lists against each game/rules-compatible catalog separately."""
    compatible = [c for c in catalogs if all(c.get(k) == config.get(k)
                                            for k in ("game_version", "rules_version"))]
    observations = []
    for record in records:
        if record.get("family") != "vendor" or addon_records.check_house(record, config):
            continue
        for item in scans._list(record.get("merchant_items", []), "merchant items"):
            if isinstance(item, dict):
                observations.append(_observation(record, item, compatible))
    return {"scope": {"source_id": config["source_id"], **{k: dict(config)[k] for k in MARKET_KEYS},
                      "rules_version": config.get("rules_version")}, "observations": observations}


def _observation(record: dict, item: dict, catalogs: list[dict]) -> dict:
    comparisons = []
    for catalog in catalogs:
        marked = catalog["items_by_id"].get(item.get("item_id"), {})
        if item.get("item_id") in catalog["items_by_id"]:
            price = marked.get("vendor_price_copper")
            comparisons.append({"catalog": catalog["catalog_id"], "catalog_version": catalog["catalog_version"],
                                "marked_price_copper": price, "vendor_verified": marked.get("vendor_verified"),
                                "result": _comparison(item, record.get("vendor_standing"), price)})
    return {"entry_id": record["entry_id"],
            "captured_utc": datetime.fromtimestamp(record["captured_at"], UTC).isoformat(),
            "character": record["character"], "vendor_npc_id": record.get("vendor_npc_id"),
            "vendor_guid": record.get("vendor_guid"), "zone": record.get("zone"),
            "standing": record.get("vendor_standing"),
            **{k: item.get(k) for k in ("item_id", "link", "price_copper", "quantity", "stock", "extended_cost")},
            "comparisons": comparisons or [{"catalog": None, "result": _comparison(
                item, record.get("vendor_standing"), None)}]}


def _positive(value) -> bool:
    return type(value) is int and value > 0


def _comparison(item: dict, standing, marked) -> str:
    if item.get("extended_cost") is not False:
        return "extended or unknown cost: evidence only"
    if not _positive(item.get("price_copper")) or not _positive(item.get("quantity")):
        return "missing or zero price/quantity: evidence only"
    # A reputation discount only lowers a price, so equal or higher prices are evidence at any standing.
    full_price = type(standing) is int and 1 <= standing <= 4
    if not _positive(marked):
        return "new" if full_price else "new; discounted or unknown standing: evidence only"
    full = marked * item["quantity"]
    if item["price_copper"] == full:
        return "confirms"
    if item["price_copper"] > full or full_price:
        return "contradicts"
    return "lower; discounted or unknown standing: evidence only"


def catalog_evidence(records: list[dict], config: Source) -> dict:
    catalogs, errors = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(recipe_catalogs.CONFIG_DIR))
    return vendor_prices(records, catalogs, config) | {"catalog_errors": errors}
