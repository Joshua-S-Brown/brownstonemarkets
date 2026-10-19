"""Public, integer-copper web contracts."""
from typing import Any

from pydantic import BaseModel


class Evidence(BaseModel):
    source_id: str
    market_id: str
    scan_id: str | None = None
    finished_at: str | None = None
    freshness: dict[str, Any] | None = None


class SourceOption(BaseModel):
    source_id: str
    label: str
    short_label: str
    game_version: str


class Sources(BaseModel):
    sources: list[SourceOption]
    selected: SourceOption | None
    evidence: Evidence | None
    waiting: int | None
    waiting_error: str | None = None
    questions: dict[str, str]


class SearchHit(BaseModel):
    role: str | None = None
    character: tuple[str, str, str] | None = None
    kind: str
    name: str
    item_id: int | None = None
    quality: int | None = None
    variant_state: str | None = None
    variant_id: str | None = None


class BestUse(BaseModel):
    item_id: int | None = None
    name: str | None = None
    profit_copper: int | None = None
    reason: str


class Speed(BaseModel):
    label: str
    pairs: int
    hours: float
    daily_units: int | None
    median_units: float | None
    days_supply: float | None
    suggested_units: int | None
    reason: str
    settings: dict[str, int]


class Item(BaseModel):
    speed: Speed | None = None
    role: str | None
    deposit_copper: int | None
    item_id: int
    name: str
    quality: int | None
    price_copper: int | None
    typical_copper: int | None
    units: int | None
    listings: int | None
    vendor_buy: list[int]
    vendor_sell: int | None
    held: int | None
    at_least: bool
    crowding: str | None
    overshoot: str | None
    used_in: BestUse
    made_from: BestUse
    evidence: Evidence
    details: dict[str, Any]


class MarketRow(BaseModel):
    item_id: int
    name: str
    variant_id: str | None
    variant_state: str | None
    quality: int | None
    price_copper: int | None
    typical_copper: int | None
    gap_copper: int | None
    gap_percent: float | None
    roles: list[str]
    listings: int | None
    units: int | None
    signal: dict[str, Any] | None
    sparkline: list[int | None]
    variants: list["MarketRow"] = []


class MarketCardRow(BaseModel):
    item_id: int
    name: str
    variant_id: str | None
    variant_state: str | None
    quality: int | None
    price_copper: int | None
    typical_copper: int | None
    gap_percent: float | None
    sparkline: list[int | None]
    outside_chains: bool
    removed_units: int | None


class MarketCard(BaseModel):
    preview: list[MarketCardRow]
    more: list[MarketCardRow]


class Market(BaseModel):
    rows: list[MarketRow]
    cards: dict[str, MarketCard]
    item_count: int
    identity_count: int
    listed_chain_count: int
    pulse: dict[str, list[dict[str, Any]]]
    removals: dict[str, Any]
    movement: dict[str, Any]
    floods: dict[str, Any]
    chain_count: int
    warning: str | None
    note: str
    evidence: Evidence


class HistoryPoint(BaseModel):
    scan_id: str
    finished_at: str
    metrics: dict[str, Any] | None


class History(BaseModel):
    removals: dict[str, Any]
    removals_error: str | None
    scans: list[dict[str, Any]]
    points: list[HistoryPoint]
    other_identities: int
    note: str


class LadderRow(BaseModel):
    price_copper: int
    listings: int
    units: int
    cumulative_units: int


class Ladder(BaseModel):
    scan: dict[str, Any]
    rows: list[LadderRow]
    no_buyout_listings: int
    no_buyout_units: int
    note: str
    freshness: dict[str, Any]
    zoom_copper: int | None


class MaterialUse(BaseModel):
    action: str
    value_copper: int | None
    reason: str
    characters: list[dict[str, Any]]
    eligible: bool
    eligibility: str = ""
    over_selling_copper: int | None
    catalog_id: str | None = None
    recipe_id: int | None = None
    item_id: int | None = None
    quantity: int | None = None
    intermediate: bool = False
    vendor_capped: bool = False
    vendor_price_cap_copper: int | None = None


class Chain(BaseModel):
    best_uses: list[MaterialUse]
    in_chain: bool
    demand: list[dict[str, Any]]
    made_from: list[dict[str, Any]]
    used_in: list[dict[str, Any]]


class Activity(BaseModel):
    your_sales: list[dict[str, Any]]
    unidentified_sales: int
    sales_error: str | None
    held: int | None
    at_least: bool
    captures: list[dict[str, Any]]
    holdings: list[dict[str, Any]]
    holdings_warning: str | None
    farming: list[dict[str, Any]]
    wowhead_url: str
