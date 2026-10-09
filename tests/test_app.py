"""Offline UI smoke test using an isolated saved Classic snapshot."""
from pathlib import Path

import pytest

from brownstone.config import read_sources
from brownstone.pipeline import run

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402  (only after the skip check)

ROOT = Path(__file__).resolve().parents[1]


def test_action_board_saved_snapshot_and_retail_browse(tmp_path, monkeypatch):
    sources = read_sources(ROOT / "config/market.toml")
    for source in sources:
        source["data_dir"] = tmp_path / "data"
    source = tmp_path / "items.csv"
    source.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n" +
        "\n".join(f"{i},Item {i},0,{p},0,0," for i, p in
                  {2592: 10, 4240: 1000, 4338: 100, 10050: 10000,
                   14047: 1000, 8170: 500, 14046: 20000}.items()) + "\n")
    run(sources[0], source)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert not any(w.label == "Recipe catalog" for w in at.selectbox)
    assert at.radio[0].value == "Today"
    at.radio[0].set_value("Crafting").run()
    assert any(m.value == "#### Action Board" for m in at.markdown)
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert set(table["Profession"]) == {"Alchemy", "Enchanting", "Tailoring"}
    next(w for w in at.selectbox if w.label == "Profession").set_value("tailoring").run()
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert len(table) == 3
    assert table.iloc[0]["Item"] == "Mageweave Bag"
    assert table.iloc[2]["Action"] == "negative margin"
    assert set(table["Output depth"]) == {"Unavailable"}
    assert table["Output listings"].isna().all() and table["Output units"].isna().all()
    assert all("Unavailable" in text for text in table["Direct input depth"])
    inputs = next(t.value for t in at.dataframe if "Input" in t.value.columns)
    assert set(inputs["Market depth"]) == {"Unavailable"}
    assert inputs["Market listings"].isna().all() and inputs["Market units"].isna().all()
    next(w for w in at.selectbox if w.label == "Rank by").set_value("margin").run()
    assert not at.exception
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert table.iloc[0]["Item"] == "Woolen Bag"
    assert any(m.label == "Break-even sale price" for m in at.metric)
    at.radio[0].set_value("Opportunities").run()
    assert not at.exception
    assert any("cannot run" in i.value for i in at.info)  # Classic historical values are zero.
    next(w for w in at.selectbox if w.label == "Experience").set_value("retail").run()  # Retail still works.
    assert any("several enabled sources" in i.value for i in at.info)  # Area 52 and region commodities.
    next(w for w in at.selectbox if w.label == "Data source").set_value(0).run()
    at.radio[0].set_value("Browse market").run()
    assert not at.exception
    assert not any(m.value == "#### Action Board" for m in at.markdown)
    assert any(h.value == "Browse market" for h in at.subheader)


def test_addon_source_imports_on_click_and_prices_the_forever_board(tmp_path, monkeypatch):
    from test_scans import finished_now, forever_scan_file, listing, scan, write_scans
    sources = read_sources(ROOT / "config/market.toml")
    addon = next(source for source in sources if source["provider"] == "addon")
    assert not addon["enabled"]  # Disabled in the tracked config; enabled per machine in market.local.toml.
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=forever_scan_file(tmp_path, finished_now()),
                 scan_evidence={"faction": "Alliance"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any("Refresh or import" in i.value for i in at.info)  # Nothing imported until clicked.
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception
    assert any("Imported" in s.value for s in at.success)
    assert not any(w.label == "Recipe catalog" for w in at.selectbox)
    assert at.radio[0].value == "Today"
    at.radio[0].set_value("Crafting").run()
    combined = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert {"Alchemy", "Tailoring"} <= set(combined["Profession"])  # Plus any professions added in the app.
    alchemy = combined[combined["Profession"] == "Alchemy"]
    dyes = alchemy.set_index("Item")
    assert (dyes.loc["Magenta Dye", "Output listings"], dyes.loc["Magenta Dye", "Output units"]) == (1, 4)
    assert (dyes.loc["Cerulean Dye", "Output listings"], dyes.loc["Cerulean Dye", "Output units"]) == (1, 2)
    absent = alchemy[alchemy["Output depth"] == "Not listed"]
    assert len(absent) == len(alchemy) - 2
    assert (absent["Output listings"] == 0).all() and (absent["Output units"] == 0).all()
    next(w for w in at.selectbox if w.label == "Profession").set_value("tailoring").run()
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert table.iloc[0]["Item"].startswith("Runecloth Bag") and table.iloc[0]["Action"] == "potential craft"
    assert set(table["Action"][1:]) == {"missing prices"}  # Bags without listings in the fixture scan.
    bag = table.iloc[0]
    assert (bag["Output listings"], bag["Output units"], bag["Output depth"]) == (2, 2, "Listed")
    assert bag["Craft cost (g)"] == 3.35 and bag["Profit (g)"] == 2.35
    assert "Bolt of Runecloth: 1 listings / 2 units" in bag["Direct input depth"]
    assert "Rune Thread: Not listed" in bag["Direct input depth"]
    assert set(table["Output depth"][1:]) == {"Not listed"}
    assert (table["Output listings"][1:] == 0).all() and (table["Output units"][1:] == 0).all()
    inputs = next(t.value for t in at.dataframe if "Input" in t.value.columns).set_index("Input")
    assert inputs.loc["Bolt of Runecloth", "Choice"] == "craft"
    assert (inputs.loc["Bolt of Runecloth", "Market listings"],
            inputs.loc["Bolt of Runecloth", "Market units"]) == (1, 2)
    assert inputs.loc["Rune Thread", "Choice"] == "vendor"
    assert inputs.loc["Rune Thread", "Market depth"] == "Not listed"
    # An older import cannot replace either the displayed prices or their depth.
    older = scan("older", finished_now() - 3600, [listing(14046, 99, 9900)],
                 house={"zone": "Stormwind City", "npc_name": "Auctioneer Fitch"})
    addon["scan_path"] = write_scans(tmp_path / "older.lua", older)
    at.run()  # Without a plain rerun, AppTest does not register a second click on the same button.
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception
    assert any("older completed: imported" in s.value for s in at.success)
    after = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert after.equals(table)


def classic_sources(tmp_path):
    sources = [source for source in read_sources(ROOT / "config/market.toml") if source["enabled"]]
    for source in sources:
        source["data_dir"] = tmp_path / "data"
    return sources


def test_browse_market_lists_saved_items_blanks_zero_prices_and_searches(tmp_path, monkeypatch):
    sources = classic_sources(tmp_path)
    items = tmp_path / "items.csv"
    items.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n"
                     "2592,Wool Cloth,0,120,0,0,\n4306,Silk Cloth,900,0,0,0,\n", encoding="utf-8")
    run(sources[0], items)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    at.radio[0].set_value("Browse market").run()
    assert not at.exception
    table = at.dataframe[0].value
    assert list(table["Item"]) == ["Silk Cloth", "Wool Cloth"]
    assert table.set_index("Item").loc["Wool Cloth", "Minimum buyout (g)"] == 0.012
    assert table["Market value (g)"].isna().sum() == 1  # Zero is unavailable, shown blank, never free.
    next(t for t in at.text_input if t.label == "Find an item").set_value("silk").run()
    assert list(at.dataframe[0].value["Item"]) == ["Silk Cloth"]
    next(t for t in at.text_input if t.label == "Find an item").set_value("no such item").run()
    assert any("No items match" in i.value for i in at.info)


