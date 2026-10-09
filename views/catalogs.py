"""Recipe catalogs: the sidebar experience's catalogs and their status, then one flow to add or update a profession.

Choose a profession, its saved page and its recipes; the review below them follows every choice and writes
nothing. **Save catalog** writes exactly what the review shows: its key carries a fingerprint of the choices and
of the files on disk, so a click on a review that has since changed does nothing. Brownstone never downloads the
Wowhead page; the user saves it in a browser.
"""
import hashlib
import json
import os
from datetime import UTC, date, datetime

import streamlit as st

from brownstone import recipe_catalogs as rc
from brownstone.crafting import parse_recipe_catalog
from brownstone.money import format_money
from brownstone.recipe_import import archived_saved_at
from views.common import EXPERIENCES, show_context
from views.crafting import _materials, _recipe_heading

GAMES = {game: EXPERIENCES[game] for game in rc.CATALOG_PREFIXES}  # Experiences that have catalogs.
KINDS = {"yield": "yield", "vendor": "vendor status and price", "post-launch": "post-launch"}
WRITTEN = "catalogs-written"  # Session key: the last write's summary, shown after the page reloads.
PICK = "catalogs-pick"  # Session key: the profession to select after a write (the one just saved).
ARCHIVED, UPLOAD = "archived", "upload"
NEW = "new:"  # Profession choices without a catalog yet are "new:<profession>"; others are catalog names.


def render(config, sources, config_dir, archive_dir):
    st.subheader("Recipe catalogs")
    show_context(config)
    st.caption("One catalog per game version and profession, generated from a Wowhead page you save in your "
               "browser. Brownstone never downloads from Wowhead.")
    _written()
    try:
        entries = rc.find_catalogs(config_dir)
    except Exception as error:
        st.error(f"Could not read the selection files: {error}")
        return
    game = config["game_version"]  # The sidebar experience, like every other page.
    if game not in GAMES:
        st.info(f"{EXPERIENCES.get(game, game)} has no recipe catalogs. Choose Classic Era or WoW Forever "
                "in the sidebar to manage catalogs.")
        return
    entries = [entry for entry in entries if entry["selection"]["game_version"] == game]
    st.markdown(f"#### {GAMES[game]} catalogs")
    today = datetime.now(UTC).date()
    statuses = [rc.catalog_status(entry, sources, archive_dir, today) for entry in entries]
    if statuses:
        _status_table(statuses)
    else:
        st.info(f"No {GAMES[game]} catalogs yet. Add a profession below.")
    missing = rc.missing_professions(entries)[game]
    st.caption(f"No {GAMES[game]} catalog yet: "
               + (", ".join(rc.profession_title(p).lower() for p in missing) or "none"))
    _details(statuses)
    _recipe_view(entries)
    st.markdown("#### Add or update a profession")
    _manage(game, entries, missing, sources, config_dir, archive_dir)


def _status_table(statuses):
    rows = [{
        "Profession": rc.profession_title(status["profession"]), "Recipes": status["recipes"],
        "Items": status["items"], "Version": status["catalog_version"] or "not generated",
        "Rules": status["rules_version"], "Page saved": status["saved_at"],
        "Game build": status["build"] or "page not archived here", "SHA-256": (status["sha256"] or "")[:12],
        "Unconfirmed": len(status["unconfirmed"]), "Refresh due": "yes" if status["refresh"] else "no",
    } for status in statuses]
    st.dataframe(rows, hide_index=True, width="stretch")


def _details(statuses):
    for status in statuses:
        if not status["unconfirmed"] and not status["refresh"]:
            continue
        with st.expander(f"{status['label']}: {len(status['unconfirmed'])} unconfirmed"
                         + (" · refresh due" if status["refresh"] else "")):
            for reason in status["refresh"]:
                st.warning(f"Refresh due: {reason}.")
            st.dataframe([{"Value": KINDS[value["kind"]], "Recipe or item": value["name"], "Note": value["note"]}
                          for value in status["unconfirmed"]], hide_index=True, width="stretch")


def _manage(game, entries, missing, sources, config_dir, archive_dir):
    """Step 1: one profession list, existing catalogs (to update) first, then professions without one."""
    by_name = {entry["name"]: entry for entry in entries}
    options = list(by_name) + [NEW + profession for profession in missing]
    key = f"manage-{game}"
    pending = st.session_state.pop(PICK, None)
    if pending in options:  # Set before the widget exists, so the profession just saved stays selected.
        st.session_state[key] = pending

    def label(option):
        if option.startswith(NEW):
            return f"{rc.profession_title(option[len(NEW):])} · new catalog"
        catalog = by_name[option]["catalog"] or {}
        return (f"{rc.profession_title(by_name[option]['selection']['profession'])} · update "
                f"({len(catalog.get('recipes', []))} recipes)")

    choice = st.selectbox("1. Profession", options, key=key, format_func=label)
    if choice.startswith(NEW):
        _add(game, choice[len(NEW):], sources, config_dir, archive_dir)
    else:
        _update(game, by_name[choice], sources, archive_dir)


