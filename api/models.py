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
    game_version: str


class Sources(BaseModel):
    sources: list[SourceOption]
    selected: SourceOption | None
    evidence: Evidence | None
    waiting: int | None
    waiting_error: str | None = None
    questions: dict[str, str]


class SearchHit(BaseModel):
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


class Item(BaseModel):
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
