"""Pure Ledger display projections; filtering never changes the cached evidence."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from . import item_ledger, ledger, stock
from .action_board import compatible_catalogs
from .watchlist import catalog_names


def day_bounds(days, now):
    end = datetime.combine(now.astimezone(UTC).date() + timedelta(days=1), datetime.min.time(), UTC)
    return (None if days == "all" else int((end - timedelta(days=int(days))).timestamp()), int(end.timestamp()))


def in_range(at, bounds):
    start, end = bounds
    return (start is None or at >= start) and at < end


def capture_state(capture):
    return dict(
        empty=capture["units"] == 0,
        partial=bool(capture.get("partial")),
        unknown=capture["age_hours"] is None,
        excluded=capture["excluded"],
    )


def restock_row(row):
    entry = row["entry"]
    return row | dict(
        target_units=entry.target_units if entry else None,
        fill_state="insufficient listings" if row.get("unlisted_units") else "priced",
        limit_kind=limit_kind(entry),
        variant_id=row["key"][1],
        whole_stack_units=row.get("purchased_units"),
        above_limit_cost_copper=row.get("wait_cost_copper"),
    )


def limit_kind(entry):
    if entry is None:
        return "none"
    return "percent" if entry.buy_percent is not None else "copper" if entry.buy_copper is not None else "none"


def selected(item, stock_data, query, chains):
    query = query.strip().casefold()
    return (not chains or item in stock_data.get("chain_ids", set())) and (
        not query or query in str(item) or query in stock_data.get("names", {}).get(item, "").casefold()
    )


def gold_answer(data, bounds):
    movements = [m for m in data["movements"] if in_range(m["at"], bounds)]
    totals = ledger.summarize(movements)
    categories, daily = (
        defaultdict(lambda: dict(in_copper=0, out_copper=0)),
        defaultdict(lambda: dict(in_copper=0, out_copper=0)),
    )
    for row in totals:
        for key in ("in_copper", "out_copper"):
            categories[row["category"]][key] += row[key]
            daily[row["day"]][key] += row[key]
    team = {key: sum(r[key] for r in totals) for key in ("in_copper", "out_copper")}
    pairs = [r for r in data["reconciliation"] if in_range(r["to"], bounds)]
    return dict(
        team=team | dict(net_copper=team["in_copper"] - team["out_copper"]),
        totals=totals,
        categories=[dict(category=k, **v) for k, v in sorted(categories.items())],
        daily=[dict(day=k, **v) for k, v in sorted(daily.items())],
        reconciliation=[r | dict(from_utc=utc(r["from"]), to_utc=utc(r["to"])) for r in pairs],
        pairs=dict(
            total=len(pairs),
            reconciled=sum(r["unexplained_copper"] == 0 for r in pairs),
            unknown=sum(r["unexplained_copper"] is None for r in pairs),
        ),
        movement_count=len(movements),
        evidence={k: v for k, v in data.items() if k not in ("movements", "totals", "team", "reconciliation")}
        | dict(
            match_seconds=ledger.MATCH_SECONDS,
            coin_match_seconds=5,
            snapshots=[dict(before_id=r.get("before_id"), after_id=r.get("after_id")) for r in pairs],
        ),
    )


def items_answer(data, stock_data, bounds, query="", chains=False):
    def choose(item):
        return selected(item, stock_data, query, chains)

    movements = [m for m in data["movements"] if in_range(m["at"], bounds) and choose(m["item_id"])]
    pairs = [r for r in data["reconciliation"] if in_range(r["to"], bounds)]
    if query.strip() or chains:
        pairs = [
            r
            for r in pairs
            if any(choose(i["item_id"]) and (i["actual_units"] or i["recorded_units"]) for i in r["items"])
        ]

    reconciliation = [
        dict(
            character=r["character"],
            kind=r["kind"],
            **i,
            possibly_incomplete=r["possibly_incomplete"],
            from_utc=utc(r["from"]),
            to_utc=utc(r["to"]),
            before_id=r["before_id"],
            after_id=r["after_id"],
            **{"from": r["from"], "to": r["to"]},
        )
        for r in pairs
        for i in r["items"]
        if choose(i["item_id"]) and (i["actual_units"] or i["recorded_units"])
    ]
    return dict(
        team=item_ledger.team(movements),
        totals=item_ledger.summarize(movements),
        movement_count=len(movements),
        transfers=[
            t
            for t in data["transfers"]
            if choose(t["item_id"]) and any(t[k] and in_range(t[k]["at"], bounds) for k in ("sent", "received"))
        ],
        pairs=[
            dict(
                kind=kind,
                total=len(rows),
                reconciled=sum(not any(i["residual_units"] for i in r["items"] if choose(i["item_id"])) for r in rows),
            )
            for kind in ("bags", "bank")
            if (rows := [r for r in pairs if r["kind"] == kind])
        ],
        reconciliation=sorted(reconciliation, key=lambda r: not r["residual_units"]),
        evidence={
            k: v for k, v in data.items() if k not in ("movements", "totals", "team", "reconciliation", "transfers")
        }
        | dict(
            match_seconds=item_ledger.MATCH_SECONDS,
            baseline_count=len(data["baselines"]),
            snapshots=[dict(before_id=r.get("before_id"), after_id=r.get("after_id")) for r in pairs],
        ),
    )


def stock_answer(data, query="", chains=False):
    rows = stock.filter_rows(data, query, chains)
    keys = {r["key"] for r in rows}
    return dict(
        rows=[restock_row(r) for r in rows],
        entries=data["entries"],
        names=data["names"],
        captures=[c | capture_state(c) for c in data["captures"]],
        holdings=[h for h in data["holdings"] if h["key"] in keys],
        items_held=sum(r["held"] > 0 for r in rows),
        value_copper=sum(r["value_copper"] or 0 for r in rows),
        excluded_prices=sum(r["held"] > 0 and r["unit_copper"] is None for r in rows),
        items_short=sum(bool(r.get("short")) for r in rows),
        buy_cost_copper=sum(r.get("buy_cost_copper", 0) for r in rows),
        evidence=dict(snapshot=data["snapshot"], freshness=data["freshness"]),
        scan_state="No complete scan · import in Data"
        if not data["freshness"]
        else "Stale"
        if data["freshness"]["stale"]
        else "Fresh scan",
    )


def filter_basis(loaded):
    """Stock's names and chains, or the catalogs' when Stock failed, so Items filtering still works."""
    return loaded.get("stock") or loaded.get("catalog_filter") or {}


def page(loaded, days, now, query="", chains=False):
    bounds = day_bounds(days, now)
    stock_data = loaded.get("stock") or {}
    basis = filter_basis(loaded)
    return dict(
        gold=gold_answer(loaded["gold"], bounds) if loaded.get("gold") else None,
        items=items_answer(loaded["items"], basis, bounds, query, chains) if loaded.get("items") else None,
        stock=stock_answer(stock_data, query, chains) if stock_data else None,
        names=basis.get("names", {}),
        errors=loaded["errors"],
        evidence=loaded.get("evidence", {}),
    )


def movements(data, kind, character, day, category, stock_data=None, query="", chains=False):
    version = "ledger_version" if kind == "gold" else "item_ledger_version"
    return [
        m
        | {
            version: data[version],
            "utc": utc(m["at"]),
            "name": (stock_data or {}).get("names", {}).get(m.get("item_id")),
        }
        for m in data["movements"]
        if tuple(m["character"]) == character
        and datetime.fromtimestamp(m["at"], UTC).date().isoformat() == day
        and any(p["category"] == category for p in m["parts"])
        and (kind == "gold" or selected(m["item_id"], stock_data or {}, query, chains))
    ]


def load(config, catalogs, now):
    result = dict(errors={}, evidence=dict(source_id=config["source_id"], market_id=config["market_id"]))
    compatible = compatible_catalogs(catalogs, config)
    result["catalog_filter"] = dict(
        chain_ids={i for c in compatible for i in c["items_by_id"]}, names=catalog_names(catalogs, config)
    )
    for key, reader, note in (
        ("gold", lambda: ledger.load(config), "gold evidence: {}. Check saved journal evidence in Data, then reload."),
        (
            "items",
            lambda: item_ledger.load(config),
            "item evidence: {}. Check saved journal evidence in Data, then reload.",
        ),
        (
            "stock",
            lambda: stock.load_stock(config, catalogs, now),
            "Stock evidence: {}. Check saved evidence in Data and the local targets file, then reload.",
        ),
    ):
        try:
            result[key] = reader()
        except Exception as error:
            result["errors"][key] = "Unable to read " + note.format(error)
    return result


def utc(at):
    return datetime.fromtimestamp(at, UTC).isoformat()