def test_refresh_reports_success_and_failure_without_losing_saved_data(tmp_path, monkeypatch):
    sources = classic_sources(tmp_path)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    calls = []

    def offline(config):
        calls.append(config["source_id"])
        if len(calls) == 1:
            raise RuntimeError("network unreachable")

    monkeypatch.setattr("brownstone.pipeline.run", offline)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not calls  # Opening the app never downloads (UI-01).
    next(b for b in at.button if b.label == "Refresh from TSM").click().run()
    assert any("Refresh failed: network unreachable" in e.value for e in at.error)
    next(b for b in at.button if b.label == "Refresh from TSM").click().run()
    assert any("refreshed and saved" in s.value for s in at.success)
    assert calls == ["classic-us-mankrik-alliance"] * 2


def test_import_of_a_file_without_a_complete_scan_says_prices_are_unchanged(tmp_path, monkeypatch):
    from test_scans import finished_now, scan, write_scans
    addon = next(source for source in read_sources(ROOT / "config/market.toml") if source["provider"] == "addon")
    scan_file = write_scans(tmp_path / "scan.lua", scan("cut-short", finished_now(), [], status="stopped",
                                                        reported=5, house={"zone": "Stormwind City",
                                                                           "npc_name": "Auctioneer Fitch"}))
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=scan_file)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception
    assert any("No complete scan among the imported scans, so prices are unchanged" in w.value for w in at.warning)


def test_no_enabled_source_explains_how_to_enable_one(monkeypatch):
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert any("No enabled data source" in e.value for e in at.error)


