"""Read-only tail of FreeRADIUS's own log file, surfaced in the web (Logs →
Server log). This shows what the decision log cannot: packets FreeRADIUS drops
before any policy runs — unknown clients (with their real source IP), bad
shared secrets / invalid Message-Authenticator, malformed packets — plus auth
accept/reject results. So an operator never has to SSH in to see why a NAS is
not getting through.
"""
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter

from ..config import get_settings

router = APIRouter(prefix="/api/logs", tags=["logs"])
settings = get_settings()

# "Fri Sep 11 18:02:04 2026 : Error: <message>"
_LINE = re.compile(r"^(\w{3} \w{3} +\d+ [\d:]+ \d{4}) : (\w+): (.*)$")


def _iso(fr_ts: str) -> str:
    """FreeRADIUS logs the container's wall clock (UTC) as
    'Fri Sep 11 18:02:04 2026' → ISO with tz so the browser shows local time
    (same as the decision log's created_at)."""
    try:
        dt = datetime.strptime(fr_ts, "%a %b %d %H:%M:%S %Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ""


def _tail(path: str, n: int) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, 512 * 1024)  # last 512 KiB is plenty
            f.seek(size - block)
            data = f.read().decode("utf-8", "replace")
    except (FileNotFoundError, OSError):
        return []
    lines = data.splitlines()
    if block < size and lines:
        lines = lines[1:]  # drop the partial first line after the seek
    return lines[-n:]


@router.get("/radius")
async def radius_log(lines: int = 300, q: str = ""):
    """Tail the FreeRADIUS log. `q` filters (case-insensitive substring)."""
    n = max(1, min(lines, 2000))
    ql = q.lower()
    out = []
    for ln in _tail(settings.radius_log_path, n):
        if ql and ql not in ln.lower():
            continue
        m = _LINE.match(ln)
        if m:
            out.append({"ts": _iso(m.group(1)), "level": m.group(2), "text": m.group(3)})
        else:
            out.append({"ts": "", "level": "", "text": ln})
    return {"path": settings.radius_log_path, "lines": out}
