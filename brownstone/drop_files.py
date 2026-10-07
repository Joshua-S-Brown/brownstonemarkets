"""Shared Windows/Python drop-name contract; no file-content inference."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

CONTRACT_PATH = Path(__file__).with_name("drop_contract.json")
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def validate_machine(value: object) -> str:
    """Machine labels contain only lowercase ASCII letters, digits and hyphens."""
    if not isinstance(value, str) or not re.fullmatch(CONTRACT["machine_pattern"], value):
        raise ValueError("machine must contain only lowercase letters, digits or hyphens")
    return value


def parse_drop_name(name: str) -> tuple[str, datetime] | None:
    """Return configured provenance encoded in a final filename, or reject it."""
    match = re.fullmatch(CONTRACT["file_pattern"], name)
    if not match:
        return None
    try:
        time = datetime.strptime(match[2], CONTRACT["python_time_format"]).replace(tzinfo=UTC)
    except ValueError:
        return None
    return match[1], time


def ignored_reason(name: str) -> str:
    """Explain common non-final files without opening them."""
    if name.endswith((".partial", ".tmp")):
        return "Partial copy (not a final drop)"
    if "(" in name or "conflict" in name.lower():
        return "Conflict copy (not a final drop)"
    return "Does not match final drop naming pattern or valid UTC time"