def test_importing_nothing_new_warns_to_reload_instead_of_claiming_success(tmp_path, monkeypatch):
    from test_scans import finished_now, forever_scan_file
    addon = next(source for source in read_sources(ROOT / "config/market.toml") if source["provider"] == "addon")
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=forever_scan_file(tmp_path, finished_now()),
                 scan_evidence={"faction": "Alliance"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert any("/bscan clear" in i.value for i in at.info)  # Something new was saved: clearing is safe.
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not any(b.label == "Import addon scan" for b in at.button)
    assert not at.success
    assert any(w.value.startswith("Nothing new") and "/reload" in w.value for w in at.caption)


def test_combined_board_duplicate_recipe_selection_uses_own_catalog(tmp_path, monkeypatch):
    from copy import deepcopy

    from test_action_board import catalog
    sources = classic_sources(tmp_path)[:1]
    items = tmp_path / "items.csv"
    items.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n"
                     "2592,Wool Cloth,10,10,0,0,\n4240,Woolen Bag,1000,1000,0,0,\n")
    run(sources[0], items)
    first = catalog()
    second = deepcopy(first)
    second["profession"] = "alchemy"
    for recipe in second["recipes"]:
        recipe["profession"] = "alchemy"
    next(item for item in second["items"] if item["item_id"] == 2321)["vendor_price_copper"] = 200
    entries = [{"name": "tailoring", "catalog": first}, {"name": "alchemy", "catalog": second}]
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    monkeypatch.setattr("brownstone.recipe_catalogs.find_catalogs", lambda *args: entries)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    assert not any(w.label in {"Recipe catalog", "Data source"} for w in at.selectbox)
    assert at.radio[0].value == "Today"
    at.radio[0].set_value("Crafting").run()
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert len(table) == 6 and set(table["Profession"]) == {"Tailoring", "Alchemy"}
    wool = table[table["Item"] == "Woolen Bag"].set_index("Profession")
    assert wool.loc["Tailoring", "Craft cost (g)"] == .019
    assert wool.loc["Alchemy", "Craft cost (g)"] == .029
    recipe = next(w for w in at.selectbox if w.label == "Recipe")
    recipe.set_value(("alchemy", 3757)).run()
    assert not at.exception
    assert next(m for m in at.metric if m.label == "Craft cost").value == "2s 90c"
    inputs = next(t.value for t in at.dataframe if "Input" in t.value.columns).set_index("Input")
    assert inputs.loc["Fine Thread", "Unit cost (g)"] == .02
    next(w for w in at.selectbox if w.label == "Recipe").set_value(("tailoring", 3757)).run()
    assert next(m for m in at.metric if m.label == "Craft cost").value == "1s 90c"
    next(w for w in at.selectbox if w.label == "Profession").set_value("alchemy").run()
    assert not at.exception
    filtered = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert list(filtered["Rank"]) == list(table[table["Profession"] == "Alchemy"]["Rank"])
    # A cycle in one catalog remains one unsupported row and cannot hide the other rows.
    next(recipe for recipe in second["recipes"] if recipe["recipe_id"] == 18405)["inputs"].append(
        {"item_id": 14046, "quantity": 1})
    at.run()
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert len(table) == 3 and table.iloc[-1]["Action"] == "unsupported recipe"
    errors = next(e for e in at.expander if e.label == "1 recipes could not be evaluated")
    assert not errors.proto.expanded
    assert list(errors.dataframe[0].value["Output"]) == ["Runecloth Bag"]
    assert "Recipe cycle" in errors.dataframe[0].value.iloc[0]["Reason"]
    assert not any("could not be evaluated" in w.value for w in at.warning)
    next(w for w in at.selectbox if w.label == "Recipe").set_value(("alchemy", 18405)).run()
    assert not at.exception
    assert any("This recipe cannot be evaluated: Recipe cycle" in e.value for e in at.error)
    # A catalog that fails to parse is named, and the other catalog still prices.
    entries[1] = {"name": "broken", "catalog": {"profession": "alchemy"}}
    at.run()
    assert not at.exception
    assert any(w.value.startswith("Recipe catalog broken unavailable") for w in at.warning)
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert set(table["Profession"]) == {"Tailoring"}


def test_selected_experience_upgrades_its_own_database(tmp_path, monkeypatch):
    import duckdb

    from brownstone.storage import MIGRATIONS, SCHEMA_VERSION, schema_version
    classic, forever = (classic_sources(tmp_path)[0], {**classic_sources(tmp_path)[0], "game_version": "forever",
                                                       "source_id": "forever-test", "data_dir": tmp_path / "forever"})
    classic["data_dir"] = tmp_path / "classic-old"
    classic["data_dir"].mkdir()
    with duckdb.connect(str(classic["data_dir"] / "brownstone.duckdb")) as db:
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        MIGRATIONS[1](db)
        MIGRATIONS[2](db)
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '2')")
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [classic, forever])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    # Forever opens first even though market.toml lists Classic first; Classic's database is untouched.
    assert next(w for w in at.selectbox if w.label == "Experience").value == "forever"
    assert not (classic["data_dir"] / "brownstone.v2.backup.duckdb").exists()
    next(w for w in at.selectbox if w.label == "Experience").set_value("classic").run()
    assert not at.exception
    assert any("upgraded" in t.value for t in at.toast)
    assert (classic["data_dir"] / "brownstone.v2.backup.duckdb").exists()
    with duckdb.connect(str(classic["data_dir"] / "brownstone.duckdb"), read_only=True) as db:
        assert schema_version(db) == SCHEMA_VERSION


def test_incompatible_catalogs_inspect_without_prices_and_link_to_management(tmp_path, monkeypatch):
    source = classic_sources(tmp_path)[0]
    source["rules_version"] = "classic-new-rules"
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [source])
    monkeypatch.setattr("brownstone.recipe_catalogs.ARCHIVE_DIR", tmp_path / "archive")
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    at.radio[0].set_value("Crafting").run()
    assert not at.exception
    assert any("No compatible recipe catalog for classic / classic-new-rules" in i.value for i in at.info)
    mismatches = [i.value for i in at.info if "Rules mismatch" in i.value]
    assert len(mismatches) == 3 and all("classic-era" in text and "classic-new-rules" in text
                                       for text in mismatches)
    assert len([w for w in at.selectbox if w.label == "Inspect recipe"]) == 3
    assert not at.metric and not any("Action" in t.value.columns for t in at.dataframe)
    assert not any(w.label == "Recipe catalog" for w in at.selectbox)
    next(b for b in at.button if b.label == "Open Recipe catalogs").click().run()
    assert not at.exception
    assert any(h.value == "Recipe catalogs" for h in at.subheader)
    assert any(m.value == "#### Classic Era catalogs" for m in at.markdown)  # Same experience as Crafting.
    assert next(w for w in at.selectbox if w.label == "Experience").value == "classic"
    assert any(f"Source {source['source_id']}" in c.value for c in at.caption)


