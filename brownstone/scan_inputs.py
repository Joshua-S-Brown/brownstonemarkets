"""Read-only multi-file preview and explicit per-file collections (OPS-03)."""
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .config import Source
from .drop_files import ignored_reason, parse_drop_name
from .pipeline import ScanPreview, StalePreviewError, import_scans, preview_configuration, preview_scans


@dataclass
class InputFile:
    path: Path
    machine: str | None
    drop_time: datetime | None = None
    preview: ScanPreview | None = None
    error: str = ""
    ignored: str = ""

    @property
    def fully_imported(self) -> bool:
        return bool(self.preview and (self.preview.known or self.preview.snapshot_known)
                    and all(self.preview.known + self.preview.snapshot_known)
                    and not any(self.preview.mismatches + self.preview.snapshot_mismatches))

    @property
    def matching_snapshots(self) -> bool:
        return bool(self.preview and any(not m for m in self.preview.snapshot_mismatches))

    @property
    def matching_ids(self) -> list[str]:
        if self.preview is None:
            return []
        return [s["scan_id"] for s, mismatch in zip(self.preview.summaries, self.preview.mismatches, strict=True)
                if not mismatch]


@dataclass
class InputPreview:
    configuration: str
    files: list[InputFile] = field(default_factory=list)

    @property
    def new_files(self) -> list[str]:
        # UI selections name files: scan IDs are shared across files and cannot identify a file.
        return [str(f.path) for f in self.files if f.preview and (f.preview.new_ids or f.preview.new_snapshot_ids)]

    def latest(self) -> list[InputFile]:
        machines: dict[str, InputFile] = {}
        for file in self.files:
            if file.drop_time and file.machine:
                previous = machines.get(file.machine)
                if previous is None or (file.drop_time, file.path.name) > (previous.drop_time, previous.path.name):
                    machines[file.machine] = file
        return [machines[key] for key in sorted(machines)]


def file_source(config: Source, file: InputFile) -> Source:
    """Override provenance from the filename only; retain the complete source/market scope."""
    result = config.copy()
    if file.machine is not None:
        result["machine"] = file.machine
    return result


def input_source(config: Source, path: Path) -> Source:
    """An explicit --input keeps the machine its drop name carries; other names use the configured machine."""
    parsed = parse_drop_name(path.name)
    return file_source(config, InputFile(path, parsed[0] if parsed else config.get("machine")))


def _inventory(config: Source) -> list[InputFile]:
    files = [InputFile(Path(config["scan_path"]), config.get("machine"))]
    folder = Path(config["drop_folder"])
    try:
        entries = sorted(folder.iterdir())
    except OSError as error:
        files.append(InputFile(folder, None, error=f"Drop folder unreadable: {error}"))
        return files
    for path in entries:
        parsed = parse_drop_name(path.name)
        if parsed:
            files.append(InputFile(path, *parsed))
        else:
            files.append(InputFile(path, None, ignored=ignored_reason(path.name)))
    return files


def preview_inputs(config: Source, now: datetime | None = None) -> InputPreview:
    """List every local/drop input, isolating read, parse and content-conflict errors."""
    result = InputPreview(preview_configuration(config), _inventory(config))
    for file in result.files:
        if file.error or file.ignored:
            continue
        try:
            file.preview = preview_scans(file_source(config, file), file.path, now)
        except (OSError, ValueError, RuntimeError) as error:
            file.error = str(error)
    return result


def _review_equal(before: InputPreview, current: InputPreview) -> bool:
    def states(preview: InputPreview) -> list:
        return [(f.path, f.machine, f.drop_time, f.error, f.ignored,
                 (f.preview.configuration, f.preview.raw, f.preview.known, f.preview.snapshot_known)
                 if f.preview else None)
                for f in preview.files]
    return before.configuration == current.configuration and states(before) == states(current)


