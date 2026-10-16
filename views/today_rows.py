"""Framework-free Today table projections and wording for the app; copper conversion uses money.py."""
from datetime import UTC, datetime

from brownstone.money import format_money
from brownstone.tier_levels import fallback_label
from brownstone.today_session import PLAN_RESET as PLAN_RESET
from brownstone.today_session import headline_profit
from brownstone.today_warnings import warning_fields

ROW_LIMIT_NOTE = "more rows outside this list's 10-row limit"
SETTINGS_NOTE = "One funded plan · whole auction stacks are bought; surplus is shown · sales speed is unknown"
MISSING_CHARACTER = "Saved character is no longer present in this source and market; showing Our team."
ZERO_GOLD_HINT = "Enter the gold you have available to size the plan. Use explicit units, for example 12g 50s."
NO_SNAPSHOT = "Refresh or import a scan for this market to inspect Today."
NO_LISTINGS = ("Individual listings, thin markets, cheap now, undercuts and below-vendor listings: "
               "not available for this source. Batches use funds and the per-item cap; costs are aggregate estimates.")

VENDOR_ASIDE = "Independent aside, not part of the craft budget."


def state(row):
    return "stale — inspect only" if row["stale"] else "potential gain"


def unreadable_settings(error):
    return f"Could not read Today settings: {error}. Defaults are shown; save to replace this file."


def provenance(result, config, manifest, snapshot_id):
    freshness = result["freshness"]
    return (f"Today rules v{result['today_version']} · cautious output price · "
            f"{config['auction_cut']:.0%} auction cut · source {config['source_id']} · "
            f"market {config['market_id']} · snapshot {snapshot_id} · "
            f"scan {manifest.get('scan_id', 'not available for this source')} · "
            f"evidence {freshness['observed_at']} (UTC) · time basis {freshness['basis']}")


def hidden_line(counts):
    return "Hidden recipes: " + ("; ".join(f"{reason}: {count}" for reason, count in sorted(counts.items())) or "0")


def shopping_line(result):
    return (f"Whole shopping list: {format_money(result['shopping_total_copper'])}. "
            "Cheap now means average paid is strictly below scan p25; informational only. Vendor stock is unknown.")


def craft_row(row, sell):
    headline = headline_profit(row, sell)
    return present_row({"Item": row["output_name"], "Profession": row["profession"].title(),
            "Catalog": row["catalog_id"],
            "Recipe": row["recipe_id"], "Batch": row["batch_size"], "Limited by": row["limiting_factor"],
            "Material cost (g)": row["batch_cost_copper"],
            "Batch profit (g)": headline["headline_profit_copper"],
            "Profit per craft (g)": headline["headline_per_craft_copper"],
            "Cautious output unit (g)": row["sale_price_copper"], "Listings": sell["listings"],
            "Units": sell["units"], "Thin": sell["thin"], "Availability": row["availability"],
            "Profit basis": headline["profit_basis"].strip() or "at post price",
            "Vendor ceiling": vendor_cap_label(row, sell),
            "Evidence notes": "; ".join(row["evidence_notes"]), "Recipe source": row["recipe_source"],
            **_character_columns(row), **_confidence_columns(row), "State": state(row)})


def _character_columns(row):
    if "craft_status" not in row:
        return {"Who can make it": ", ".join(row.get("who_can_make_it", [])) or "unknown"}
    learning = row["character_reason"]
    if row["craft_status"] == "Train now":
        cost = row["training_cost_copper"]
        learning = "Training: " + (format_money(cost) if cost is not None else "cost unknown")
    team = {"Who can make it": ", ".join(row.get("who_can_make_it", [])) or "unknown"} if row.get("team") else {}
    return team | {"Can make": row["craft_status"], "Learning": learning}


def sell_deposit(row):
    """Short table cell; the Queue post line keeps the full refund wording."""
    value = row.get("deposit_copper")
    if value is None:
        return "deposit unknown"
    return f"{format_money(value)} at {row.get('post_duration_hours', 24)}h, lost if it expires"