def test_sidebar_experience_resolves_source_and_market_on_every_market_page(tmp_path, monkeypatch):
    from test_scans import finished_now, forever_scan_file
    sources = read_sources(ROOT / "config/market.toml")
    classic = sources[0]
    classic["data_dir"] = tmp_path / "classic"
    addon = next(source for source in sources if source["provider"] == "addon")
    addon.update(enabled=True, data_dir=tmp_path / "forever",
                 scan_path=forever_scan_file(tmp_path, finished_now()), scan_evidence={"faction": "Alliance"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [classic, addon])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    experience = next(w for w in at.selectbox if w.label == "Experience")
    assert experience.options == ["WoW Forever", "Classic Era"]
    experience.set_value("forever").run()
    assert not at.exception
    assert not any(w.label == "Data source" for w in at.selectbox)
    assert any(f"Source {addon['source_id']}" in c.value for c in at.caption)
    details = next(e for e in at.sidebar.expander if e.label == "Source details")
    assert not details.proto.expanded
    assert any(f"Market {addon['market_id']}" in c.value for c in details.caption)
    assert not any(c.value.startswith(("Source ", "Market "))
                   for c in at.sidebar.children.values() if c.type == "caption")
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception
    assert at.radio[0].value == "Today"
    context = f"Showing **WoW Forever** · source {addon.get('label', addon['source_id'])} · market {addon['market_id']}"
    for page in ["Today", "Crafting", "Browse market", "Opportunities", "Recipe catalogs", "Scan changes"]:
        next(w for w in at.radio if w.label == "View").set_value(page).run()
        assert not at.exception
        assert any(c.value == context for c in at.main.caption)
        details = next(e for e in at.sidebar.expander if e.label == "Source details")
        assert not details.proto.expanded
        assert not any(c.value.startswith(("Source ", "Market "))
                       for c in at.sidebar.children.values() if c.type == "caption")
    next(w for w in at.radio if w.label == "View").set_value("Crafting").run()
    table = next(t.value for t in at.dataframe if "Action" in t.value.columns)
    assert {"Alchemy", "Tailoring"} <= set(table["Profession"])
    forever = f"Showing **WoW Forever** · source {addon.get('label', addon['source_id'])} · market {addon['market_id']}"
    assert any(c.value == forever for c in at.caption)  # On the page itself, not only the sidebar.
    next(w for w in at.radio if w.label == "View").set_value("Browse market").run()
    assert not at.exception
    assert any(c.value == forever for c in at.caption)
    assert any("Runecloth Bag" in list(t.value["Item"]) for t in at.dataframe if "Item" in t.value.columns)
    next(w for w in at.radio if w.label == "View").set_value("Opportunities").run()
    assert any(c.value == forever for c in at.caption)
    assert any("cannot run" in i.value for i in at.info)
    next(w for w in at.selectbox if w.label == "Experience").set_value("classic").run()
    next(w for w in at.radio if w.label == "View").set_value("Browse market").run()
    assert not at.exception
    assert any(c.value.startswith(f"Showing **Classic Era** · source {classic.get('label', classic['source_id'])} · "
                                  f"market {classic['market_id']}") for c in at.caption)
    assert not at.dataframe  # Forever's imported data never leaks into Classic's separate source.
    assert any(f"Source {classic['source_id']}" in c.value for c in at.caption)


def test_multiple_sources_for_one_experience_require_explicit_sidebar_selection(tmp_path, monkeypatch):
    source = classic_sources(tmp_path)[0]
    other = {**source, "source_id": "other-observer", "label": "Another observer"}
    items = tmp_path / "items.csv"
    items.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n"
                     "2592,Wool Cloth,10,10,0,0,\n4240,Woolen Bag,1000,1000,0,0,\n")
    run(source, items)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [source, other])
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not at.exception
    # Nothing is chosen for the user: no source, market, import button or view until one is picked.
    assert next(w for w in at.selectbox if w.label == "Data source").value is None
    assert any("several enabled sources" in i.value for i in at.info)
    assert not at.dataframe and not at.button and not at.radio
    assert not any(c.value.startswith(("Source ", "Market ")) for c in at.caption)
    next(w for w in at.selectbox if w.label == "Data source").set_value(0).run()
    assert not at.exception
    assert at.radio[0].value == "Today"
    at.radio[0].set_value("Crafting").run()
    assert any("Action" in t.value.columns for t in at.dataframe)
    next(w for w in at.selectbox if w.label == "Data source").set_value(1).run()
    assert not at.exception
    assert not at.dataframe  # The same house and database, but another observer has no snapshot.
    assert any("Source other-observer" in c.value for c in at.caption)


def preview_addon(tmp_path, monkeypatch, records=None, sources_count=1):
    from test_scans import finished_now, listing, scan, write_scans
    addon = next(s for s in read_sources(ROOT / "config/market.toml") if s["provider"] == "addon")
    records = records if records is not None else [scan("one", finished_now(), [listing(1, 1, 50)]),
                                                   scan("two", finished_now(), [], status="stopped")]
    path = write_scans(tmp_path / "preview.lua", *records)
    addon.update(enabled=True, data_dir=tmp_path / "data", scan_path=path, scan_evidence={"faction": "Alliance"})
    sources = [addon]
    if sources_count == 2:
        sources.append({**addon, "source_id": "other", "label": "Other observer"})
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: sources)
    at = AppTest.from_file(str(ROOT / "app.py")).run()
    if sources_count == 2:
        next(w for w in at.selectbox if w.label == "Data source").set_value(0).run()
    return at, addon