def import_inputs(config: Source, reviewed: InputPreview, selected: list[str] | None = None,
                  now: datetime | None = None, scan_ids: list[str] | None = None) -> list[dict]:
    """Invalidate changed reviews before writes, then import independent files in inventory order.

    Identical records in later files deduplicate after earlier files commit. Errors remain per file.
    A successful collection includes duplicates so every matching file can be archived explicitly.
    """
    now = now or datetime.now(UTC)
    current = preview_inputs(config, now)
    if not _review_equal(reviewed, current):
        raise StalePreviewError("Preview is stale: inputs, configuration or imported scans changed. Preview again")
    wanted = set(selected) if selected is not None else _default_selection(current, scan_ids)
    _validate_selection(current, wanted, scan_ids)
    results = []
    committed: dict[str, dict] = {}
    snapshot_committed: dict[str, dict] = {}
    for file in current.files:
        if str(file.path) in wanted:
            result = _import_file(config, file, now, scan_ids, committed, snapshot_committed)
            results.append(result)
            committed.update(_committed_scans(file, result))
            snapshot_committed.update({r["snapshot_id"]: {"snapshot_sha256": r["snapshot_sha256"]}
                                       for r in result.get("manifest", {}).get("snapshots", [])
                                       if r["outcome"] != "other_house"})
    return results


def _default_selection(preview: InputPreview, scan_ids: list[str] | None) -> set[str]:
    """Default runs archive files with new records (or requested scans), never re-archive the rest."""
    if scan_ids is None:
        return set(preview.new_files)
    return {str(f.path) for f in preview.files if set(f.matching_ids) & set(scan_ids)}


def _validate_selection(preview: InputPreview, wanted: set[str], scan_ids: list[str] | None) -> None:
    if not wanted <= {str(f.path) for f in preview.files if f.matching_ids or f.matching_snapshots}:
        raise ValueError("Select only readable matching files from this preview")
    available = {sid for f in preview.files if str(f.path) in wanted for sid in f.matching_ids}
    if scan_ids is not None and not set(scan_ids) <= available:
        raise ValueError(f"Unknown scan IDs for selected matching files: {sorted(set(scan_ids) - available)}")


def _committed_scans(file: InputFile, result: dict) -> dict[str, dict]:
    if file.preview is None or "manifest" not in result:
        return {}
    hashes = {s["scan_id"]: s["scan_sha256"] for s in file.preview.summaries}
    return {s["scan_id"]: {"snapshot_id": s["snapshot_id"], "scan_sha256": hashes[s["scan_id"]],
                           "priced": s["priced"], "item_count": s["items"]}
            for s in result["manifest"]["scans"]}


def _import_file(config: Source, file: InputFile, now: datetime, scan_ids: list[str] | None,
                 committed: dict[str, dict], snapshot_committed: dict[str, dict]) -> dict:
    source = file_source(config, file)
    try:
        refreshed = preview_scans(source, file.path, now)
        if file.preview is None or refreshed.raw != file.preview.raw:
            raise StalePreviewError("File changed. Preview again")
        expected = [committed.get(s["scan_id"], known)
                    for s, known in zip(file.preview.summaries, file.preview.known, strict=True)]
        if refreshed.known != expected:
            raise StalePreviewError("Imported scans changed. Preview again")
        expected_snapshots = [snapshot_committed.get(r["snapshot_id"], known)
                              for r, known in zip(file.preview.snapshots, file.preview.snapshot_known, strict=True)]
        if refreshed.snapshot_known != expected_snapshots:
            raise StalePreviewError("Imported snapshots changed. Preview again")
        ids = file.matching_ids
        if scan_ids is not None:
            ids = [sid for sid in ids if sid in scan_ids]
        if not ids and not file.matching_snapshots:
            return {"file": str(file.path), "machine": file.machine, "status": "skipped"}
        manifest = import_scans(source, file.path, ids, now, reviewed=refreshed, include_duplicates=True)
        return {"file": str(file.path), "machine": file.machine, "status": "imported", "manifest": manifest}
    except (OSError, ValueError, RuntimeError) as error:
        return {"file": str(file.path), "machine": file.machine, "status": "error", "error": str(error)}


def file_rows(preview: InputPreview) -> list[dict]:
    """Common CLI/page file status, including ignored entries and conservative cleanup evidence."""
    return [{"File": str(f.path), "Machine": f.machine, "Drop (UTC)": str(f.drop_time or ""),
             "Status": f.ignored or f.error or "Readable", "Fully imported": f.fully_imported}
            for f in preview.files]


def latest_rows(preview: InputPreview) -> list[dict]:
    return [{"Machine": f.machine, "Latest drop": f.path.name, "Fully imported": f.fully_imported}
            for f in preview.latest()]


CLEAR_REMINDER = ("Delete dropped files by hand only when Fully imported is true. /bscan clear on that machine "
                  "is safe only if its latest drop is fully imported and you haven't played there since that drop.")
