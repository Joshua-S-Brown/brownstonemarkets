"""Read-only captured colour/trainer comparisons and explicit selection writes (CRAFT-10)."""
import json
import re
from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from . import action_board, hiring, recipe_catalogs, team_view, today_loading
from .crafting import valid_required_skill, valid_skillup_colors
from .markets import scope_predicate
from .money import format_money
from .recipe_import import toml_value
from .scans import _list
from .storage import has_table
from .today_settings import TodaySettings

DIFFICULTIES = ('optimal', 'medium', 'easy', 'trivial')


def _craft_readings(record):
    """Yield (recipe ID, reading) for learned rows that belong to the record's own profession."""
    state = record.get('known_recipes', {})
    rank = state.get('rank')
    rank = int(rank) if isinstance(rank, str) and rank.isdecimal() else rank
    for row in _list(state.get('rows'), 'recipe rows'):
        info = row.get('info', {})
        # C_TradeSkillUI reports unlearned recipes as optimal (0), so they aren't evidence; rows
        # left over from a previously open window carry another profession's link prefix.
        prefix = re.search(r'\|h\[([^:\]]+): ', row.get('recipe_link') or '')
        if info.get('learned') is False or (prefix and prefix[1] != state.get('name')):
            continue
        difficulty = info.get('relativeDifficulty')
        difficulty = (DIFFICULTIES[difficulty] if type(difficulty) is int and 0 <= difficulty <= 3
                      else row.get('difficulty'))
        yield row.get('recipe_id', row.get('spell_id')), (
            record['character'], record['realm'], record['faction'], rank, difficulty,
            info.get('maxTrivialLevel'), info.get('numSkillUps'))


def observations(records):
    """Deduplicate the same character/rank/colour reading, retaining every journal ID."""
    recipes: dict[tuple, dict] = defaultdict(dict)
    trainers: dict[tuple, dict] = defaultdict(dict)
    for record in records:
        if record.get('family') == 'craft' and record.get('known_recipes'):
            for rid, key in _craft_readings(record):
                recipes[record['known_recipes'].get('name'), rid].setdefault(key, set()).add(record['entry_id'])
        if record.get('family') == 'vendor':
            for service in _list(record.get('trainer_services'), 'trainer services'):
                skill, info, cost = (service.get(k, {}) for k in ('skill_required', 'info', 'cost'))
                name = info.get('1', info.get(1))
                profession = skill.get('1', skill.get(1))
                key = (skill.get('2', skill.get(2)), cost.get('1', cost.get(1)))
                trainers[profession, name].setdefault(key, set()).add(record['entry_id'])
    return recipes, trainers


def compare(recipe, readings):
    """Compare every usable observation; contradictory captures never fill a gap."""
    colors = recipe.get('skillup_colors')
    observed = [r for r in readings if type(r[3]) is int and r[3] > 0 and r[4] in DIFFICULTIES]
    if not observed:
        return 'not observed', None
    greys = {r[5] for r in readings if type(r[5]) is int and r[5] > 0}
    if colors:
        matches = all(r[3] >= colors[0] and sum(r[3] >= boundary for boundary in colors[1:]) == DIFFICULTIES.index(r[4])
                      and (r[5] is None or r[5] == colors[3]) for r in observed)
        return ('confirms' if matches else 'contradicts'), None
    oranges = [r[3] for r in observed if r[4] == 'optimal']
    if not oranges or len(greys) != 1 or not valid_required_skill(recipe.get('required_skill')):
        return ('contradicts' if len(greys) > 1 else 'not observed'), None
    yellow = max(oranges) + 1
    yellows = [r[3] for r in observed if r[4] == 'medium']
    derived = [1 if min(oranges) < recipe['required_skill'] else recipe['required_skill'], yellow,
               max(yellows) + 1 if yellows else yellow, next(iter(greys))]
    if not valid_skillup_colors(derived) or compare(recipe | {'skillup_colors': derived}, readings)[0] != 'confirms':
        return 'contradicts', None
    return 'derived', derived


