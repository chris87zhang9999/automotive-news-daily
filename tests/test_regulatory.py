from unittest.mock import patch, MagicMock
from src.collectors.samr import SamrCollector
from src.collectors.rapex import RapexCollector
from src.collectors.nhtsa import NhtsaCollector
from src.schemas import NewsItem

_SAMR_XML = """<?xml version="1.0"?>
<recalls>
  <recall>
    <title>理想汽车召回部分 L9 车辆</title>
    <url>https://www.samr.gov.cn/cpgls/12345</url>
    <pubDate>2026-06-29</pubDate>
    <description>因悬架问题召回 1200 辆</description>
  </recall>
</recalls>"""

def test_samr_returns_news_items():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = MagicMock(text=_SAMR_XML, status_code=200)
        items = SamrCollector().collect()
    assert len(items) == 1
    assert items[0].region == "中国"
    assert items[0].priority == "P3"  # filter.py assigns priority later

def test_samr_handles_http_error():
    with patch("httpx.get", side_effect=Exception("connection reset")):
        items = SamrCollector().collect()
    assert items == []

def test_nhtsa_returns_news_items():
    with patch("feedparser.parse") as mock:
        entry = MagicMock()
        entry.title = "NHTSA Recall: Li Auto L7 investigation"
        entry.link = "https://www.nhtsa.gov/recall/123"
        entry.published = "Mon, 29 Jun 2026 00:00:00 GMT"
        entry.summary = "Investigation opened."
        mock.return_value = MagicMock(entries=[entry])
        items = NhtsaCollector().collect()
    assert len(items) == 1
    assert items[0].region == "北美"