def _page_upload(label_key, game, profession, archive_dir):
    """The uploaded page's bytes, SHA-256, name and save date, or None until a page is uploaded."""
    url = rc.wowhead_page_url(game, profession)
    st.markdown(f"Save [{url}]({url}) in your browser, then upload the saved page.")
    upload = st.file_uploader("Saved Wowhead page", type=["html", "htm"], key=f"page-{label_key}")
    if upload is None:
        return None
    raw = upload.getvalue()
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        known = archived_saved_at(raw, archive_dir)
    except ValueError as error:
        st.error(f"This is not a saved Wowhead profession page: {error}")
        return None
    # Keyed by the page's bytes, so a date typed for one file never carries over to another.
    saved = st.date_input("Date you saved the page", value=date.fromisoformat(known) if known else date.today(),
                          key=f"saved-{label_key}-{sha256[:16]}", disabled=known is not None,
                          help="Already archived pages keep their recorded date." if known else None)
    return raw, sha256, upload.name, saved.isoformat()


def _page_for_update(entry, archive_dir):
    """The archived page behind the catalog, or a newly saved one; same shape as ``_page_upload``."""
    selection = entry["selection"]
    copy = rc.archived_copy(entry, archive_dir)
    source = UPLOAD
    if copy is not None:
        saved_at = entry["catalog"]["verified_at"]
        source = st.radio("Page", [ARCHIVED, UPLOAD], horizontal=True, key=f"update-source-{entry['name']}",
                          format_func=lambda s: f"Archived page saved {saved_at}" if s == ARCHIVED
                          else "Upload a newly saved page")
    if source == ARCHIVED:
        raw = copy.read_bytes()
        return raw, hashlib.sha256(raw).hexdigest(), copy.name, saved_at
    return _page_upload(f"update-{entry['name']}", selection["game_version"], selection["profession"],
                        archive_dir)