def sell_row(row):
    return present_row({"Output": row["output_name"], "Catalog": row["catalog_id"], "Recipe": row["recipe_id"],
            "Batch": row["batch_size"], "Lowest competing unit (g)": row["lowest_copper"],
            "Listings": row["listings"], "Units": row["units"], "Largest stack units": row["largest_stack_units"],
            "Undercut unit (g)": row["undercut_copper"], "Price step": row.get("price_step", "1c"),
            "Vendor ceiling": vendor_cap_label(row),
            "Profit at undercut for batch (g)": row["undercut_batch_profit_copper"],
            "Deposit_copper": row.get("deposit_copper"), "Deposit": sell_deposit(row),
            "Your sales": sales_text(row.get("your_sales")), "Thin": row["thin"], "Warnings": warning_fields(row),
            **held_output_columns(row), **_confidence_columns(row), "State": state(row)})


def capture_label(capture):
    """One holdings capture with its age; a missing location is never shown as empty."""
    age = capture['age_hours']
    state = f"{age:.1f} hours old" if age is not None else f"{capture['kind']} not captured"
    return f"{capture['character']} · {capture['kind']} · {state}"


def held_output_columns(row):
    held = row.get('held_outputs', [])
    if not held:
        return {}
    value = row.get('held_value_copper')
    return {'Held units': sum(u['units'] for u in held),
            'Held by': ', '.join(f"{u['character']} ({u['kind']}): {u['units']}" for u in held),
            'Held value_copper': value, 'Held value': money_text(value)}


def _confidence_columns(row):
    return {"Confidence": row["confidence"], "Reasons": ", ".join(row["confidence_reasons"])}


def _name(names, item_id):
    return names.get(item_id, f"Item {item_id}")


def buy_row(row, names, *, item_id=False, used_for=None):
    """Project item identity and the crafts purchased units are for."""
    result = {"Material": _name(names, row["item_id"]), **({"Item ID": row["item_id"]} if item_id else {}),
              "Route": row["method"]}
    if used_for is not None:
        result["For"] = used_for
    return present_row(result | {"Required units": row["quantity"], "Purchased units": row["purchased_units"],
                     "Cost (g)": row["cost_copper"],
                     "Highest unit price (g)": row["highest_unit_copper"],
                     "Scan p25 (g)": (row["p25_copper"]), "Cheap now": row["cheap_now"], "State": state(row)})


def vendor_row(row, names, *, item_id=False):
    return present_row({"Item": _name(names, row["item_id"]),
            **({"Item ID": row["item_id"], "Listings": row["listings"]} if item_id else {}),
            "Units": row["purchased_units"], "Cost (g)": row["cost_copper"],
            "Vendor pays per unit (g)": row["vendor_sell_copper"],
            "Highest listing unit (g)": row["highest_unit_copper"], "Gain (g)": row["gain_copper"],
            "State": state(row)})


def material_row(row, *, item_id=False):
    """One reserved purchase from ``today.craft_details``."""
    return present_row({"Material": row["item_name"], **({"Item ID": row["item_id"]} if item_id else {}),
            "Route": ("held" if row["method"] == "held" else
                      ("vendor" if row["method"] == "vendor" else "auction house")),
            "Required units": row["quantity"], "Purchased units": row["purchased_units"],
            "Cost (g)": row["cost_copper"], "Highest unit price (g)": row["highest_unit_copper"],
            "State": state(row)})


def summary_tiles(result, *, hide_low=False):
    """Display totals from the reserved plan, using Sell's undercut profits without re-quoting.

    Hiding Low confidence filters the shown crafts like the cards; gold needed stays the reserved plan's.
    """
    crafts = [r for r in result['craft'] if not (hide_low and r['confidence'] == 'Low')]
    shown = {r['output_item_id'] for r in crafts} if hide_low else None
    sells = [r for r in result['sell'] if shown is None or r['output_item_id'] in shown]
    valued = [r for r in sells if r['undercut_batch_profit_copper'] is not None]
    best = max(valued, key=lambda r: r['undercut_batch_profit_copper'], default=None)
    profit = (format_money(sum(r['undercut_batch_profit_copper'] for r in valued))
              if len(valued) == len(sells) else 'unavailable')
    return [('Crafts', str(len(crafts))), ('Gold needed', format_money(result['shopping_total_copper'])),
            ('Expected profit', profit), ('Best craft',
             f"{best['output_name']} · {format_money(best['undercut_batch_profit_copper'])}"
             if best else 'none valued')]


