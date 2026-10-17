"""Supply chains adapters; Market's cache and pure projections own route evidence."""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from brownstone import supply_chain, today_settings

from . import context
from .models import Evidence

router = APIRouter()


class Output(BaseModel):
    makeable: bool
    team_reason: str
    catalog_id: str
    recipe_id: int
    item_id: int
    name: str
    profession: str
    profit_copper: int | None


class Outputs(BaseModel):
    scan_at: str | None
    ranked: list[Output]
    hits: list[Output]
    hit_count: int


class Option(BaseModel):
    method: str
    unit_cost_copper: int


class CharacterStatus(BaseModel):
    character: tuple[str, str, str]
    craft_status: str
    character_reason: str
    training_cost_copper: int | None


class Node(BaseModel):
    output: bool
    sale_price_copper: int | None
    listings: int | None
    quality: int | None = None
    item_id: int
    name: str
    units: int
    column: int
    method: str
    unit_cost_copper: int | None
    forced: bool
    options: list[Option]
    maker: str
    characters: list[CharacterStatus]
    route_note: str
    held: int | None
    at_least: bool


class Edge(BaseModel):
    chosen: bool
    parent: int
    child: int
    quantity: int


class Leaf(BaseModel):
    item_id: int
    name: str
    quantity: int
    method: str
    unit_cost_copper: int | None
    total_cost_copper: int | None
    depth: str


class Line(BaseModel):
    start_copper: int
    end_copper: int | None
    quantity: int | None = None
    unit_cost_copper: int | None = None
    label: str
    amount_copper: int | None


class Route(BaseModel):
    catalog_id: str
    recipe_id: int
    name: str
    batch: int
    max_crafts: int
    reason: str
    can_add: bool
    nodes: list[Node]
    edges: list[Edge]
    leaves: list[Leaf]
    waterfall: list[Line]
    spend_copper: int | None
    profit_copper: int | None
    evidence: dict
    source_evidence: Evidence


def forces(values):
    result = {}
    for value in values:
        try:
            item, method = value.split(':')
            item_id = int(item)
            if item_id in result:
                raise ValueError('Duplicate force')
            result[item_id] = method
        except ValueError as error:
            raise ValueError('Force must be a unique item_id:method') from error
    return result


@router.get('/chains', response_model=Outputs)
def outputs(source: str = '', q: str = ''):
    return supply_chain.outputs(context.explorer(context.resolve(source)), q)


@router.get('/chains/route', response_model=Route)
def route(catalog_id: str, recipe_id: int, source: str = '', batch: int = 1,
          force: Annotated[list[str] | None, Query()] = None):
    chosen = context.resolve(source)
    explorer = context.explorer(chosen)
    settings = today_settings.load_settings(today_settings.settings_path(chosen['data_dir'], chosen['source_id']))
    try:
        result = supply_chain.route(explorer, catalog_id, recipe_id, batch, settings.max_crafts, forces(force or []))
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return jsonable_encoder(result | {'source_evidence': context.evidence(chosen, explorer['snapshot'] or {})})
