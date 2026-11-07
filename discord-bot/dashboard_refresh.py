"""Stable signature for the image shown in each in-channel Discord dashboard.

Only the data that actually affects a panel is included. Updating the tracked
image only when its signature changes avoids a redundant Discord PATCH each
minute (and the resulting Discord rate limiting).
"""
from datetime import date
from hashlib import sha256
import json


def dashboard_fingerprint(panel, data, today=None):
    """Return the same digest until a panel's visible source data changes.

    Date changes invalidate calendar at local host midnight. Unknown panels are
    rejected rather than causing an unexpected render or API update.
    """
    if panel == "calendar":
        payload = {"today": (today or date.today()).isoformat(), "events": data["events"]}
    elif panel == "board":
        payload = {
            "users": data["users"],
            "affiliates": data["affiliates"],
            "redemptions": data["redemptions"],
        }
    elif panel == "rewards":
        payload = {"rewards": data["rewards"], "redemptions": data["redemptions"]}
    else:
        raise ValueError(f"Unsupported dashboard panel: {panel}")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()