def empty_sentence(hidden, minimum_copper, gold_copper):
    """Explain the largest exclusions without claiming knowledge or prices we do not have."""
    reasons = sorted(((reason, count) for reason, count in hidden.items() if count),
                     key=lambda entry: (-entry[1], entry[0]))[:2]
    why = ' Most recipes are hidden because ' + ' and '.join(
        HIDDEN_WORDING.get(r, (r, r))[0] for r, _ in reasons) + '.' if reasons else ''
    return (f"No craft meets the {format_money(minimum_copper)} minimum batch gain with "
            f"{format_money(gold_copper)} available.{why} Review your settings or inspect all reasons.")


def scan_status(freshness):
    """Short age chip; unknown upstream time remains explicit."""
    age = freshness['age_hours']
    if age < 0:
        return 'Scan dated in the future'
    basis = 'Scan' if freshness['upstream_known'] else 'Download (price age unknown)'
    return f'{basis} {age:.0f} hours old'


def stale_banner(freshness):
    if freshness['age_hours'] < 0:
        return 'These prices are dated in the future. Check the clock and scan again before you buy.'
    return 'Prices are from an older scan. Treat this plan as a preview; scan again before you buy.'


def planning_label(character, data):
    if character is None or character not in data:
        return 'Planning for Our team'
    from brownstone.today_characters import profession_rank

    skills = []
    for name, record in data[character].get('recipes', {}).items():
        rank, _ = profession_rank(data[character], record)
        skills.append(f"{name} {rank if rank is not None else 'rank unknown'}")
    return 'Planning for ' + character[0] + (' · ' + ', '.join(skills) if skills else '')


def material_card_rows(materials):
    """Reserved purchases in the approved card table, with in-game money and surplus explicit."""
    return [{'Material': r['item_name'],
             'Where': 'Held' if r['method'] == 'held' else ('Vendor' if r['method'] == 'vendor' else 'Auction house'),
             'Units': str(r['purchased_units']) + (f" ({r['quantity']} needed)"
                       if r['purchased_units'] != r['quantity'] else ''),
             'Cost': f"worth {money_text(r['cost_copper'])} if sold" if r['method'] == 'held'
             else money_text(r['cost_copper']), 'State': state(r)} for r in materials]


def display_hidden(result, hide_low):
    """Display filtering is counted without changing the reserved plan or its hidden reasons."""
    counts = dict(result['hidden'])
    if hide_low:
        counts['low confidence'] = sum(r['confidence'] == 'Low' for r in result['craft'])
    return counts


def recorded_gold_rows(data, character):
    """Captured balances alongside an entered budget; zero/missing captures remain unknown."""
    identities = [character] if character in data else sorted(data)
    rows = []
    for identity in identities:
        bags = data[identity].get('bags', {})
        gold, captured = bags.get('gold_copper'), bags.get('captured_at')
        readable = type(gold) is int and gold > 0 and type(captured) is int
        rows.append({'Character': ' · '.join(identity),
                     'Recorded gold': format_money(gold) if readable else 'unknown',
                     'Captured (UTC)': datetime.fromtimestamp(captured, UTC).strftime('%Y-%m-%d %H:%M UTC')
                     if type(captured) is int else 'unknown'})
    return rows


def present_row(row):
    """Money stays sortable in copper while visible cells use the player's units."""
    result = {}
    for key, value in row.items():
        if key.endswith(' (g)'):
            key = key.removesuffix(' (g)')
            result[key + '_copper'] = value
            value = money_text(value)
        elif key in ('Thin', 'Cheap now'):
            value = 'unknown' if value is None else ('yes' if value else 'no')
        elif key == 'Warnings':
            result['_warnings'] = value
            value = warning_text(value)
        result[key] = value
    return result


