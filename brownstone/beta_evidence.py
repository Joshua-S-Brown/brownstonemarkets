"""Pure beta evidence checks. Raw payloads stay private; output uses explicit projections."""
from collections import Counter, defaultdict
from datetime import UTC, datetime

from . import addon_records, character_snapshots, journal, pipeline, professions, scans

BETA_START = datetime(2026, 9, 17, tzinfo=UTC)  # requirements.md → Product direction
# Alternatives within a row describe the two client API paths, not mandatory simultaneous support.
COVERAGE = (
    ("snapshots", "logout/reload bags", ("PLAYER_LOGOUT",)),
    ("snapshots", "bank open", ("BANKFRAME_OPENED",)),
    ("snapshots", "bank close", ("BANKFRAME_CLOSED",)),
    ("journal", "money", ("PLAYER_MONEY",)),
    ("journal", "bags", ("BAG_UPDATE_DELAYED",)),
    ("journal", "mail/invoices", ("MAIL_SHOW", "MAIL_INBOX_UPDATE")),
    ("journal", "take mail", ("TakeInboxMoney", "TakeInboxItem", "AutoLootMailItem")),
    ("journal", "send mail", ("SendMail", "MAIL_SEND_SUCCESS")),
    ("journal", "post", ("StartAuction", "PostAuction", "C_AuctionHouse.PostItem",
                          "C_AuctionHouse.PostCommodity", "AUCTION_HOUSE_AUCTION_CREATED")),
    ("journal", "buy auction", ("PlaceAuctionBid", "C_AuctionHouse.PlaceBid",
                                 "C_AuctionHouse.ConfirmCommoditiesPurchase", "AUCTION_HOUSE_PURCHASE_COMPLETED")),
    ("journal", "cancel", ("CancelAuction", "C_AuctionHouse.CancelAuction", "AUCTION_HOUSE_AUCTION_CANCELED")),
    ("journal", "vendor buy", ("BuyMerchantItem",)),
    ("journal", "vendor sell", ("SellCursorItem", "UseContainerItem", "C_Container.UseContainerItem")),
    ("journal", "repair", ("RepairAllItems",)),
    ("journal", "craft", ("DoTradeSkill", "DoCraft", "C_TradeSkillUI.CraftRecipe", "UNIT_SPELLCAST_SUCCEEDED")),
    ("journal", "loot/gathering", ("CHAT_MSG_LOOT", "LOOT_OPENED", "LOOT_SLOT_CLEARED")),
    ("active auctions", "owned list", ("OWNED_AUCTIONS_UPDATED", "AUCTION_OWNED_LIST_UPDATE")),
    ("professions", "recipe window", ("TRADE_SKILL_SHOW", "CRAFT_SHOW")),
    ("professions", "recipe changes", ("TRADE_SKILL_UPDATE", "CRAFT_UPDATE")),
)


def check(report: dict, name: str, status: str, detail, ids=()) -> None:
    report["checks"].append(dict(check=name, status=status, detail=detail, entry_ids=list(ids)))


def serialized_size(value) -> int:
    """Approximate serialized bytes: compact typed JSON, not byte offsets in the Lua source."""
    import json
    return len(json.dumps(journal._typed(value), ensure_ascii=False, separators=(",", ":")).encode())


def identity(record: dict) -> tuple:
    return tuple(record.get(k) for k in ("character", "realm", "faction"))


def identifier(record: dict) -> str:
    return str(record.get("scan_id", record.get("entry_id", record.get("snapshot_id", "missing ID"))))


