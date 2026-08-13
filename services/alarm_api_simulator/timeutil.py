"""ISO-8601 formatting for values that may be echoed back into a URL query string by a
client (as the supplied Postman chaining collection does with flood-window start/end).
`datetime.isoformat()` renders UTC as `+00:00`; the literal `+` is misread as a space
once it round-trips through `application/x-www-form-urlencoded` query decoding. `Z` has
no such character and is equally valid ISO-8601, so every UTC timestamp this service
emits uses it.
"""

from __future__ import annotations

from datetime import UTC, datetime


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