def test_preview_subset_empty_selection_and_remaining_guidance(tmp_path, monkeypatch):
    at, addon = preview_addon(tmp_path, monkeypatch)
    assert not any(b.label == "Import addon scan" for b in at.button)
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not addon["data_dir"].exists()
    table = next(t.value for t in at.dataframe if "Scan ID" in t.value.columns)
    assert list(table["Import state"]) == ["New", "New"]
    assert list(table["Partial"]) == [False, True]
    assert all(t.endswith(" UTC") for t in table["Finished (UTC)"])
    at.multiselect[0].set_value([]).run()
    assert not any(b.label == "Import addon scan" for b in at.button)
    at.multiselect[0].set_value(["one"]).run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert any("remain unimported" in i.value for i in at.info)
    assert not any("Everything" in i.value for i in at.info)
    # The result replaces the reviewed table, which would otherwise still show the imported scan as New.
    assert not any("Scan ID" in t.value.columns for t in at.dataframe)
    assert not any(b.label == "Import addon scan" for b in at.button)
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert at.multiselect[0].value == ["two"]
    table = next(t.value for t in at.dataframe if "Scan ID" in t.value.columns)
    assert list(table["Import state"]) == ["Already imported", "New"]
    assert not at.exception


def test_preview_retryable_error_then_stale_file_invalidates_without_writes(tmp_path, monkeypatch):
    at, addon = preview_addon(tmp_path, monkeypatch)
    original = addon["scan_path"].read_bytes()
    addon["scan_path"].write_text("BrownstoneScanDB = {")
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert any("Preview failed" in e.value and "Preview again" in e.value for e in at.error)
    assert not any(b.label == "Import addon scan" for b in at.button)
    addon["scan_path"].write_bytes(original)
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    addon["scan_path"].write_bytes(original + b"\n")
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert any("Preview is stale" in e.value and e.value.count("Preview again") == 1 for e in at.error)
    assert not addon["data_dir"].exists()
    at.run()
    assert not any(b.label == "Import addon scan" for b in at.button)
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert at.success and not at.exception


def test_source_and_configuration_switch_discard_review_and_selection(tmp_path, monkeypatch):
    at, addon = preview_addon(tmp_path, monkeypatch, sources_count=2)
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    at.multiselect[0].set_value(["one"]).run()
    next(w for w in at.selectbox if w.label == "Data source").set_value(1).run()
    assert not at.multiselect and not any(b.label == "Import addon scan" for b in at.button)
    next(w for w in at.selectbox if w.label == "Data source").set_value(0).run()
    assert not at.multiselect
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert at.multiselect[0].value == ["one", "two"]
    addon["max_age_hours"] += 1
    at.run()
    assert not at.multiselect and not any(b.label == "Import addon scan" for b in at.button)
    assert not addon["data_dir"].exists() and not at.exception


def test_preview_marks_other_house_scans_and_imports_the_rest(tmp_path, monkeypatch):
    from test_scans import finished_now, listing, scan
    at, addon = preview_addon(tmp_path, monkeypatch, records=[
        scan("ours", finished_now(), [listing(1, 1, 50)]),
        scan("horde", finished_now(), [listing(2, 1, 50)], faction={"player": "Horde"})])
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not at.error
    table = next(t.value for t in at.dataframe if "Scan ID" in t.value.columns)
    assert list(table["Import state"]) == ["New", "Other house"]
    assert any("another auction house" in c.value and "horde" in c.value for c in at.caption)
    assert at.multiselect[0].options == ["ours"]
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert at.success and any("another auction house" in i.value for i in at.info)
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert any(w.value.startswith("Nothing new") for w in at.caption)
    assert not at.exception