def count_word(count, singular, plural=None):
    return f"{count:,} {singular if count == 1 else (plural or singular + 's')}"


HIDDEN_WORDING = {
    'no character has this profession': ('your team does not have the required professions',
                                         'need a profession nobody has'),
    'rank below required skill': ('profession ranks are below the required skill', 'need more skill'),
    'below minimum gain': ('profit is below minimum gain', 'are below minimum gain'),
    'one craft exceeds funds': ('one craft costs more than the available gold', 'cost more than available gold'),
    'insufficient listed materials': ('there are not enough listed materials', 'need more listed materials'),
    'missing prices': ('prices are missing', 'need prices'),
}


def hidden_summary(counts):
    return ' · '.join(f"{count:,} {HIDDEN_WORDING.get(reason, (reason, reason))[1]}"
                      for reason, count in sorted(counts.items(), key=lambda r: (-r[1], r[0])) if count) or '0 hidden'


CROWDING = {'thin': ('thin: few listings', 'warn'), 'contested': ('contested: many sellers', 'warn')}
OVERSHOOT = {'cheap': ('cheap right now', 'good'), 'high': ('pricier than usual', 'warn'),
             'too few days': ('price history too short', 'neutral'), 'no buyout': ('no buyout', 'neutral')}


def warning_text(fields):
    signal = fields.get('signal') or {}
    words = [labels[key][0] for labels, key in ((CROWDING, signal.get('crowding')),
             (OVERSHOOT, signal.get('overshoot', {}).get('label'))) if key in labels]
    removals = fields.get('early_removals')
    if removals and removals['pairs'] >= 3 and removals['units'] == 0:
        words.append(f"no early removals in {removals['pairs']} scan gaps")
    if fields.get('price_note'):
        words.append(fields['price_note'])
    return '; '.join(words)


def money_text(value):
    return format_money(value) if value is not None else 'unknown'


def sales_text(row):
    if not row or not row['resolved']:
        return 'none resolved yet'
    text = f"{row['sold']} of {row['resolved']} sold"
    if row['average_copper'] is not None:
        text += f" · {format_money(row['average_copper'])} each after cut"
    return text


def vendor_cap_label(*rows):
    """Label only a value the vendor price actually lowered; a sale already below it is uncapped."""
    row = next((r for r in rows if r.get('vendor_capped')), None)
    return f"capped at vendor price {format_money(row['vendor_price_cap_copper'])}" if row else ""


def vendor_cap_suffix(*rows):
    label = vendor_cap_label(*rows)
    return f" · {label}" if label else ""


def cheap_share(estimate):
    cheap, cost = estimate['cheap_cost_copper'], estimate['cost_copper']
    if cheap is None:
        return 'cheap auction materials unknown'
    if cheap == cost and cost:
        return 'all on materials that are cheap right now'
    return f'{format_money(cheap)} of it on cheap auction materials' if cheap else 'no cheap auction materials'


def step_text(step, character, window):
    """One plain line per option; the figures are the ones in the details below."""
    name = character['character'][0]
    kind = step['kind']
    if kind == 'craft':
        rows = ', '.join(f"{r['batch_size']} {r['output_name']}" for r in character['crafts'])
        return (f"Craft {rows} · planned profit {format_money(character['craft_profit_copper'])}"
                f"{session_profit_basis(character)}")
    if kind == 'nothing':
        return (f'Nothing to craft or level within {window} points. '
                'Gathering is an option here.')
    if kind == 'evidence':
        return 'No professions seen yet: open each profession window next login so Brownstone can read them.'
    group = step['group']
    profession = group['profession']
    if kind == 'level_profession':
        recipe, estimate = step['recipe'], step['recipe']['estimate']
        more = f" (+{step['more']} more on the way)" if step['more'] else ''
        return (f"Level {profession} {group['rank']} → {recipe['required_skill']} for "
                f"{format_money(estimate['cost_copper'])}, {cheap_share(estimate)} · unlocks {recipe['name']} "
                f"at {format_money(recipe['profit_copper'])} per craft{more}{vendor_cap_suffix(recipe)}")
    tier = step['tier']
    if len(step.get('groups', [])) > 1:
        return merged_tier_text(step, character)
    if kind == 'train':
        return (f"{profession} is capped at {tier['cap']}: train {tier['name']} {profession} at a trainer"
                f"{fallback_label(tier)}")
    level = character['level']
    reach = (f"{profession} is capped at {tier['cap']}" if group['capped']
             else f"Before {profession} reaches {tier['cap']}")
    now = f"{level} → {tier['required_level']}" if level is not None else f"to {tier['required_level']} (level unknown)"
    return f"{reach}: level {name} {now} to train {tier['name']}{fallback_label(tier)}"