def report_rows(entries, records):
    captured, trainers = observations(records)
    rows = []
    for entry in entries:
        catalog = entry['catalog']
        profession = recipe_catalogs.profession_title(catalog['profession'])
        for recipe in catalog['recipes']:
            readings = captured.get((profession, recipe['recipe_id']), {})
            # Our own captured colours are re-derived from the latest evidence, never confirmed by it.
            wowhead = recipe if recipe.get('skillup_colors_basis') != 'captured' else {
                key: value for key, value in recipe.items() if key != 'skillup_colors'}
            status, colors = compare(wowhead, readings)
            services = trainers.get((profession, recipe['name']), {})
            rows.append({'entry': entry, 'recipe': recipe, 'profession': profession, 'status': status,
                         'colors': colors, 'observations': readings, 'trainers': services})
    return rows, trainers, captured


def write_selections(rows):
    """Edit only existing derived recipe picks, preserving comments and all other selection bytes.

    A derived recipe without its own pick (an imported intermediate) is skipped and returned:
    appending a pick would turn it into a selected finished recipe."""
    by_path = defaultdict(list)
    for row in rows:
        if row['status'] == 'derived':
            by_path[row['entry']['selection_path']].append(row)
    written, skipped = 0, []
    for path, derived in by_path.items():
        text = path.read_text(encoding='utf-8')
        for row in derived:
            rid = row['recipe']['recipe_id']
            ids = sorted({entry for entries in row['observations'].values() for entry in entries})
            fields = (f"captured_skillup_colors = {toml_value(row['colors'])}\n"
                      f"captured_colors_source = {toml_value(ids)}\n")
            pattern = rf'(?m)^\[\[recipes\]\]\s*\nrecipe_id = {rid}\b[^\n]*\n(?:[^\[]|\[(?!\[))*'
            match = re.search(pattern, text)
            if not match:
                skipped.append(f"{row['profession']} / {row['recipe']['name']} ({rid})")
                continue
            block = re.sub(r'(?m)^captured_(?:skillup_colors|colors_source) = .*\n', '', match[0])
            text = text[:match.start()] + block.rstrip() + '\n' + fields + '\n' + text[match.end():]
            written += 1
        path.write_text(text, encoding='utf-8')
    return written, skipped


def effect_counts(catalogs, config):
    """Compare regenerated catalogs against the same catalogs without captured colours."""
    data, warning = today_loading.load_today_characters(config)
    if warning:
        raise ValueError(warning)
    now = datetime.now(UTC)
    _, arguments = today_loading.load_today(config, catalogs, TodaySettings(), data, now)
    if arguments is None:
        return None
    baseline = deepcopy(catalogs)
    for catalog in baseline:
        for recipe in catalog['recipes_by_id'].values():
            if recipe.get('skillup_colors_basis') == 'captured':
                recipe.pop('skillup_colors', None)
    professions = {action_board.catalog_identity(c): c['profession'] for c in catalogs}
    states = []
    for version in (baseline, catalogs):
        shared = team_view.team_board(version, data, arguments)
        paths = team_view.team_results(version, data, arguments, 25, shared)
        context = hiring.prepare(catalogs=version, character_data=data, shared=shared,
                                 **{key: arguments[key] for key in team_view.BOARD_KEYS})
        hires = hiring.summaries(context)['rows']
        states.append({**{('hire', row['profession']): row['estimate']['complete'] for row in hires},
                       **{('path', professions[recipe['catalog_id']], character,
                           recipe['catalog_id'], recipe['recipe_id']):
                          recipe['estimate']['complete'] for character, result in paths.items()
                          for group in result['professions'] for recipe in group['recipes']}})
    return {profession: {kind: sum(key[0] == kind and key[1] == profession and complete
                                  and states[0].get(key) is False for key, complete in states[1].items())
                         for kind in ('hire', 'path')} for profession in {c['profession'] for c in catalogs}}


