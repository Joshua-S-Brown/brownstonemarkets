"""Personal planned roster, separate from captured team evidence."""
import tomllib

from . import hiring


def load(path):
    if not path.exists():
        return []
    document = tomllib.loads(path.read_text(encoding='utf-8'))
    entries = document.get('planned', [])
    if not isinstance(entries, list):
        raise ValueError('planned: expected [[planned]] entries')
    seen = set()
    for index, entry in enumerate(entries, 1):
        label = f'planned entry {index}'
        if not isinstance(entry, dict):
            raise ValueError(f'{label}: expected a table')
        name = entry.get('name')
        label += f' ({name})' if isinstance(name, str) else ''
        checks = {
            'name': name is None or isinstance(name, str) and bool(name.strip()),
            'faction': entry.get('faction') in ('alliance', 'horde'),
            'role': isinstance(entry.get('role'), str),
            'professions': isinstance(entry.get('professions'), list),
        }
        for field, valid in checks.items():
            if not valid:
                raise ValueError(f'{label}: invalid {field}')
        skills = entry['professions']
        if len(skills) > 2:
            raise ValueError(f'{label}: professions must contain at most two skill IDs')
        if any(type(skill) is not int or skill not in hiring.SKILL_IDS.values() for skill in skills):
            raise ValueError(f'{label}: professions contains an unknown skill ID')
        key = (name.casefold(), entry['faction']) if name else None
        if key and key in seen:
            raise ValueError(f'{label}: duplicate name and faction')
        seen.add(key)
    return entries


def roster(entries, cards, context, summaries):
    captured = {(c['name'].casefold(), c['faction'].lower()) for c in cards}
    names = {skill: name for name, skill in hiring.SKILL_IDS.items()}
    rows = {row['profession']: row for row in summaries}
    result = []
    for entry in entries:
        if entry.get('name') and (entry['name'].casefold(), entry['faction']) in captured:
            continue
        professions = []
        for skill in entry['professions']:
            name = names[skill]
            row = rows.get(name)
            unknown = dict(estimate=dict(complete=False, cost_copper=None, reasons=['No priced scan or catalog']),
                           best=None)
            tiers = [dict(cap=cap, **(hiring.tier(context, row, cap) if context and row else unknown))
                     for cap in hiring.CAPS[:2]]
            professions.append(dict(profession=name, tiers=tiers))
        result.append(entry | {'professions': professions})
    return result