def test_addon_source_upgrades_an_existing_older_database_on_load(tmp_path, monkeypatch):
    import duckdb

    from brownstone.storage import MIGRATIONS, SCHEMA_VERSION, schema_version
    data = tmp_path / "data"
    data.mkdir()
    with duckdb.connect(str(data / "brownstone.duckdb")) as db:
        db.execute("CREATE TABLE schema_info (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        MIGRATIONS[1](db)
        MIGRATIONS[2](db)
        db.execute("INSERT INTO schema_info VALUES ('schema_version', '2')")
    at, _ = preview_addon(tmp_path, monkeypatch)
    assert not at.exception and any("upgraded" in t.value for t in at.toast)
    with duckdb.connect(str(data / "brownstone.duckdb"), read_only=True) as db:
        assert schema_version(db) == SCHEMA_VERSION


def test_drop_import_page_machine_files_cleanup_and_stale_review(tmp_path, monkeypatch):
    from test_scans import finished_now, listing, scan, write_scans
    at, addon = preview_addon(tmp_path, monkeypatch)
    folder = tmp_path / "drop"
    folder.mkdir()
    addon.update(machine="mac", drop_folder=folder)
    win = write_scans(folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua",
                      scan("win", finished_now(), [listing(2, 1, 80)]))
    (folder / "copy.partial").write_bytes(b"partial")
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    files = next(t.value for t in at.dataframe if "File" in t.value.columns)
    assert set(files["Machine"].dropna()) == {"mac", "windows-pc"}
    assert any("Partial copy" in status for status in files["Status"])
    latest = next(t.value for t in at.dataframe if "Latest drop" in t.value.columns)
    assert not latest["Fully imported"].iloc[0]
    assert any("haven't played" in i.value for i in at.info)
    selection = next(w for w in at.multiselect if w.label.startswith("Files to import"))
    selection.set_value([]).run()
    assert not any(b.label == "Import addon scan" for b in at.button)
    next(w for w in at.multiselect if w.label.startswith("Files to import")).set_value([str(win)]).run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    latest = next(t.value for t in at.dataframe if "Latest drop" in t.value.columns)
    assert latest["Fully imported"].iloc[0]
    assert any(str(win) in s.value for s in at.success)
    # Duplicate files remain selectable explicitly to preserve a collection, default excludes them.
    selection = next(w for w in at.multiselect if w.label.startswith("Files to import"))
    selection.set_value([str(addon["scan_path"])]).run()
    addon["scan_path"].write_bytes(addon["scan_path"].read_bytes() + b"\n")
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert any("stale" in e.value for e in at.error)
    assert not at.exception


@pytest.mark.parametrize("drop_folder", [False, True])
def test_character_snapshot_import_page_unknown_bank_and_snapshot_only_files(tmp_path, monkeypatch, drop_folder):
    from test_character_snapshots import snapshot, write
    from test_scans import finished_now
    at, addon = preview_addon(tmp_path, monkeypatch)
    r = snapshot()
    r.update(captured_at=finished_now())
    r.pop("captured_at_utc")
    path = addon["scan_path"]
    if drop_folder:
        folder = tmp_path / "drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        path = folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua"
    write(path, [r])
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not at.exception
    snapshots = next(t.value for t in at.dataframe if "Snapshot ID" in t.value.columns)
    assert snapshots["Character"].tolist() == ["Alice"] and snapshots["Import state"].tolist() == ["new"]
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception and not at.error
    table = next(t.value for t in at.dataframe if "Bank (UTC)" in t.value.columns)
    assert table["Bank (UTC)"].tolist() == ["bank unknown"] and table["Gold"].tolist() == [1.2345]
    if drop_folder:
        latest = next(t.value for t in at.dataframe if "Latest drop" in t.value.columns)
        assert latest["Fully imported"].iloc[0]
    else:
        assert any(m.value.startswith("Imported character records") for m in at.success) and not at.warning


@pytest.mark.parametrize("drop_folder", [False, True])
def test_journal_only_import_page_counts_latest_duplicates_and_reload_guidance(tmp_path, monkeypatch, drop_folder):
    from test_journal import entry, write
    from test_scans import finished_now
    at, addon = preview_addon(tmp_path, monkeypatch)
    r = entry()
    r.update(captured_at=finished_now())
    r.pop("captured_at_utc")
    path = addon["scan_path"]
    if drop_folder:
        folder = tmp_path / "journal-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        path = folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua"
    write(path, [r])
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not at.exception and not at.error
    table = next(t.value for t in at.dataframe if "Family" in t.value.columns)
    assert table["new"].tolist() == [1] and table["Character"].tolist() == ["Alice"]
    # Local database writes can exceed AppTest's three-second default under coverage.
    next(b for b in at.button if b.label == "Import addon scan").click().run(timeout=30)
    assert not at.exception and not at.error
    saved = next(t.value for t in at.dataframe if "Entries" in t.value.columns)
    assert saved["Entries"].tolist() == [1] and saved["Latest (UTC)"].iloc[0].endswith("+00:00")
    if drop_folder:
        latest = next(t.value for t in at.dataframe if "Latest drop" in t.value.columns)
        assert latest["Fully imported"].iloc[0]
    else:
        assert any(m.value.startswith("Imported character records") for m in at.success)
        next(b for b in at.button if b.label == "Preview addon scans").click().run()
        assert any("Nothing new" in m.value and "/reload" in m.value for m in at.caption)


@pytest.mark.parametrize("drop_folder", [False, True])
def test_active_auctions_import_page_latest_and_unknown(tmp_path, monkeypatch, drop_folder):
    from test_active_auctions import owned
    from test_character_snapshots import snapshot
    from test_journal import write
    from test_scans import finished_now

    r = owned("owned", 3)
    r.update(captured_at=finished_now())
    r.pop("captured_at_utc")
    bob = snapshot(character="Bob")
    bob.update(captured_at=finished_now())
    bob.pop("captured_at_utc")
    at, addon = preview_addon(tmp_path, monkeypatch)
    path = addon["scan_path"]
    if drop_folder:
        folder = tmp_path / "auction-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        path = folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua"
    write(path, [r], [bob])
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception and not at.error
    table = next(t.value for t in at.dataframe if "Active auctions (UTC)" in t.value.columns)
    assert table["Character"].tolist() == ["Alice", "Bob"]
    assert table["Auctions"].iloc[0] == 2 and table["Marked sold"].iloc[0] == 1
    assert table["Active auctions (UTC)"].iloc[0].endswith("+00:00")
    assert table["Active auctions (UTC)"].iloc[1] == "active auctions unknown"
    assert table["Auctions"].isna().iloc[1] and table["Marked sold"].isna().iloc[1]


@pytest.mark.parametrize("drop_folder", [False, True])
def test_professions_import_page_rows_and_unknown(tmp_path, monkeypatch, drop_folder):
    from test_character_snapshots import snapshot
    from test_journal import write
    from test_professions import recipes
    from test_scans import finished_now

    r = recipes()
    r.update(captured_at=finished_now())
    r.pop("captured_at_utc")
    alice = snapshot(level=22, skills={"legacy": {"rows": [
        {"name": "Engineering", "rank": 20, "max_rank": 75}, {"name": "Mining", "rank": 55, "max_rank": 75}]}})
    bob = snapshot("bob", character="Bob")
    for s in (alice, bob):
        s.update(captured_at=finished_now())
        s.pop("captured_at_utc")
    at, addon = preview_addon(tmp_path, monkeypatch)
    path = addon["scan_path"]
    if drop_folder:
        folder = tmp_path / "profession-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        path = folder / "windows-pc-20261007T004900Z-BrownstoneScan.lua"
    write(path, [r], [alice, bob])
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.exception and not at.error
    table = next(t.value for t in at.dataframe if "Known recipes (UTC)" in t.value.columns)
    assert table["Character"].tolist() == ["Alice", "Alice", "Bob"]
    assert table["Listed recipes"].iloc[0] == 1 and table["Rank"].iloc[0] == 20
    assert table["Known recipes (UTC)"].iloc[1] == "known recipes unknown"
    assert table["Skills"].iloc[2] == "skills unknown" and table["Level"].isna().iloc[2]


def import_details(at):
    return next(e for e in at.expander if e.label == "Details")


@pytest.mark.parametrize("drop_folder", [False, True])
def test_simple_import_clean_summary_button_and_collapsed_tables(tmp_path, monkeypatch, drop_folder):
    from test_character_snapshots import snapshot, write
    from test_scans import finished_now, listing, scan, write_scans

    at, addon = preview_addon(tmp_path, monkeypatch, [scan("clean", finished_now(), [listing(1, 1, 50)])])
    if drop_folder:
        folder = tmp_path / "simple-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        old = write_scans(folder / "windows-pc-20261008T130000Z-BrownstoneScan.lua",
                          scan("old", finished_now(), [listing(2, 1, 60)]))
        from brownstone.pipeline import import_scans
        import_scans(addon, old)
        new = write_scans(folder / "windows-pc-20261009T090000Z-BrownstoneScan.lua",
                          scan("new", finished_now(), [listing(3, 1, 70)]))
    r = snapshot()
    r.update(captured_at=finished_now())
    r.pop("captured_at_utc")
    write(addon["scan_path"], [r], scans=[scan("clean", finished_now(), [listing(1, 1, 50)])])
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not at.exception and not at.warning
    assert any("local file: 1 new scan, 1 character record" in c.value for c in at.caption)
    assert not import_details(at).proto.expanded
    assert not next(e for e in at.expander if e.label == "Imported character data").proto.expanded
    assert len(import_details(at).dataframe) == len([t for t in at.sidebar.dataframe])
    assert not import_details(at).button
    assert at.multiselect[0].value == ([str(addon["scan_path"]), str(new)] if drop_folder else ["clean"])
    assert any(b.label == "Import addon scan" for b in at.button)
    if drop_folder:
        assert any(c.value == "windows-pc, dropped 09 Oct 09:00 UTC: 1 new scan, 0 character records"
                   for c in at.caption)
        assert any(c.value == "1 file already imported." for c in at.caption)
        assert any("1 dropped file is fully imported" in c.value for c in at.caption)
    else:
        assert not any("dropped file" in c.value for c in at.caption)
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert at.success and not at.error and not at.exception
    assert any("/bscan clear is safe" in c.value for c in at.caption)
    holdings = next(e for e in at.expander if e.label == "Imported character data")
    assert holdings.dataframe and not holdings.proto.expanded
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert sum(c.value.startswith("Nothing new") for c in at.caption) == 1
    assert not any(b.label == "Import addon scan" for b in at.button)
    assert not import_details(at).proto.expanded