def run(config, config_dir: Path, write=False):
    entries = [e for e in recipe_catalogs.find_catalogs(config_dir) if e['catalog'] and
               all(e['catalog'].get(k) == config.get(k) for k in ('game_version', 'rules_version'))]
    catalogs, errors = recipe_catalogs.parse_catalogs(entries)
    if errors:
        raise ValueError('; '.join(errors))
    records = []
    path = config['data_dir'] / 'brownstone.duckdb'
    if path.exists():
        scope, params = scope_predicate(config)
        with duckdb.connect(str(path), read_only=True) as db:
            if has_table(db, 'character_journal'):
                records = [json.loads(raw) for raw, in db.execute(
                    f"SELECT record_json FROM character_journal WHERE {scope} AND family IN ('craft','vendor')",
                    params).fetchall()]
    rows, trainers, captured = report_rows(entries, records)
    lines = [f"Skill-up evidence: {config['source_id']} / {config['market_id']} / {config.get('rules_version')}"]
    lines.extend(evidence_lines(rows, trainers, captured))
    effects = effect_counts(catalogs, config)
    for profession in sorted({c['profession'] for c in catalogs}):
        group = [r for r in rows if r['entry']['catalog']['profession'] == profession]
        counts = {status: sum(r['status'] == status for r in group)
                  for status in ('confirms', 'contradicts', 'derived', 'not observed')}
        gained = sum(r['recipe'].get('skillup_colors_basis') == 'captured' for r in group)
        effect = effects[profession] if effects is not None else None
        lines.append(f"{profession}: {counts}; gained colours={gained}; incomplete -> complete: "
                     f"hire rows={effect['hire'] if effect else 'unknown (no snapshot)'}, "
                     f"CRAFT-11 paths={effect['path'] if effect else 'unknown (no snapshot)'} (window 25)")
    if write:
        written, skipped = write_selections(rows)
        lines.append(f"Wrote {written} derived picks; regenerate with brownstone recipes.")
        lines.extend(f'Not written, no selection pick of its own: {name}' for name in skipped)
    else:
        lines.append('Read-only; use --write to record derived picks, then regenerate with brownstone recipes.')
    return lines


def evidence_lines(rows, trainers, captured):
    lines = []
    for row in rows:
        recipe = row['recipe']
        lines.append(f"{row['profession']} / {recipe['name']} ({recipe['recipe_id']}): {row['status']}; "
                     f"catalog colours={recipe.get('skillup_colors', 'unknown')}, "
                     f"required_skill={recipe.get('required_skill', 'unknown')}, "
                     f"learning={recipe_catalogs.learning_label(recipe)}, "
                     f"training={format_money(recipe.get('training_cost_copper'))}; derived={row['colors']}")
        for reading, ids in row['observations'].items():
            character, realm, faction, rank, difficulty, grey, points = reading
            lines.append(f"  {character}/{realm}/{faction}: rank={rank}, difficulty={difficulty}, "
                         f"maxTrivialLevel={grey}, numSkillUps={points}; entries={', '.join(sorted(ids))}")
        for (skill, cost), ids in row['trainers'].items():
            confirms = (skill == recipe.get('required_skill') and cost == recipe.get('training_cost_copper')
                        and 6 in recipe.get('learned_from', []))
            lines.append(f"  trainer: {'confirms' if confirms else 'contradicts'}; skill={skill}, "
                         f"cost={format_money(cost)}; entries={', '.join(sorted(ids))}")
    matched_ids = {(r['profession'], r['recipe']['recipe_id']) for r in rows}
    for (profession, rid), readings in captured.items():
        if (profession, rid) not in matched_ids:
            lines.append(f'{profession} / recipe {rid}: not observed in catalog')
            for reading, ids in readings.items():
                lines.append(f'  {reading}; entries={", ".join(sorted(ids))}')
    matched = {(r['profession'], r['recipe']['name']) for r in rows}
    for (profession, name), services in trainers.items():
        if profession and (profession, name) not in matched:  # class spells have no profession
            for (skill, cost), ids in services.items():
                lines.append(f'{profession} / {name}: not observed in catalog; trainer skill={skill}, '
                             f'cost={format_money(cost)}; entries={", ".join(sorted(ids))}')
    return lines
