"""Ledger JSON adapters over one cached generation of each evidence projection."""

import threading
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, StrictInt

from brownstone import ledger_view, recipe_catalogs, stock

from . import context

router = APIRouter()
_lock = threading.Lock()
_cache: dict[str, tuple[tuple, dict]] = {}


class Target(BaseModel):
    item_id: StrictInt
    target_units: StrictInt
    buy_copper: StrictInt | None = None
    buy_percent: StrictInt | None = None


class Targets(BaseModel):
    entries: list[Target]


class GoldTotal(BaseModel):
    character: tuple[str, str, str]
    day: str
    category: str
    in_copper: int
    out_copper: int


class ItemTotal(BaseModel):
    character: tuple[str, str, str]
    day: str
    category: str
    in_units: int
    out_units: int


class GoldTeam(BaseModel):
    in_copper: int
    out_copper: int
    net_copper: int


class ItemTeam(BaseModel):
    in_units: int
    out_units: int


class Category(BaseModel):
    category: str
    in_copper: int
    out_copper: int


class Day(BaseModel):
    day: str
    in_copper: int
    out_copper: int


class Pairs(BaseModel):
    total: int
    reconciled: int
    unknown: int = 0
    kind: str = "bags"


class GoldPair(BaseModel):
    character: tuple[str, str, str]
    from_utc: str
    to_utc: str
    actual_copper: int | None
    recorded_copper: int | None
    unexplained_copper: int | None
    reason: str | None


class ItemResidual(BaseModel):
    character: tuple[str, str, str]
    item_id: int
    kind: str
    from_utc: str
    to_utc: str
    actual_units: int
    recorded_units: int
    residual_units: int
    possibly_incomplete: bool


class Movement(BaseModel):
    model_config = ConfigDict(extra="allow")
    utc: str
    name: str | None = None
    item_id: int | None = None
    entry_id: str
    machine: str | None


class Gold(BaseModel):
    team: GoldTeam
    totals: list[GoldTotal]
    categories: list[Category]
    daily: list[Day]
    reconciliation: list[GoldPair]
    pairs: Pairs
    movement_count: int
    evidence: dict[str, Any]


class Transfer(BaseModel):
    model_config = ConfigDict(extra="allow")
    sender: tuple[str, str, str]
    recipient: tuple[str, str, str]
    item_id: int
    units: int
    status: str


class Capture(BaseModel):
    model_config = ConfigDict(extra="allow")
    character: str
    kind: str
    age_hours: float | None
    unknown: bool
    empty: bool
    partial: bool
    excluded: int


class Items(BaseModel):
    team: ItemTeam
    totals: list[ItemTotal]
    transfers: list[Transfer]
    reconciliation: list[ItemResidual]
    pairs: list[Pairs]
    movement_count: int
    evidence: dict[str, Any]


class StockRow(BaseModel):
    item_id: int
    name: str
    variant_id: str | None
    variant_state: str
    held: int
    target_units: int | None
    short: int | None = None
    at_most: bool
    buy_units: int | None = None
    wait_units: int | None = None
    unlisted_units: int | None = None
    buy_cost_copper: int | None = None
    fill_cost_copper: int | None = None
    value_copper: int | None
    entry: Target | None
    fill_state: str
    limit_kind: str
    limit_copper: int | None = None
    limit_unknown: bool = False
    whole_stack_units: int | None = None
    above_limit_cost_copper: int | None = None
    purchased_units: int | None = None
    wait_cost_copper: int | None = None


class Stock(BaseModel):
    scan_state: str
    rows: list[StockRow]
    entries: list[Target]
    names: dict[int, str]
    captures: list[Capture]
    holdings: list[dict[str, Any]]
    items_held: int
    value_copper: int
    excluded_prices: int
    items_short: int
    buy_cost_copper: int
    evidence: dict[str, Any]


class Ledger(BaseModel):
    gold: Gold | None
    items: Items | None
    stock: Stock | None
    names: dict[int, str]
    errors: dict[str, str]
    evidence: dict[str, str]


def cached(chosen):
    now = datetime.now(UTC)
    stamp = (*context._inputs(chosen, now), context._stamp(stock.targets_path(chosen["data_dir"], chosen["source_id"])))
    entry = _cache.get(chosen["source_id"])
    if entry is None or entry[0] != stamp:
        catalogs, _ = recipe_catalogs.parse_catalogs(recipe_catalogs.find_catalogs(context.ROOT / "config"))
        entry = (stamp, ledger_view.load(chosen, catalogs, now))
        _cache[chosen["source_id"]] = entry
    return entry[1]


@router.get("/ledger", response_model=Ledger)
def ledger(source: str = "", days: Literal["7", "30", "all"] = "7", q: str = "", chains: bool = False):
    chosen = context.resolve(source)
    with _lock:
        return jsonable_encoder(ledger_view.page(cached(chosen), days, datetime.now(UTC), q, chains))


@router.get("/ledger/movements", response_model=list[Movement])
def movements(
    name: str,
    realm: str,
    faction: str,
    day: str,
    category: str,
    ledger: Literal["gold", "items"],
    source: str = "",
    q: str = "",
    chains: bool = False,
):
    chosen = context.resolve(source)
    with _lock:
        loaded = cached(chosen)
        data = loaded.get(ledger)
        if data is None:
            raise HTTPException(503, f"Unable to read {ledger} evidence. Open Data or retry.")
        return jsonable_encoder(
            ledger_view.movements(
                data, ledger, (name, realm, faction), day, category, ledger_view.filter_basis(loaded), q, chains
            )
        )


@router.post("/ledger/targets", response_model=Targets)
def targets(body: Targets, source: str = ""):
    chosen = context.resolve(source)
    with _lock:
        try:
            stock.save_entries(
                stock.targets_path(chosen["data_dir"], chosen["source_id"]),
                [stock.Entry(**entry.model_dump()) for entry in body.entries],
            )
        except (ValueError, TypeError, OSError) as error:
            raise HTTPException(422, f"Save rejected: {error}. Last saved targets kept.") from error
        _cache.pop(chosen["source_id"], None)
    return body
