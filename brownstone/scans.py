"""BrownstoneScan SavedVariables: parse, validate, check the house and derive unit prices.

Pure functions over bytes and records; no files, database or clock. The format is documented in
``addon/README.md`` and the decisions (stack pricing, market value, partial scans) in
``docs/requirements.md`` → ADDON rules.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import polars as pl

SCAN_SCHEMA_VERSION = 1
# market_value is the price of the unit at this quantity-weighted percentile (nearest rank).
MARKET_VALUE_PERCENTILE = 25
# Configurable house evidence and where each value lives in a scan.
EVIDENCE_FIELDS = {
    "faction": ("faction", "player"), "auctioneer": ("house", "npc_name"), "zone": ("house", "zone"),
    "realm": ("realm", "name"), "label": ("label",),
}

# The SavedVariables subset WoW writes: one top-level assignment per table, string or integer keys,
# strings, numbers, booleans and nil. A keyed scalar (`["quantity"] = 20,`) is one token, which keeps
# a 100,000-listing file fast to parse in pure Python.
_SCALAR = r'"(?:[^"\\]|\\.)*"|true|false|nil|-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?'
_TOKEN = re.compile(rf"""\s*(?:
    \[\s*(?:"(?P<skey>(?:[^"\\]|\\.)*)"|(?P<ikey>-?\d+))\s*\]\s*=\s*(?:(?P<keyed>{_SCALAR})|(?P<keyed_table>\{{))
  | (?P<name>[A-Za-z_]\w*)\s*=\s*\{{
  | (?P<value>{_SCALAR})
  | (?P<table>\{{)
  | (?P<close>\}})
)\s*[,;]?\s*""", re.X | re.S)
_ESCAPE = re.compile(r"\\(\d{1,3}|\n|.)", re.S)
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
            "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


def _unescape(match: re.Match) -> str:
    code = match.group(1)
    if code.isdigit():
        if int(code) > 127:
            raise ValueError("Non-ASCII decimal escapes are not supported")
        return chr(int(code))
    if code not in _ESCAPES:
        raise ValueError(f"Unsupported string escape \\{code}")
    return _ESCAPES[code]


def _scalar(text: str) -> Any:
    if text[0] == '"':
        body = text[1:-1]
        return _ESCAPE.sub(_unescape, body) if "\\" in body else body
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "nil":
        return None
    return float(text) if any(c in text for c in ".eE") else int(text)


def _finish(table: dict) -> Any:
    """A table whose keys are exactly 1..n becomes a list; anything else stays a dict (empty: {})."""
    if table and type(next(iter(table))) is int and list(table) == list(range(1, len(table) + 1)):
        return list(table.values())
    return table


def parse_lua(text: str) -> dict[str, Any]:
    """Parse SavedVariables text into {global name: value}. Raises ValueError on anything else."""
    result: dict[str, Any] = {}
    frames: list[list] = []  # [table, key in parent, next positional index]
    pos, end = 0, len(text)
    while pos < end:
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise ValueError(f"Unexpected SavedVariables content at character {pos}")
        pos = match.end()
        kind = match.lastgroup
        if kind == "name":
            if frames:
                raise ValueError(f"Unexpected assignment at character {match.start()}")
            frames.append([{}, match["name"], 1])
            continue
        if not frames:
            raise ValueError(f"Value outside a table at character {match.start()}")
        frame = frames[-1]
        if kind in ("keyed", "keyed_table"):
            key: Any = match["skey"] if match["ikey"] is None else int(match["ikey"])
            if isinstance(key, str) and "\\" in key:
                key = _ESCAPE.sub(_unescape, key)
            if kind == "keyed":
                frame[0][key] = _scalar(match["keyed"])
            else:
                frames.append([{}, key, 1])
        elif kind == "value":
            frame[0][frame[2]] = _scalar(match["value"])
            frame[2] += 1
        elif kind == "table":
            frames.append([{}, frame[2], 1])
            frame[2] += 1
        else:  # close
            table, key, _ = frames.pop()
            if frames:
                frames[-1][0][key] = _finish(table)
            else:
                result[key] = _finish(table)
    if frames:
        raise ValueError("SavedVariables ended inside a table")
    return result


def _list(value: Any, what: str) -> list:
    if value is None or value == {}:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{what} must be a list")
    return value


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def read_saved_variables(raw: bytes) -> list[dict]:
    """Every scan in a BrownstoneScan SavedVariables file, in file order."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"SavedVariables file is not UTF-8: {error}") from error
    database = parse_lua(text).get("BrownstoneScanDB")
    if not isinstance(database, dict):
        raise ValueError("No BrownstoneScanDB table in this file")
    if database.get("schema_version") != SCAN_SCHEMA_VERSION:
        raise ValueError(f"Unsupported BrownstoneScanDB schema_version {database.get('schema_version')!r}")
    scans = _list(database.get("scans"), "scans")
    ids = [scan.get("scan_id") if isinstance(scan, dict) else None for scan in scans]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate scan_id in file")
    return scans


def _evidence(scan: dict, field: str) -> Any:
    value: Any = scan
    for part in EVIDENCE_FIELDS[field]:
        value = _dict(value).get(part)
    return value


def _utc(seconds: Any, text: Any, what: str) -> datetime:
    if type(seconds) is not int:
        raise ValueError(f"{what} must be integer Unix seconds")
    moment = datetime.fromtimestamp(seconds, UTC)
    if text is not None and text != moment.strftime("%Y-%m-%dT%H:%M:%SZ"):
        raise ValueError(f"{what} {seconds} disagrees with {what}_utc {text!r}")
    return moment


def summarize(scan: dict) -> dict:
    """Validate one scan's header and return its metadata. Listings are checked in ``listing_frame``."""
    scan_id = scan.get("scan_id")
    if not isinstance(scan_id, str) or not scan_id:
        raise ValueError("Every scan needs a scan_id")
    if scan.get("schema_version") != SCAN_SCHEMA_VERSION:
        raise ValueError(f"Scan {scan_id}: unsupported schema_version {scan.get('schema_version')!r}")
    status = scan.get("status")
    if status not in ("completed", "stopped"):
        raise ValueError(f"Scan {scan_id}: unknown status {status!r}")
    listings = _list(scan.get("listings"), f"Scan {scan_id} listings")
    if scan.get("listing_count") != len(listings):
        raise ValueError(f"Scan {scan_id}: listing_count {scan.get('listing_count')!r} "
                         f"but {len(listings)} listings saved")
    reported = scan.get("reported_count")
    client = _dict(scan.get("client"))
    house = _dict(scan.get("house"))
    faction = _dict(scan.get("faction"))
    return {
        "scan_id": scan_id, "status": status, "stop_reason": scan.get("stop_reason"),
        # Stopped, or the server reported more than was saved: prices could miss the cheapest listing.
        "partial": status != "completed" or reported != len(listings),
        "started_at": _utc(scan.get("started_at"), scan.get("started_at_utc"), "started_at"),
        "finished_at": _utc(scan.get("finished_at"), scan.get("finished_at_utc"), "finished_at"),
        "listing_count": len(listings), "reported_count": reported if type(reported) is int else None,
        "api": scan.get("api"), "client_version": client.get("version"),
        "client_build": None if client.get("build") is None else str(client.get("build")),
        "player_faction": faction.get("player"), "neutral": faction.get("neutral"),
        "auctioneer": house.get("npc_name"), "zone": house.get("zone"), "subzone": house.get("subzone"),
        "realm_name": _dict(scan.get("realm")).get("name"), "label": scan.get("label"),
        "errors": [str(e) for e in _list(scan.get("errors"), f"Scan {scan_id} errors")],
        "scan_sha256": hashlib.sha256(json.dumps(scan, sort_keys=True, separators=(",", ":"))
                                      .encode()).hexdigest(),
    }


def check_house(scan: dict, market: Mapping[str, Any]) -> list[str]:
    """Reasons this scan does not match the configured market; empty when it does.

    The configured source defines the market. The scan's faction, auctioneer, zone, realm and label
    are only evidence checked against it, never used to derive one.
    """
    scan_id = scan.get("scan_id")
    problems = []
    for field, expected in (market.get("scan_evidence") or {}).items():
        observed = _evidence(scan, field)
        if observed != expected:
            problems.append(f"scan {scan_id}: {field} is {observed!r}, configured {expected!r}")
    player = str(_evidence(scan, "faction") or "").lower()
    neutral = _dict(scan.get("faction")).get("neutral")
    configured = market.get("faction", "")
    if configured in ("alliance", "horde"):
        if player != configured:
            problems.append(f"scan {scan_id}: player faction is {player or 'unknown'!r}, market is {configured!r}")
        if neutral is True:
            problems.append(f"scan {scan_id}: taken at a neutral auction house, market is {configured!r}")
    elif configured == "neutral" and neutral is not True and "auctioneer" not in (market.get("scan_evidence") or {}):
        problems.append(f"scan {scan_id}: nothing shows a neutral house; the client did not report one, so "
                        "configure scan_evidence.auctioneer for the neutral auctioneer")
    return problems


LISTING_SCHEMA = {"item_id": pl.Int64, "name": pl.String, "quantity": pl.Int64, "buyout": pl.Int64,
                  "unit_buyout": pl.Int64, "min_bid": pl.Int64, "bid": pl.Int64, "complete_info": pl.Boolean}


def listing_frame(scan: dict) -> pl.DataFrame:
    """One row per listing with exact and rounded-up unit prices, all integer copper.

    ``buyout`` is the whole stack's price. ``unit_buyout`` is kept only when ``buyout / quantity`` is exact;
    ``unit_buyout_ceil`` always rounds up, so a non-exact stack never understates what a unit costs.
    A missing or zero buyout means no buyout price: both unit columns stay null, never zero.
    """
    scan_id = scan["scan_id"]
    listings = _list(scan.get("listings"), f"Scan {scan_id} listings")
    if any(not isinstance(listing, dict) for listing in listings):
        raise ValueError(f"Scan {scan_id}: every listing must be a table")
    try:
        frame = pl.DataFrame({key: [listing.get(key) for listing in listings] for key in LISTING_SCHEMA},
                             schema=LISTING_SCHEMA, strict=True)
    except (TypeError, pl.exceptions.PolarsError) as error:
        raise ValueError(f"Scan {scan_id}: listing fields must be integer copper and counts: {error}") from error
    bad = frame.filter(pl.col("item_id").is_null() | (pl.col("item_id") <= 0)
                       | pl.col("quantity").is_null() | (pl.col("quantity") <= 0)
                       | (pl.col("buyout") < 0) | (pl.col("min_bid") < 0) | (pl.col("bid") < 0))
    if bad.height:
        raise ValueError(f"Scan {scan_id}: {bad.height} listings have a missing item ID or quantity, "
                         "or a negative price")
    buyout = pl.when(pl.col("buyout") > 0).then(pl.col("buyout"))
    exact = buyout % pl.col("quantity") == 0
    frame = frame.with_columns(
        pl.int_range(1, pl.len() + 1, dtype=pl.Int64).alias("listing_index"),
        buyout.alias("buyout"),
        pl.when(pl.col("name") != "").then(pl.col("name")).alias("item_name"),
        pl.col("unit_buyout").alias("reported_unit_buyout"),
        pl.when(exact).then(buyout // pl.col("quantity")).alias("unit_buyout"),
        (-(-buyout // pl.col("quantity"))).alias("unit_buyout_ceil"),
    )
    disagree = frame.filter(pl.col("reported_unit_buyout").is_not_null()
                            & (pl.col("reported_unit_buyout") != pl.col("unit_buyout")).fill_null(True))
    if disagree.height:
        raise ValueError(f"Scan {scan_id}: {disagree.height} listings report a unit_buyout that is not "
                         "buyout / quantity")
    return frame.select("listing_index", "item_id", "item_name", "quantity", "buyout", "unit_buyout",
                        "unit_buyout_ceil", "min_bid", "bid", "complete_info")


def nonexact_stacks(listings: pl.DataFrame) -> int:
    """Listings priced by rounding up because the stack's buyout does not divide exactly."""
    return listings.filter(pl.col("unit_buyout_ceil").is_not_null() & pl.col("unit_buyout").is_null()).height


def item_prices(listings: pl.DataFrame) -> pl.DataFrame:
    """Item-level unit prices in the market_snapshots shape (integer copper; 0 means no buyout listing).

    - ``min_buyout``: the cheapest unit price (rounded up for non-exact stacks).
    - ``market_value``: the unit price at the MARKET_VALUE_PERCENTILE of all listed units, nearest rank,
      weighting each listing by its quantity. Robust to one stray cheap stack and to high listings
      that never sell; similar in spirit to TSM's average of the cheapest 15-30% of units.
    - ``recent_value`` and ``historical_value``: 0; one scan has no history.
    """
    priced = listings.filter(pl.col("unit_buyout_ceil").is_not_null()).sort("item_id", "unit_buyout_ceil")
    target = (pl.col("quantity").sum().over("item_id") * MARKET_VALUE_PERCENTILE + 99) // 100
    prices = (priced.with_columns(pl.col("quantity").cum_sum().over("item_id").alias("units"), target.alias("target"))
              .group_by("item_id").agg(
                  pl.col("unit_buyout_ceil").min().alias("min_buyout"),
                  pl.col("unit_buyout_ceil").filter(pl.col("units") >= pl.col("target")).min().alias("market_value")))
    names = (listings.filter(pl.col("item_name").is_not_null()).group_by("item_id", "item_name").len()
             .sort(["item_id", "len", "item_name"], descending=[False, True, False])
             .unique("item_id", keep="first", maintain_order=True).select("item_id", "item_name"))
    items = listings.select("item_id").unique()
    return (items.join(names, on="item_id", how="left").join(prices, on="item_id", how="left")
            .select(
                "item_id",
                pl.coalesce("item_name", pl.concat_str(pl.lit("Item "), pl.col("item_id").cast(pl.String)))
                .alias("item_name"),
                pl.col("market_value").fill_null(0), pl.col("min_buyout").fill_null(0),
                pl.lit(0, pl.Int64).alias("recent_value"), pl.lit(0, pl.Int64).alias("historical_value"))
            .sort("item_id"))