def validate(report: dict, lists: tuple, now: datetime) -> tuple[list[dict], list[dict]]:
    valid_scans: list[dict] = []
    valid_records: list[dict] = []
    for kind, values in zip(("scan", "snapshot", "journal"), lists, strict=True):
        seen: dict[str, str] = {}
        sequences = []
        for index, record in enumerate(values):
            label = identifier(record) if isinstance(record, dict) else f"{kind}[{index + 1}]"
            try:
                _validate_one(record, kind, now)
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
                check(report, "import validation", "fail", f"{kind} {label}: {error}", [label])
                continue
            check(report, "import validation", "pass", kind, [label])
            digest = scans.scan_content_hash(record) if kind == "scan" else addon_records.content_hash(record)
            if label in seen:
                detail = "same ID with different content" if seen[label] != digest else "Duplicate ID in file"
                check(report, "unique IDs", "fail", detail, [label])
            seen[label] = digest
            sequences.append(record.get("sequence"))
            (valid_scans if kind == "scan" else valid_records).append(record)
            _times(report, record, kind, now)
        if kind != "scan":
            increasing = all(type(s) is int for s in sequences) and all(
                b > a for a, b in zip(sequences, sequences[1:], strict=False))
            check(report, "sequence", "pass" if increasing else "fail",
                  f"{kind}: sequence must be present and strictly increasing in its file array",
                  [identifier(r) for r in values if isinstance(r, dict)])
    sequence_records = [r for r in valid_records if type(r.get("sequence")) is int]
    sequences = [r["sequence"] for r in sequence_records]
    check(report, "shared sequence", "pass" if len(set(sequences)) == len(sequences) else "fail",
          "Snapshots and journal share one account sequence", [identifier(r) for r in sequence_records])
    return valid_scans, valid_records


def _validate_one(record: dict, kind: str, now: datetime) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"{kind} must be a table")
    if kind == "scan":
        pipeline._validate_scans([record], now)
    elif kind == "snapshot":
        character_snapshots.summarize(record, now)
    else:
        journal.summarize(record, now)


def _times(report: dict, r: dict, kind: str, now: datetime) -> None:
    fields = ("started_at", "finished_at") if kind == "scan" else ("captured_at",)
    for field in fields:
        moment = scans._utc(r.get(field), r.get(field + "_utc"), field)
        plausible = BETA_START <= moment <= now
        check(report, "time", "pass" if plausible else "fail", {field: moment.isoformat()}, [identifier(r)])


def load_sessions(records: list[dict]) -> list[list[dict]]:
    """Infer loads from shared sequence, logout, identity/login changes and decreasing uptime.

    GetTime can persist across reload; it is not itself a load ID. Files omit explicit load IDs.
    """
    sessions: list[list[dict]] = []
    previous: dict = {}
    for r in sorted(records, key=lambda r: (r.get("sequence", 0), r["captured_at"])):
        changed = identity(r) != identity(previous) or r.get("login_at") != previous.get("login_at")
        reset = r.get("session_time", float("inf")) < previous.get("session_time", 0)
        if not sessions or changed or reset or previous.get("event") == "PLAYER_LOGOUT":
            sessions.append([])
        sessions[-1].append(r)
        previous = r
    return sessions


def session_checks(report: dict, sessions: list[list[dict]], database: dict) -> None:
    diagnostics = database.get("journal_diagnostics")
    readable = isinstance(diagnostics, dict) and all(k in diagnostics for k in (
        "rejected_events", "missing_hooks", "installed_hooks", "fired_events"))
    check(report, "diagnostics", "pass" if readable else "warn",
          "Only latest load diagnostics are saved; earlier loads are unavailable" if diagnostics is not None
          else "Missing journal_diagnostics (expected before format 6)")
    if diagnostics is not None and not readable:
        check(report, "diagnostic fields", "warn", "Missing or malformed diagnostic fields")
    report["load_sessions"] = []
    report["journal_errors_scope"] = "Persistent account-wide counters; load attribution is unavailable"
    if not sessions and isinstance(diagnostics, dict):
        sessions = [[]]  # Latest diagnostic evidence exists even when the load retained no records.
    for number, records in enumerate(sessions, 1):
        entries = [r for r in records if "entry_id" in r]
        latest = number == len(sessions)
        report["load_sessions"].append(dict(
            load=number, inferred=True, entry_ids=[identifier(r) for r in records],
            character_identity=list(identity(records[0])) if records else None,
            journal_entries=len(entries), approximate_journal_bytes=sum(map(serialized_size, entries)),
            diagnostics=diagnostics if latest else None,
            journal_errors=database.get("journal_errors") if latest else None))
        if not latest:
            check(report, "load diagnostics", "warn", f"Load {number}: historical diagnostics not retained",
                  [identifier(r) for r in records])
        _money_chain(report, entries)
        _session_recipes(report, entries, number)
    errors = database.get("journal_errors") or {}
    if errors:
        check(report, "journal errors", "warn", errors)
    for r in records_flat(sessions):
        if r.get("event") == "JOURNAL_OVERFLOW" or r.get("skipped", 0):
            check(report, "overflow", "fail", {"skipped": r.get("skipped")}, [identifier(r)])


