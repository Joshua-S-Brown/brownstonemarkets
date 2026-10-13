"""Catalog-shaped team routes. Callers supply scoped makeability and purchase prices."""
from collections import defaultdict

from .crafting import _craft_route
from .markets import MARKET_KEYS


def identity(catalog: dict) -> str:
    return catalog.get('catalog_id', ':'.join(catalog[key] for key in
                                             ('game_version', 'rules_version', 'profession', 'catalog_version')))


class RecipeGraph:
    """Index one market's compatible catalogs once, then select routes for each root recipe.

    A projection keeps the root catalog's legacy eligibility and admits other catalogs only
    through supplied Known/Train now evidence. The ordinary crafting walker consumes the result.
    """

    def __init__(self, catalogs: list[dict], makeable: dict, market: dict):
        self.makeable = makeable
        self.items: dict[int, dict] = {}
        self.recipes: dict[int, dict] = {}
        self.outputs: dict[int, list[int]] = defaultdict(list)
        self.origins: dict[int, list[tuple[str, dict]]] = defaultdict(list)
        catalogs = [c for c in catalogs if catalog_compatible(c, market)]
        names = [identity(c) for c in catalogs]
        if len(set(names)) != len(names):
            raise ValueError("Catalog identities must be unique")
        for catalog in sorted(catalogs, key=identity):
            self._add_catalog(catalog)
        self.conflicts = {item for item, records in self.origins.items() if _disagree(records)}
        self.warnings = [f"Item {item}: disagreeing route fields in catalogs "
                         + ', '.join(name for name, _ in self.origins[item]) + '; buy-only'
                         for item in sorted(self.conflicts)]
        for item in self.conflicts:
            self.items[item] = {k: v for k, v in self.items[item].items() if k != 'vendor_price_copper'}

    def _add_catalog(self, catalog):
        name = identity(catalog)
        for item_id, item in catalog['items_by_id'].items():
            # A field one catalog omits takes another catalog's recorded value; only differing values conflict.
            self.items[item_id] = item | self.items.get(item_id, {})
            self.origins[item_id].append((name, item))
        for recipe_id, recipe in catalog['recipes_by_id'].items():
            if recipe_id in self.recipes:
                raise ValueError(f"Recipe ID {recipe_id} collides in catalogs "
                                 f"{self.recipes[recipe_id]['catalog_id']} and {name}")
            self.recipes[recipe_id] = recipe | {'catalog_id': name}
            self.outputs[recipe['output_item_id']].append(recipe_id)

    def for_recipe(self, catalog: dict, recipe_id: int, prices: dict[int, int]) -> dict:
        """Choose each reachable maker using the existing unit-cost calculation, then identity."""
        name = identity(catalog)
        if self.recipes.get(recipe_id, {}).get("catalog_id") != name:
            raise ValueError(f"Recipe {recipe_id} does not belong to compatible catalog {name}")
        graph = catalog | {'items_by_id': self.items, 'recipes_by_id': self.recipes,
                           'recipe_for_output': {}, 'catalog_warnings': self.warnings,
                           'blocked_cross_items': set(), 'team_makeable': self.makeable}
        selection = _RouteSelection(self, graph, prices, name)
        recipe = self.recipes[recipe_id]
        for ingredient in recipe['inputs']:
            selection.resolve(ingredient['item_id'], (recipe['output_item_id'],))
        return graph

    def _candidates(self, item_id, own):
        if item_id in self.conflicts:
            return []
        return [r for r in self.outputs.get(item_id, []) if self.recipes[r]['catalog_id'] == own
                or self.makeable.get((self.recipes[r]['catalog_id'], r))]


class _RouteSelection:
    def __init__(self, index: RecipeGraph, graph: dict, prices: dict[int, int], own: str) -> None:
        self.index, self.graph, self.prices, self.own = index, graph, prices, own
        self.visited: set[int] = set()

    def resolve(self, item_id, trail):
        if item_id in trail:
            raise ValueError('Recipe cycle detected across catalogs')
        if item_id in self.visited:
            return
        candidates = self.index._candidates(item_id, self.own)
        if self.index.outputs.get(item_id) and not candidates and item_id not in self.index.conflicts:
            self.graph['blocked_cross_items'].add(item_id)
        costs, errors = [], []
        for nested_id in candidates:
            nested = self.index.recipes[nested_id]
            try:
                # An invalid maker anywhere in its chain must not hide a valid competing maker.
                for ingredient in nested['inputs']:
                    self.resolve(ingredient['item_id'], (*trail, item_id))
                route = _craft_route(self.graph, self.prices, nested_id, ())
            except ValueError as error:
                errors.append(error)
                continue
            costs.append((route is None, route[0] if route else 0, nested['catalog_id'], nested_id))
        if not costs and errors:
            raise errors[0]
        if costs:
            self.graph['recipe_for_output'][item_id] = min(costs)[-1]
        self.visited.add(item_id)


def catalog_compatible(catalog, market):
    return (catalog['game_version'] == market.get('game_version')
            and catalog['rules_version'] == market.get('rules_version')
            and all(key not in catalog or catalog[key] == market.get(key) for key in MARKET_KEYS))


ROUTE_FIELDS = ('vendor_price_copper', 'raw_material', 'availability')


def _disagree(records):
    return any(len({record[key] for _, record in records if key in record}) > 1 for key in ROUTE_FIELDS)


def route_catalog(catalog, recipe_id, prices, graph=None):
    return graph.for_recipe(catalog, recipe_id, prices) if graph is not None else catalog


def label_routes(result, catalog):
    """Attach route origins without altering the cost walk or adding intermediate profit."""
    if 'team_makeable' not in catalog:
        return result
    for step in result['intermediate_steps']:
        recipe = catalog['recipes_by_id'][step['recipe_id']]
        step.update(_maker(recipe, catalog))
    for choice in result['choices']:
        if choice['method'] == 'craft':
            recipe = catalog['recipes_by_id'][catalog['recipe_for_output'][choice['item_id']]]
            choice.update(_maker(recipe, catalog))
        elif choice['item_id'] in catalog['blocked_cross_items']:
            choice['route_note'] = 'no one on the team makes this'
    result['catalog_warnings'] = catalog['catalog_warnings']
    return result


def _maker(recipe, catalog):
    makers = catalog['team_makeable'].get((recipe['catalog_id'], recipe['recipe_id']), [])
    return {'catalog_id': recipe['catalog_id'], 'profession': recipe['profession'],
            'made_by': makers[0] if makers else None}


def made_by_label(step):
    profession = step.get('profession', '').replace('-', ' ').title()
    maker = step.get('made_by')
    return f'{maker}, {profession}' if maker else profession


def step_label(step):
    maker = made_by_label(step)
    return step["item_name"] + (f" · {maker}" if maker else "")
