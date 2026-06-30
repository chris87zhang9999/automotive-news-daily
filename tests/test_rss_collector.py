from unittest.mock import patch, MagicMock
from src.collectors.rss import RssCollector
from src.schemas import NewsItem

_FAKE_ENTRY = {
    "link": "https://example.com/news/1",
    "title": "BYD announces new EV model",
    "published": "2026-06-29T08:00:00Z",
    "summary": "BYD has unveiled its new electric sedan.",
}

def test_rss_collector_returns_news_items():
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[MagicMock(**_FAKE_ENTRY)])
        collector = RssCollector(feeds=["https://example.com/rss"], region="中国")
        items = collector.collect()
    assert len(items) == 1
    assert isinstance(items[0], NewsItem)
    assert items[0].url == "https://example.com/news/1"
    assert items[0].region == "中国"

def test_rss_collector_skips_failed_feed():
    with patch("feedparser.parse", side_effect=Exception("timeout")):
        collector = RssCollector(feeds=["https://bad.example.com/rss"], region="北美")
        items = collector.collect()
    assert items == []

def test_rss_collector_deduplicates_within_batch():
    entry = MagicMock(**_FAKE_ENTRY)
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[entry, entry])
        collector = RssCollector(feeds=["https://a.com/rss", "https://b.com/rss"], region="北美")
        items = collector.collect()
    assert len(items) == 1