def _session_recipes(report: dict, entries: list[dict], number: int) -> None:
    names: dict[str, list[str]] = defaultdict(list)
    for r in entries:
        if "known_recipes" in r:
            names[str(r["known_recipes"].get("name"))].append(identifier(r))
    for name, ids in names.items():
        check(report, "profession frequency", "warn" if len(ids) > 5 else "pass",
              {"profession": name, "lists": len(ids), "load": number}, ids)


def records_flat(sessions: list[list[dict]]) -> list[dict]:
    return [r for session in sessions for r in session]


def _money_chain(report: dict, entries: list[dict]) -> None:
    previous = None
    for r in entries:
        if r.get("family") != "money":
            continue
        before, after = r.get("before_copper"), r.get("after_copper")
        known = before is not None and after is not None
        if previous is not None and known:
            residual = before - previous["after_copper"]
            check(report, "money chain", "fail" if residual else "pass",
                  {"residual_copper": residual}, [identifier(previous), identifier(r)])
        elif not known:
            check(report, "money chain", "warn", "Missing baseline; chain unknown", [identifier(r)])
        previous = r if known else None


def reconciliation(report: dict, records: list[dict]) -> None:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[identity(r)].append(r)
    for values in groups.values():
        ordered = sorted(values, key=lambda r: (r["captured_at"], r.get("sequence", 0)))
        bags = [r for r in ordered if r.get("kind") == "bags"]
        for before, after in zip(bags, bags[1:], strict=False):
            interval = [r for r in ordered if _order(before) < _order(r) <= _order(after) and "entry_id" in r]
            _gold_residual(report, before, after, interval)
            _bag_residual(report, before, after, interval)


def _order(r: dict) -> tuple:
    return r["captured_at"], r.get("sequence", 0)


def _gold_residual(report: dict, before: dict, after: dict, interval: list[dict]) -> None:
    money = [r for r in interval if r.get("family") == "money"]
    amounts = [r.get(k) for r in money for k in ("before_copper", "after_copper")]
    gold = [r.get("gold_copper") for r in (before, after)]
    ids = [identifier(before), identifier(after), *map(identifier, money)]
    if None in gold or None in amounts:
        check(report, "snapshot gold", "warn", "Missing gold/baseline; residual unknown", ids)
        return
    residual = after["gold_copper"] - before["gold_copper"] - sum(
        r["after_copper"] - r["before_copper"] for r in money)
    check(report, "snapshot gold", "warn" if residual else "pass", {"residual_copper": residual}, ids)


def _inventory(r: dict) -> Counter | None:
    slots = scans._list(r.get("slots"), "slots")
    if not character_snapshots._complete(r) or any(s.get("item_id") is None or s.get("count") is None for s in slots):
        return None
    result: Counter = Counter()
    for slot in slots:
        result[slot["item_id"]] += slot["count"]
    return result


