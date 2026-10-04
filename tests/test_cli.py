"""Command line: recipe catalogs from a saved page, TSM collection and source selection, all offline."""
import sys
import tomllib
from datetime import UTC, datetime

import pytest
from test_recipe_import import PAGE
from test_scans import scan, write_scans

from brownstone import cli

SELECTION = """game_version = "forever"
rules_version = "forever-beta-1.60"
profession = "tailoring"
status = "beta-observed"
catalog_version = "0.1"

[[recipes]]
recipe_id = 3755

[[items]]
item_id = 2320
vendor = true
"""
SHARED = 'data_dir = "data"\nmax_age_hours = 1000000\nauction_cut = 0.05\nmin_discount = 0.2\ntop_n = 20\n'
TSM = ('[[sources]]\nsource_id = "{id}"\nprovider = "tsm"\nenabled = {enabled}\n'
       'source_url = "https://example.com/items.csv"\ngame_version = "classic"\nregion = "us"\nscope = "house"\n'
       'realm = "mankrik"\nfaction = "alliance"\nallow_missing_updated_at = true\n')


def run_cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["brownstone", *map(str, args)])
    cli.main()


def recipes_args(tmp_path, page):
    selection = tmp_path / "forever-test.toml"
    selection.write_text(SELECTION, encoding="utf-8")
    return ("recipes", "--page", page, "--selection", selection, "--output", tmp_path / "catalog.toml",
            "--saved-at", "2026-10-04", "--archive-dir", tmp_path / "archive")


def test_recipes_command_writes_the_catalog_then_lists_changes(tmp_path, monkeypatch, capsys):
    page = tmp_path / "page.html"
    page.write_text(PAGE, encoding="utf-8")
    run_cli(monkeypatch, *recipes_args(tmp_path, page))
    out = capsys.readouterr().out
    assert "Wrote 2 recipes and 4 items" in out and "changes" not in out  # Nothing to compare the first time.
    catalog = tomllib.loads((tmp_path / "catalog.toml").read_text(encoding="utf-8"))
    assert {r["recipe_id"] for r in catalog["recipes"]} == {2963, 3755}  # The bolt is added as an intermediate.

    run_cli(monkeypatch, *recipes_args(tmp_path, page))
    assert "no recipe or vendor price changes" in capsys.readouterr().out

    page.write_text(PAGE.replace('"reagents":[[2589,2]]', '"reagents":[[2589,3]]'), encoding="utf-8")
    run_cli(monkeypatch, *recipes_args(tmp_path, page))
    assert "changed recipe 2963 Bolt of Linen Cloth" in capsys.readouterr().out


def test_recipes_command_reports_failures(tmp_path, monkeypatch, capsys):
    page = tmp_path / "page.html"
    page.write_text("<html>not a profession page</html>", encoding="utf-8")
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, *recipes_args(tmp_path, page))
    assert "Recipe import failed" in capsys.readouterr().err
    assert not (tmp_path / "catalog.toml").exists()


def tsm_config(tmp_path, *sources):
    config = tmp_path / "config/market.toml"
    config.parent.mkdir(exist_ok=True)
    config.write_text(SHARED + "".join(TSM.format(id=source, enabled=enabled) for source, enabled in sources),
                      encoding="utf-8")
    return config


def test_tsm_collection_uses_the_first_enabled_source_by_default(tmp_path, monkeypatch, capsys):
    config = tsm_config(tmp_path, ("off", "false"), ("on", "true"))
    items = tmp_path / "items.csv"
    items.write_text("itemId,name,marketValue,minBuyout,recent,historical,updatedAt\n1,Ore,100,50,100,100,\n",
                     encoding="utf-8")
    run_cli(monkeypatch, "--config", config, "--input", items)
    assert "Saved 1 screening candidates" in capsys.readouterr().out
    assert list((tmp_path / "data/bronze/on").glob("*.csv")) and not (tmp_path / "data/bronze/off").exists()


@pytest.mark.parametrize("args, message", [
    (["--source", "missing"], "Unknown source: missing"),
    (["--source", "on", "--scan", "x"], "--scan applies only to addon sources"),
])
def test_cli_rejects_unknown_sources_and_misplaced_scan_flags(tmp_path, monkeypatch, capsys, args, message):
    config = tsm_config(tmp_path, ("on", "true"))
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "--config", config, *args)
    assert message in capsys.readouterr().err


def test_cli_says_when_a_file_has_no_complete_scan(tmp_path, monkeypatch, capsys):
    config = tmp_path / "config/market.toml"
    config.parent.mkdir()
    write_scans(tmp_path / "scan.lua", scan("cut-short", int(datetime.now(UTC).timestamp()) - 60, [],
                                            status="stopped", reported=10))
    config.write_text(SHARED + '[[sources]]\nsource_id = "mine"\nprovider = "addon"\nscan_path = "scan.lua"\n'
                      'game_version = "forever"\nregion = "us"\nscope = "house"\nserver_type = "normal"\n'
                      'faction = "alliance"\n', encoding="utf-8")
    run_cli(monkeypatch, "--config", config, "--source", "mine")
    out = capsys.readouterr().out
    assert "Scan cut-short: stopped, 0 listings, empty" in out
    assert "No complete scan in this file; prices are unchanged" in out
