import json, tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from src.schemas import NewsItem
from src.dedup import deduplicate

def _item(url: str) -> NewsItem:
    return NewsItem(url=url, title="t", source_name="s",
                    region="r", published_at="", raw_text="")

def test_new_items_pass_through(tmp_path):
    items = [_item("https://a.com"), _item("https://b.com")]
    with patch("src.dedup.SEEN_FILE", tmp_path / "seen.json"):
        result = deduplicate(items)
    assert len(result) == 2

def test_already_seen_items_filtered(tmp_path):
    item = _item("https://a.com")
    seen_file = tmp_path / "seen.json"
    now = datetime.now(timezone.utc).isoformat()
    seen_file.write_text(json.dumps({item.hash_id: now}))
    with patch("src.dedup.SEEN_FILE", seen_file):
        result = deduplicate([item])
    assert result == []

def test_old_entries_evicted(tmp_path):
    item = _item("https://a.com")
    seen_file = tmp_path / "seen.json"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    seen_file.write_text(json.dumps({item.hash_id: old_ts}))
    with patch("src.dedup.SEEN_FILE", seen_file):
        result = deduplicate([item])
    assert len(result) == 1

def test_seen_file_updated_after_dedup(tmp_path):
    item = _item("https://new.com")
    seen_file = tmp_path / "seen.json"
    with patch("src.dedup.SEEN_FILE", seen_file):
        deduplicate([item])
    saved = json.loads(seen_file.read_text())
    assert item.hash_id in saved