def merged_tier_text(step, character):
    professions = [g['profession'] for g in step['groups']]
    names = ', '.join(professions[:-1]) + ' and ' + professions[-1]
    tier = step['tier']
    if step['kind'] == 'train':
        return f"Train {tier['name']} at a trainer: {names}{fallback_label(tier)}"
    level = character['level']
    now = f"{level} → {tier['required_level']}" if level is not None else f"to {tier['required_level']} (level unknown)"
    return f"Level {character['character'][0]} {now} to train {tier['name']} {names}{fallback_label(tier)}"


def mob_label(npc, names):
    if npc is None:
        return 'Gathering · zone only'
    return f'{names[npc]} (NPC {npc})' if npc in names else f'NPC {npc}'


def spot_position(spot):
    cell = spot.get('cell')
    if cell is None:
        return '—'
    half = spot['cell_percent'] // 2
    return f'around {cell[0] + half}, {cell[1] + half}'


def spot_coin_share(spot):
    coin, total = spot['coin_copper'], spot['value_copper']
    if coin is None:
        return 'Coin unavailable'
    return f'Coin {coin * 100 // total}%' if total else 'Coin unknown'


def session_profit_basis(character):
    bases = [r.get('profit_basis') for r in character['crafts']]
    if bases and all(bases):
        return ' at cautious sale price'
    return ' (includes crafts at cautious sale price)' if any(bases) else ''


def session_display(options, arguments):
    """Readable session projection retaining all evidence; no extra loads or estimates."""
    characters = []
    for character in options['characters']:
        groups = []
        for group in character['professions']:
            recipes = [r | {'skillup_band': recipe_band(r, group['rank'], arguments['catalogs'])}
                       for r in group['recipes']]
            groups.append(group | {'recipes': recipes, 'milestones': [
                m | {'recipes': [r for r in recipes if r['required_skill'] == m['skill']]}
                for m in group['milestones']]})
        farming = character['farming']
        spots = [spot | {'mob': mob_label(spot['npc_id'], farming.get('npc_names', {})),
                          'position': spot_position(spot), 'coin_share': spot_coin_share(spot)}
                 for spot in farming['spots']]
        characters.append(character | {'professions': groups, 'farming': farming | {'spots': spots},
                                       'options_text': [step_text(step, character, options['window'])
                                                        for step in character['next_steps']]})
    return options | {'characters': characters}


def recipe_band(row, rank, catalogs):
    recipe = next((c['recipes_by_id'].get(row['recipe_id']) for c in catalogs
                   if c['catalog_id'] == row['catalog_id']), None)
    colors = recipe.get('skillup_colors') if recipe else None
    if not colors:
        return 'skill-up range unknown: catalog has no colour bands'
    if rank is None:
        return 'skill-up colour unknown: character rank unknown'
    orange, yellow, green, grey = colors
    color = band_colour(rank, colors)
    return f'{color} at rank {rank} · orange {orange}, yellow {yellow}, green {green}, grey {grey}'


def band_colour(rank, colors):
    orange, yellow, green, grey = colors
    if rank < orange:
        return 'not yet'
    if orange == green:
        return 'no reliable skill-ups'
    return next((label for threshold, label in ((yellow, 'orange'), (green, 'yellow'), (grey, 'green'))
                 if rank < threshold), 'grey')
