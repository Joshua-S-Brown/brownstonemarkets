"""Single freshness policy for ingestion, the Action Board and the interface."""
from datetime import datetime

FUTURE_TOLERANCE_HOURS = 0.25


def is_stale(age_hours: float, max_age_hours: float) -> bool:
    """Too old, or dated further in the future than clock skew explains."""
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be positive")
    return age_hours > max_age_hours or age_hours < -FUTURE_TOLERANCE_HOURS


def observed_at(snapshot: dict) -> datetime:
    """When a manifest's prices were observed: upstream scan time when known, else collection time."""
    return datetime.fromisoformat(snapshot.get("updated_at") or snapshot["collected_at"])


def assess(snapshot: dict, now: datetime, max_age_hours: float) -> dict:
    """Age a snapshot manifest by upstream scan time, else by labeled collection time.

    Collection age says when we downloaded the file, not when prices were observed.
    """
    upstream = snapshot.get("updated_at")
    observed = observed_at(snapshot)
    age = (now - observed).total_seconds() / 3600
    return {"age_hours": age, "stale": is_stale(age, max_age_hours),
            "basis": "upstream scan" if upstream else "collection",
            "upstream_known": bool(upstream), "observed_at": observed}
