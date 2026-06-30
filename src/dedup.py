"""URL-hash deduplication with a 3-day sliding window stored in data/seen.json."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.schemas import NewsItem

SEEN_FILE = Path("data/seen.json")
_WINDOW_DAYS = 3

def _load() -> dict[str, str]:
    if not SEEN_FILE.exists():
        return {}
    return json.loads(SEEN_FILE.read_text())

def _save(seen: dict[str, str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2))

def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    seen = _load()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)).isoformat()
    seen = {h: ts for h, ts in seen.items() if ts >= cutoff}

    now = datetime.now(timezone.utc).isoformat()
    out: list[NewsItem] = []
    for item in items:
        h = item.hash_id
        if h not in seen:
            seen[h] = now
            out.append(item)
    _save(seen)
    return out
