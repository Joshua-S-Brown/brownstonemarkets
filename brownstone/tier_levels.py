"""Validated trainer evidence, passed as data to tier calculations (UI-12)."""
import tomllib
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'config' / 'tier_levels.toml'
TIERS = ('Journeyman', 'Expert', 'Artisan')
FALLBACK_LABEL = ' (Classic level, unconfirmed on Forever)'


def load(path: Path = DEFAULT_PATH) -> dict:
    with path.open('rb') as file:
        raw = tomllib.load(file)
    if set(raw) != {'levels'} or not isinstance(raw['levels'], list):
        raise ValueError('Tier levels require a levels table array')
    result = {}
    for row in raw['levels']:
        _validate(row)
        key = (profession_key(row['profession']), row['tier'])
        if key in result:
            raise ValueError(f'Duplicate tier level: {key}')
        result[key] = row
    return result


def _validate(row):
    fields = {'profession', 'tier', 'level', 'entry_id', 'character', 'captured_date'}
    if not isinstance(row, dict) or set(row) != fields:
        raise ValueError('Tier level requires profession, tier, level and trainer provenance')
    if any(not isinstance(row[k], str) or not row[k].strip() for k in fields - {'level', 'captured_date'}):
        raise ValueError('Tier level names and provenance must be nonempty strings')
    if row['tier'] not in TIERS or type(row['level']) is not int or row['level'] < 0:
        raise ValueError('Tier level requires a known tier and nonnegative integer level')
    if type(row['captured_date']) is not date:
        raise ValueError('Tier level captured_date must be a TOML date')


def profession_key(name):
    """Catalog slugs and captured profession titles share an explicit lookup key."""
    return name.replace('-', ' ').casefold()


def lookup(levels, game_version, profession, tier, classic_level):
    """Names identify explicit table keys only; missing Forever evidence retains a labelled assumption."""
    row = levels.get((profession_key(profession), tier)) if game_version == 'forever' else None
    if row is not None:
        return {'required_level': row['level'], 'source': 'trainer', 'evidence': row}
    return {'required_level': classic_level,
            'source': 'classic_fallback' if game_version == 'forever' else 'classic'}


def fallback_label(tier):
    return FALLBACK_LABEL if tier.get('source') == 'classic_fallback' else ''


def explanation(levels, game_version):
    if game_version != 'forever':
        return 'Classic Era tier levels: Journeyman 10, Expert 20, Artisan 35.'
    known = '; '.join(f"{r['profession']} {r['tier']} {r['level']}" for r in levels.values()) or 'none'
    return ('Levels from captured Forever trainer lists: ' + known + '. Other tiers use Classic levels '
            '(Classic level, unconfirmed on Forever).')