def _token(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _update(game, entry, sources, archive_dir):
    st.markdown("**2. Saved page**")
    page = _page_for_update(entry, archive_dir)
    if page is None:
        return
    raw, sha256, page_name, saved_at = page
    try:
        extract = rc.read_page(raw, game, entry["selection"]["profession"], saved_at)
    except ValueError as error:
        st.error(f"Cannot use this page: {error}")
        return
    st.markdown("**3. Recipes**")
    chosen = _choose(extract, f"update-{entry['name']}-{sha256[:16]}", rc.current_choices(entry))
    if chosen is None:
        return
    rules = _rules(game, sources, f"update-rules-{entry['name']}", entry["selection"]["rules_version"])
    # The files on disk are part of the review: if either changes, the old Save click is ignored.
    on_disk = [path.read_text(encoding="utf-8") if path.exists() else None
               for path in (entry["selection_path"], entry["catalog_path"])]
    token = _token("update", entry["name"], sha256, saved_at, on_disk, chosen, rules)
    st.markdown("**4. Review and save**")
    _update_review(entry, (raw, page_name, saved_at), archive_dir, chosen, rules, token)


def _update_review(entry, page, archive_dir, chosen, rules, token):
    """The live review of an update, and the Save button that writes exactly it."""
    raw, page_name, saved_at = page
    try:
        preview = rc.preview_update(entry, raw, saved_at, chosen, rules)
    except Exception as error:
        st.error(f"Cannot use this page: {error}")
        return
    _show_page(preview)
    if not preview["changed"]:
        st.info("Nothing to save: this page and these choices give the current catalog exactly.")
        return
    _summary(entry["catalog"], preview["catalog"], preview["catalog_version"])
    _show_changes(preview["changes"])
    for note in preview["dropped_notes"]:
        st.warning(f"Selection note removed: {note}.")
    with st.expander("Selection file after saving"):
        st.code(preview["selection_text"], language="toml")
    if st.button("Save catalog", type="primary", key=f"save-{token[:16]}"):
        _write(lambda: rc.regenerate(entry, raw, page_name, saved_at, archive_dir, chosen, rules), entry["name"])


def _add(game, profession, sources, config_dir, archive_dir):
    st.markdown("**2. Saved page**")
    upload = _page_upload(f"add-{game}-{profession}", game, profession, archive_dir)
    if upload is None:
        return
    raw, sha256, page_name, saved_at = upload
    try:
        extract = rc.read_page(raw, game, profession, saved_at)
    except ValueError as error:
        st.error(f"Cannot use this page: {error}")
        return
    st.markdown("**3. Recipes**")
    chosen = _choose(extract, f"add-{game}-{profession}-{sha256[:16]}", rc.choices([]))
    if chosen is None:
        return
    rules = _rules(game, sources, f"add-rules-{game}", None)
    notes = st.text_input("Notes (optional)", key="add-notes")
    try:
        selection = rc.new_selection(game, profession, rules, chosen, notes)
    except ValueError as error:
        st.info(str(error))
        return
    st.markdown("**4. Review and save**")
    try:
        preview = rc.preview_new(config_dir, raw, selection, saved_at)
    except Exception as error:
        st.error(f"Cannot build this catalog: {error}")
        return
    _show_page(preview)
    _summary(None, preview["catalog"], selection["catalog_version"])
    st.caption(f"Creates {preview['name']}: {len(selection['recipes'])} chosen recipes plus the intermediates "
               "they need.")
    with st.expander("Selection file to write"):
        st.code(preview["selection_text"], language="toml")
    token = _token("add", sha256, saved_at, selection, preview["text"])
    if st.button("Save catalog", type="primary", key=f"save-{token[:16]}"):
        _write(lambda: rc.create(config_dir, raw, page_name, selection, saved_at, archive_dir), preview["name"])


def _choose(extract, key, start):
    """The user's choices (``rc.choices``), starting from ``start``; None until they are complete."""
    counts = rc.recipe_counts(extract)
    st.caption(f"{counts['offered']} of {len(extract['recipes'])} recipes on this page make an item and can be "
               f"chosen. Left out: {counts['no item']} make no item (for example enchants applied to gear), "
               f"{counts['no fixed yield']} have no fixed yield on Wowhead, {counts['shared item']} make an item "
               f"other recipes also make (such items are bought), {counts['seasonal']} belong to a seasonal realm "
               "such as Season of Discovery.")
    candidates = rc.candidate_recipes(extract)
    names = {recipe["id"]: f"{recipe['name']} (skill {recipe['learnedat'] or 0})" for recipe in candidates}
    recipe_key, vendor_key = f"{key}-recipes", f"{key}-vendors"
    if recipe_key not in st.session_state:
        st.session_state[recipe_key] = [r for r in start["recipes"] if r in names]
        unavailable = [r for r in start["recipes"] if r not in names]
        if unavailable:
            st.warning(f"No longer offered by this page, so left out: {unavailable}")
    _bulk_select(extract, key, recipe_key)
    picked = st.multiselect("Recipes", list(names), format_func=names.get, key=recipe_key,
                            help="Type to search. Intermediates these need are added automatically.")
    st.caption(f"{len(picked)} of {len(names)} recipes chosen.")
    if not picked:
        st.info("Choose at least one recipe.")
        return None
    chosen = rc.choices(picked)
    try:
        offered = rc.vendor_candidates(extract, chosen)
    except ValueError as error:
        st.error(f"Cannot use these recipes: {error}")
        return None
    st.session_state[vendor_key] = [v for v in st.session_state.get(vendor_key, start["vendor"]) if v in offered]
    vendors = st.multiselect("Sold by vendors (marked unconfirmed until checked)", offered, key=vendor_key,
                             format_func=lambda i: extract["items"][str(i)]["name"],
                             help="A Wowhead buy price is not evidence of a vendor. Unmarked items are priced "
                                  "from the auction house.")
    return rc.choices(picked, vendors)


def _bulk_select(extract, key, recipe_key):
    """Add or remove every recipe matching a name and skill range (runs before the multiselect it changes)."""
    # Only offered recipes count: the profession spell itself is listed at skill 9999.
    top = max((recipe["learnedat"] or 0 for recipe in rc.candidate_recipes(extract)), default=0)
    name_col, skill_col = st.columns(2)
    name = name_col.text_input("Recipe name contains", key=f"{key}-name")
    low, high = skill_col.slider("Skill range", 0, top, (0, top), key=f"{key}-skill") if top else (0, 0)
    matching = [recipe["id"] for recipe in rc.candidate_recipes(extract, name, low, high)]
    add, remove = st.columns(2)
    if add.button(f"Add all {len(matching)} matching", key=f"{key}-add"):
        st.session_state[recipe_key] = sorted(set(st.session_state[recipe_key]) | set(matching))
    if remove.button(f"Remove all {len(matching)} matching", key=f"{key}-remove"):
        st.session_state[recipe_key] = [r for r in st.session_state[recipe_key] if r not in set(matching)]


def _rules(game, sources, key, current):
    """The rules_version to write: a configured market's, or typed when no market of this game sets one."""
    rules = sorted({s["rules_version"] for s in sources if s["game_version"] == game and s.get("rules_version")}
                   | ({current} if current else set()))
    if rules:
        return st.selectbox("Rules version (the market it prices)", rules, key=key,
                            index=rules.index(current) if current else 0)
    return st.text_input("Rules version (no configured market sets one)", key=f"{key}-text")


def _show_page(preview):
    build = rc.build_label(preview["patch"], preview["build"])
    st.caption(f"Page saved {preview['saved_at']} · game build {build or 'not stated on the page'} · "
               f"SHA-256 {preview['sha256'][:12]}… · nothing is written until you save")


def _summary(before, after, version):
    """Before and after counts, and the recipes saving would add or remove, by name."""
    old = {recipe["recipe_id"]: recipe["name"] for recipe in (before or {}).get("recipes", [])}
    new = {recipe["recipe_id"]: recipe["name"] for recipe in after["recipes"]}
    added = sorted(new[r] for r in new.keys() - old.keys())
    removed = sorted(old[r] for r in old.keys() - new.keys())
    items_before = len((before or {}).get("items", []))
    st.markdown(f"Saving gives **{_count(len(new), 'recipe')}** (now {len(old)}: {len(added)} added, "
                f"{len(removed)} removed) and **{_count(len(after['items']), 'item')}** (now {items_before}), "
                f"catalog version **{version}**.")
    for title, names in ((f"Recipes added ({len(added)})", added), (f"Recipes removed ({len(removed)})", removed)):
        if names:
            with st.expander(title):
                st.markdown("\n".join(f"- {name}" for name in names))


def _count(number, noun):
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _show_changes(changes):
    if changes:
        with st.expander(f"Every recipe and vendor price change ({len(changes)})"):
            st.dataframe([{"Change": line} for line in changes], hide_index=True, width="stretch")
    elif changes is not None:
        st.caption("No recipe or vendor price changes; the catalog's header or evidence (date, SHA-256, "
                   "rules version) changes.")


def _write(action, name):
    try:
        result = action()
    except Exception as error:
        st.error(f"Nothing was written for {name}: {error}")
        return
    for key in [key for key in st.session_state if key.endswith(("-recipes", "-vendors"))]:
        del st.session_state[key]  # Choices restart from the files just written.
    st.session_state[WRITTEN] = {"name": name, "version": result["catalog_version"],
                                 "tracked": [os.path.relpath(path, rc.ROOT) for path in result["tracked"]],
                                 "archived": [os.path.relpath(path, rc.ROOT) for path in result["archived"]]}
    st.session_state[PICK] = name
    st.rerun()  # Reload so the status table and the board read the new files.


def _written():
    result = st.session_state.pop(WRITTEN, None)
    if result is None:
        return
    st.toast(f"Saved {result['name']} catalog version {result['version']}.")  # Seen wherever the page is scrolled.
    st.success(f"Saved {result['name']} catalog version {result['version']}. The table below shows it.")
    if result["tracked"]:
        st.markdown("Changed tracked files, to review and commit yourself:\n"
                    + "\n".join(f"- `{path}`" for path in result["tracked"]))
    st.caption("Archived page (not tracked): " + ", ".join(result["archived"]))


def _recipe_view(entries):
    generated = {entry["name"]: entry for entry in entries if entry["catalog"]}
    if not generated:
        return
    with st.expander("View a catalog recipe"):
        name = st.selectbox("Recipe catalog", list(generated),
                            format_func=lambda name: rc.profession_title(generated[name]["selection"]["profession"]),
                            key="catalogs-recipe-catalog")
        try:
            catalog = parse_recipe_catalog(generated[name]["catalog"])
        except ValueError as error:
            st.error(f"Cannot inspect this catalog: {error}")
            return
        recipes = catalog["recipes_by_id"]
        recipe_id = st.selectbox("Catalog recipe", list(recipes), format_func=lambda rid: recipes[rid]["name"],
                                 key=f"catalogs-recipe-{name}")
        _recipe_heading(catalog, recipe_id)
        recipe = recipes[recipe_id]
        st.caption(f"Learned from: {rc.learning_label(recipe)}")
        cost = recipe.get("training_cost_copper")
        st.caption(f"Training cost: {format_money(cost) if cost is not None else 'unknown'}")
        try:
            _materials(catalog, recipe_id)
        except ValueError as error:
            st.warning(f"This recipe cannot be expanded: {error}")
