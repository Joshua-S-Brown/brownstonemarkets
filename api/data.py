"""Explicit import review registry: exact bytes, source/config binding and one process writer."""

import secrets
import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from brownstone import import_review, pipeline, scan_inputs

from . import context

router = APIRouter()
_registry: dict[str, tuple[str, str, Any]] = {}
_registry_lock = threading.Lock()
_writer = threading.Lock()


class Data(BaseModel):
    provider: str
    chips: list[str]
    details: dict[str, str]
    cli: str | None = None


class Selection(BaseModel):
    new: bool
    default: list[str]
    choices: list[str]
    selected: list[str]
    selection_differs: bool
    can_import: bool
    has_records: bool
    lines: list[str]
    problems: list[str]
    sections: list[tuple[str, list[dict[str, Any]]]]
    notes: list[str]
    file_status: list[str]
    clear: list[str]


class Review(BaseModel):
    review_id: str | None = None
    review: Selection | None = None
    messages: list[tuple[str, str]] = []
    hits: list[str] = []
    success: bool = False


class Import(BaseModel):
    review_id: str
    selected: list[str]


class Discard(BaseModel):
    review_id: str | None = None


def addon(chosen):
    if chosen["provider"] != "addon":
        raise HTTPException(422, "Refresh this source with the CLI.")


def create_review(chosen):
    preview = scan_inputs.preview_inputs(chosen) if chosen.get("drop_folder") else pipeline.preview_scans(chosen)
    review_id = secrets.token_urlsafe(24)
    with _registry_lock:
        _registry[chosen["source_id"]] = (review_id, pipeline.preview_configuration(chosen), preview)
    shaped = import_review.selection(preview, bool(chosen.get("drop_folder")), machine=chosen.get("machine"))
    return dict(review_id=review_id, review=shaped)


@router.get("/data", response_model=Data)
def data(source: str = ""):
    chosen = context.resolve(source)
    provider = chosen["provider"]
    return dict(
        provider=provider,
        chips=import_review.status_chips(chosen) if provider == "addon" else [],
        details={
            k: str(chosen.get(k, "not configured"))
            for k in ("source_id", "market_id", "scan_path", "machine", "drop_folder")
        },
        cli=f"Refresh this source with: python -m brownstone --source {chosen['source_id']}"
        if provider != "addon"
        else None,
    )


@router.get("/data/imported", response_model=list[tuple[str, list[dict[str, Any]]]])
def imported(source: str = ""):
    return jsonable_encoder(import_review.holdings_sections(context.resolve(source)))


@router.post("/data/discard", response_model=dict[str, bool])
def discard(body: Discard, source: str = ""):
    chosen = context.resolve(source)
    with _registry_lock:
        current = _registry.get(chosen["source_id"])
        if current and (body.review_id is None or current[0] == body.review_id):
            _registry.pop(chosen["source_id"], None)
    return dict(discarded=True)


@router.post("/data/review", response_model=Review)
def review(source: str = ""):
    chosen = context.resolve(source)
    addon(chosen)
    with _registry_lock:
        _registry.pop(chosen["source_id"], None)
    try:
        return jsonable_encoder(create_review(chosen))
    except Exception as error:
        return dict(messages=import_review.preview_failure(error))


def perform_import(chosen, preview, selected):
    drops = bool(chosen.get("drop_folder"))
    try:
        if drops:
            results = scan_inputs.import_inputs(chosen, preview, selected)
            messages = import_review.file_messages(results)
            try:
                fresh = create_review(chosen)
            except Exception as error:
                # The write succeeded even if the follow-up read cannot produce a fresh review.
                messages += import_review.preview_failure(error)
                fresh = {}
        else:
            manifest = pipeline.import_scans(chosen, scan_ids=selected, reviewed=preview)
            messages, fresh = import_review.import_messages(chosen, manifest), {}
        success = any(kind == "success" for kind, _ in messages)
        # A saved partial scan also changes the source's evidence.
        success = success or any(kind == "warning" for kind, _ in messages)
        return dict(
            **fresh,
            messages=messages,
            success=success,
            hits=import_review.watchlist_hits(chosen, []) if success else [],
        )
    except pipeline.StalePreviewError as error:
        return dict(messages=import_review.import_failure(error, stale=True))
    except Exception as error:
        return dict(messages=import_review.import_failure(error, drops=drops))


def current_review(chosen, review_id):
    current = _registry.get(chosen["source_id"])
    if current is None or current[0] != review_id or current[1] != pipeline.preview_configuration(chosen):
        raise HTTPException(409, "Review out of date: check for new scans again")
    return current


@router.post("/data/selection", response_model=Selection)
def selection(body: Import, source: str = ""):
    chosen = context.resolve(source)
    addon(chosen)
    with _registry_lock:
        current = current_review(chosen, body.review_id)
        return jsonable_encoder(
            import_review.selection(current[2], bool(chosen.get("drop_folder")), body.selected, chosen.get("machine"))
        )


@router.post("/data/import", response_model=Review)
def collect(body: Import, source: str = ""):
    chosen = context.resolve(source)
    addon(chosen)
    if not _writer.acquire(blocking=False):
        raise HTTPException(409, "Another import is running")
    try:
        with _registry_lock:
            current = current_review(chosen, body.review_id)
            _registry.pop(chosen["source_id"])  # Consume before any writer or error path.
        return jsonable_encoder(perform_import(chosen, current[2], body.selected))
    finally:
        _writer.release()