@pytest.mark.parametrize("problem", ["read", "parse", "conflict", "partial", "house", "selection", "drop"])
def test_simple_import_problem_warning_opens_details(tmp_path, monkeypatch, problem):
    from test_scans import finished_now, listing, scan, write_scans

    record = scan("clean", finished_now(), [listing(1, 1, 50)])
    at, addon = preview_addon(tmp_path, monkeypatch, [record])
    if problem == "read":
        addon["scan_path"].unlink()
    elif problem == "parse":
        addon["scan_path"].write_text("BrownstoneScanDB = {")
    elif problem == "conflict":
        from brownstone.pipeline import import_scans
        import_scans(addon)
        record["listings"][0]["buyout"] = 51
        write_scans(addon["scan_path"], record)
    elif problem == "partial":
        write_scans(addon["scan_path"], scan("partial", finished_now(), [], status="stopped"))
    elif problem == "house":
        write_scans(addon["scan_path"], scan("horde", finished_now(), [], faction={"player": "Horde"}))
    elif problem == "drop":
        folder = tmp_path / "new-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        write_scans(folder / "windows-pc-20261008T130000Z-BrownstoneScan.lua", record)
        at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not at.exception
    if problem in ("read", "parse", "conflict"):
        # The error is shown once; with no preview there are no details to open.
        assert any("Preview failed" in e.value and (problem != "conflict" or "conflict" in e.value)
                   for e in at.error)
        assert not at.warning and not any(e.label == "Details" for e in at.expander)
        return
    if problem in ("selection", "drop"):
        at.multiselect[0].set_value([]).run()
    assert import_details(at).proto.expanded
    expected = {"partial": "New partial scan", "house": "another auction house",
                "selection": "Selection differs", "drop": "windows-pc-20261008T130000Z-BrownstoneScan.lua"}
    assert any(expected[problem] in w.value for w in at.warning)
    if problem == "drop":
        assert any("not fully imported" in w.value for w in at.warning)
        assert any(c.value == "windows-pc, dropped 08 Oct 13:00 UTC: 1 new scan, 0 character records"
                   for c in at.caption)


