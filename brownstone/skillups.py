"""Catalog-only skill-up expectations. Rules: CRAFT-10; no I/O or price-based routes."""
from collections import defaultdict

from .crafting import material_plan


def band_label(start: int) -> str:
    return f"{max(1, start)}–{start + 24}"


def recipe_placement(recipe: dict) -> tuple[list[str], str, bool]:
    """Place orange inclusive to green exclusive; unknown learned skill never becomes 1."""
    skill = recipe.get("required_skill")
    colors = recipe.get("skillup_colors")
    if skill is None:
        if colors and colors[0] == colors[2]:
            return ["skill unknown"], "skill unknown; no reliable skill-ups", False
        return ["skill unknown"], "skill unknown", True
    if not colors:
        return [band_label(skill // 25 * 25)], "skill-up range unknown", True
    orange, _, green, _ = colors
    if orange == green:
        return [band_label(skill // 25 * 25)], "no reliable skill-ups", False
    return [band_label(b) for b in range(orange // 25 * 25, (green - 1) // 25 * 25 + 1, 25)], "", True


def coverage_line(catalog: dict) -> str:
    counts = catalog.get("page_coverage")
    if counts is None:
        return "coverage unknown; regenerate the catalog"
    return (f"Catalog holds {len(catalog['recipes_by_id'])} of {counts['usable']} usable recipes on its saved page "
            f"(saved {catalog.get('verified_at', 'unknown')}); {counts['no_item']} recipes on the page create "
            "no item and aren't counted")


def partial_coverage(catalog: dict) -> bool:
    counts = catalog.get("page_coverage")
    return counts is None or len(catalog['recipes_by_id']) < counts['usable']


def raw_materials(catalog: dict) -> frozenset[int]:
    """Items the selection marks as obtained directly; their catalog recipe stays but isn't expanded."""
    return frozenset(i for i, item in catalog['items_by_id'].items() if item.get('raw_material'))


def _recipe(catalog: dict, recipe: dict, n: int, include_post_launch: bool, stop_at: frozenset[int]) -> dict:
    bands, label, reliable = recipe_placement(recipe)
    excluded = recipe.get("availability") == "post-launch" and not include_post_launch
    direct: defaultdict[int, int] = defaultdict(int)
    raw = {}
    error = None
    if reliable and not excluded:
        for ingredient in recipe['inputs']:
            direct[ingredient['item_id']] += ingredient['quantity'] * n
        try:
            raw = material_plan(catalog, recipe['recipe_id'], n, stop_at)
        except ValueError as failure:
            error = str(failure)
    return {"recipe": recipe, "bands": bands, "label": label, "excluded": excluded,
            "direct": dict(direct), "raw": raw, "error": error}


def material_totals(groups: list[dict], kind: str) -> list[dict]:
    """Each recipe occurs once in a group; prices cannot affect units or sorting."""
    totals: dict[int, dict] = {}
    for group in groups:
        catalog = group['catalog']
        for row in group['recipes']:
            for item_id, quantity in row[kind].items():
                item = catalog['items_by_id'][item_id]
                total = totals.setdefault(item_id, {"item_id": item_id, "name": item['name'], "units": 0,
                                                    "professions": set(), "bands": set()})
                total['units'] += quantity
                total['professions'].add(catalog['profession'])
                total['bands'].update(row['bands'])
    return [{**row, "professions": sorted(row['professions']), "bands": sorted(row['bands'], key=_band_order)}
            for row in sorted(totals.values(), key=lambda r: (-r['units'], r['item_id']))]


def _band_order(label: str) -> int:
    return 100000 if label == 'skill unknown' else int(label.split('–')[0])


def _bands(recipes: list[dict]) -> list[dict]:
    labels = {b for row in recipes for b in row['bands']}
    starts = [_band_order(label) for label in labels if label != 'skill unknown']
    if starts:
        labels.update(band_label(start) for start in range(0, max(starts) + 1, 25))
    return [{"label": label, "recipes": [r for r in recipes if label in r['bands']]}
            for label in sorted(labels, key=_band_order)]


def build_skillups(catalogs: list[dict], n: int = 5, include_post_launch: bool = False) -> dict:
    if type(n) is not int or not 1 <= n <= 50:
        raise ValueError("N crafts per recipe must be an integer from 1 to 50")
    groups = []
    for catalog in catalogs:
        stop_at = raw_materials(catalog)
        recipes = [_recipe(catalog, recipe, n, include_post_launch, stop_at)
                   for recipe in catalog['recipes_by_id'].values()]
        bands = _bands(recipes)
        group = {"catalog": catalog, "recipes": recipes, "bands": bands,
                 "coverage": coverage_line(catalog), "partial": partial_coverage(catalog),
                 "excluded": sum(r['excluded'] for r in recipes)}
        group.update({kind: material_totals([group], kind) for kind in ('direct', 'raw')})
        groups.append(group)
    return {"n": n, "groups": groups, "excluded": sum(g['excluded'] for g in groups),
            "partial": any(g['partial'] for g in groups),
            **{kind: material_totals(groups, kind) for kind in ('direct', 'raw')}}