def _bag_residual(report: dict, before: dict, after: dict, interval: list[dict]) -> None:
    first, last = _inventory(before), _inventory(after)
    changes = [r for r in interval if r.get("family") == "bags"]
    ids = [identifier(before), identifier(after), *map(identifier, changes)]
    if first is None or last is None or any(r.get("baseline_missing") or "item_changes" not in r for r in changes):
        check(report, "bag residual", "warn", "Incomplete bags/baseline; residual unknown", ids)
        return
    delta: Counter = Counter()
    for r in changes:
        delta.update(r.get("item_changes", {}))
    residual = {item: last[item] - first[item] - delta[item] for item in first.keys() | last.keys() | delta.keys()
                if last[item] - first[item] - delta[item]}
    check(report, "bag residual", "warn" if residual else "pass", {"residual_units": residual}, ids)


def profession_checks(report: dict, records: list[dict]) -> None:
    for r in records:
        if r.get("kind") == "bags":
            _skill_check(report, r)
        if "known_recipes" not in r:
            continue
        state = r["known_recipes"]
        name = state.get("name")
        valid = isinstance(name, str) and bool(name.strip()) and name.strip().upper() != "UNKNOWN"
        check(report, "profession name", "pass" if valid else "fail", {"profession": name}, [identifier(r)])
        causes = recipe_causes(state)
        check(report, "recipe list", "warn" if state.get("possibly_incomplete") or causes else "pass",
              {"profession": name, "listed_recipes": professions._recipe_count(state),
               "possibly_incomplete": state.get("possibly_incomplete"), "causes": causes}, [identifier(r)])


def _skill_check(report: dict, r: dict) -> None:
    version = tuple(int(part) for part in r["addon_version"].split(".") if part.isdigit())
    surfaces = r.get("skills") or {}
    missing = r.get("level") is None or not surfaces
    check(report, "bags level/skills", "warn" if version >= (0, 8, 0) and missing else "pass",
          {"level": r.get("level"), "skill_surfaces": sorted(surfaces), "missing": missing}, [identifier(r)])


def recipe_causes(state: dict) -> list[str]:
    rows = scans._list(state.get("rows"), "recipe rows")
    causes = []
    if professions._first(state.get("counts")) is None or professions._first(state.get("counts")) != len(rows):
        causes.append("missing/unreadable count or row count mismatch")
    if any(r.get("type") is None for r in rows):
        causes.append("missing row type")
    if any(r.get("type") == "header" and r.get("expanded") not in (True, 1) for r in rows):
        causes.append("collapsed/unknown header")
    if _filtered(state.get("filters") or {}):
        causes.append("filter")
    if state.get("possibly_incomplete") and not causes:
        causes.append("client marked incomplete; cause not readable")
    return causes


def _filtered(filters: dict) -> bool:
    for key, value in filters.items():
        if key in ("SubClass", "InvSlot") and isinstance(value, dict):
            if value.get("all") in (False, 0):
                return True
            if value.get("all") not in (True, 1) and any(
                    isinstance(v, dict) and v.get("enabled") in (False, 0) for v in value.values()):
                return True
        elif key == "ItemLevelFilter" and isinstance(value, dict):
            if any(type(v) in (int, float) and v > 0 for k, v in value.items() if k != "n"):
                return True
        elif key in ("OnlyShowMakeable", "OnlyShowSkillUps", "ItemNameFilter") and value:
            return True
    return False


def coverage(report: dict, records: list[dict], database: dict) -> None:
    observed = {r["event"] for r in records}
    diagnostics = database.get("journal_diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    fired = scans._dict(diagnostics.get("fired_events"))
    observed.update(k for k, v in fired.items() if v)
    installed = scans._dict(diagnostics.get("installed_hooks"))
    report["coverage"] = []
    for story, action, expected in COVERAGE:
        seen = sorted(set(expected) & observed)
        row = dict(checklist=story, action=action, expected=list(expected), seen=seen,
                   unseen=sorted(set(expected) - observed), installed=sorted(set(expected) & set(installed)))
        report["coverage"].append(row)
        check(report, "coverage", "pass" if seen else "warn", row)