@pytest.mark.parametrize("drop_folder", [False, True])
def test_simple_import_stale_error_shown_once_without_writes(tmp_path, monkeypatch, drop_folder):
    from test_scans import finished_now, listing, scan
    at, addon = preview_addon(tmp_path, monkeypatch, [scan("clean", finished_now(), [listing(1, 1, 50)])])
    if drop_folder:
        folder = tmp_path / "stale-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    addon["scan_path"].write_bytes(addon["scan_path"].read_bytes() + b"\n")
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert any("stale" in e.value for e in at.error)
    assert not at.warning and not any(e.label == "Details" for e in at.expander)
    assert not addon["data_dir"].exists()
    assert not any(b.label == "Import addon scan" for b in at.button)


def test_simple_import_quiet_empty_local_and_machine_cleanup(tmp_path, monkeypatch):
    from test_scans import finished_now, listing, scan, write_scans
    at, addon = preview_addon(tmp_path, monkeypatch, [])
    folder = tmp_path / "quiet-drops"
    folder.mkdir()
    addon["drop_folder"] = folder
    drop = write_scans(folder / "windows-pc-20261008T130000Z-BrownstoneScan.lua",
                       scan("win", finished_now(), [listing(1, 1, 50)]))
    raw = drop.read_bytes()
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert any("Local scan_path file has no scans" in c.value for c in at.caption)
    assert all("preview.lua" not in w.value for w in at.warning)
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert not at.error and not at.exception
    assert any("windows-pc: /bscan clear is safe only if you haven't played" in c.value for c in at.caption)
    assert any("1 dropped file is fully imported" in c.value for c in at.caption)
    assert not import_details(at).proto.expanded
    assert drop.exists() and drop.read_bytes() == raw
    assert any("Local scan_path file has no scans" in c.value for c in at.caption)


@pytest.mark.parametrize("problem", ["read", "parse", "conflict", "character-house"])
def test_simple_drop_problems_name_file_and_preserve_good_import(tmp_path, monkeypatch, problem):
    from test_scans import finished_now, listing, scan, write_scans
    at, addon = preview_addon(tmp_path, monkeypatch, [scan("good", finished_now(), [listing(1, 1, 50)])])
    folder = tmp_path / "problem-drops"
    folder.mkdir()
    addon["drop_folder"] = folder
    bad = folder / "windows-pc-20261008T130000Z-BrownstoneScan.lua"
    record = scan("bad", finished_now(), [listing(2, 1, 60)])
    write_scans(bad, record)
    if problem == "read":
        from brownstone import pipeline
        original = pipeline._read_scan_bytes

        def unreadable(path):
            if path == bad:
                raise PermissionError("still syncing")
            return original(path)

        monkeypatch.setattr(pipeline, "_read_scan_bytes", unreadable)
    elif problem == "parse":
        bad.write_text("BrownstoneScanDB = {")
    elif problem == "conflict":
        from brownstone.pipeline import import_scans
        import_scans(addon, bad)
        record["listings"][0]["buyout"] = 61
        write_scans(bad, record)
    else:
        from test_character_snapshots import snapshot, write
        r = snapshot()
        r["faction"] = "Horde"
        r.update(captured_at=finished_now())
        r.pop("captured_at_utc")
        write(bad, [r])
    raw = bad.read_bytes()
    at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert import_details(at).proto.expanded
    expected = {"read": "still syncing", "parse": "not fully imported", "conflict": "conflict",
                "character-house": "another auction house"}
    assert any(bad.name in w.value and expected[problem] in w.value for w in at.warning)
    next(b for b in at.button if b.label == "Import addon scan").click().run()
    assert at.success and not at.error and not at.exception
    assert any("windows-pc: don't /bscan clear" in c.value for c in at.caption)
    assert bad.read_bytes() == raw
    assert import_details(at).proto.expanded


@pytest.mark.parametrize("drop_folder", [False, True])
def test_simple_import_details_stay_open_after_selection_restored(tmp_path, monkeypatch, drop_folder):
    from test_scans import finished_now, listing, scan
    at, addon = preview_addon(tmp_path, monkeypatch, [scan("clean", finished_now(), [listing(1, 1, 50)])])
    if drop_folder:
        folder = tmp_path / "sticky-drops"
        folder.mkdir()
        addon["drop_folder"] = folder
        at.run()
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    default = at.multiselect[0].value
    assert not import_details(at).proto.expanded
    at.multiselect[0].set_value([]).run()
    assert import_details(at).proto.expanded
    at.multiselect[0].set_value(default).run()
    assert not at.warning and import_details(at).proto.expanded
    next(b for b in at.button if b.label == "Preview addon scans").click().run()
    assert not import_details(at).proto.expanded
