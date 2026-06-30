import json
from unittest.mock import MagicMock
from src.schemas import NewsItem
from src.summarizer import summarize_item, summarize_all, _parse_llm_json


def _item(title="Test article about NIO recall in Thailand", region="东南亚"):
    return NewsItem(url="https://x.com", title=title, source_name="s",
                    region=region, published_at="", raw_text="NIO recalls 500 units in Thailand due to brake defect.")


def test_parse_llm_json_valid():
    raw = '{"summary": "NIO recalled units.", "score": 2, "note": "Monitor brake supplier", "market": "东南亚"}'
    result = _parse_llm_json(raw)
    assert result["score"] == 2
    assert result["market"] == "东南亚"
    assert result["summary"] == "NIO recalled units."
    assert result["note"] == "Monitor brake supplier"


def test_parse_llm_json_with_markdown_fences():
    raw = '```json\n{"summary": "Test.", "score": 1, "note": "", "market": "北美"}\n```'
    result = _parse_llm_json(raw)
    assert result["score"] == 1
    assert result["market"] == "北美"


def test_parse_llm_json_fallback_on_invalid():
    result = _parse_llm_json("not json at all")
    assert result["score"] == 1   # fallback to background
    assert result["summary"] == ""
    assert result["note"] == ""


def test_parse_llm_json_clamps_invalid_score():
    raw = '{"summary": "Test.", "score": 99, "note": "", "market": "西欧"}'
    result = _parse_llm_json(raw)
    assert result["score"] == 1   # invalid score clamped to background


def test_summarize_item_populates_all_fields():
    llm = MagicMock()
    llm.chat.return_value = '{"summary": "NIO recalled 500 units.", "score": 2, "note": "Monitor brake supplier overlap.", "market": "东南亚"}'
    item = summarize_item(llm, _item())
    assert item.score == 2
    assert item.note == "Monitor brake supplier overlap."
    assert item.market == "东南亚"
    assert "NIO" in item.summary


def test_summarize_item_fallback_on_error():
    llm = MagicMock()
    llm.chat.side_effect = Exception("API error")
    item = summarize_item(llm, _item())
    assert item.summary == item.title   # fallback to title
    assert item.score == 1
    assert item.market == "东南亚"   # fallback to item.region


def test_summarize_item_uses_title_when_summary_empty():
    llm = MagicMock()
    llm.chat.return_value = '{"summary": "", "score": 0, "note": "", "market": "北美"}'
    item = summarize_item(llm, _item())
    assert item.summary == item.title   # empty summary → fallback to title
    assert item.score == 0


def test_summarize_all_preserves_order():
    llm = MagicMock()
    llm.chat.return_value = '{"summary": "Test.", "score": 1, "note": "", "market": "北美"}'
    items = [_item(f"Article {i}") for i in range(5)]
    result = summarize_all(llm, items)
    for i, item in enumerate(result):
        assert item.title == f"Article {i}"


def test_summarize_all_returns_all_even_with_errors():
    llm = MagicMock()
    llm.chat.side_effect = [Exception("fail"), '{"summary": "OK.", "score": 1, "note": "", "market": "国际"}']
    items = [_item("Article 0"), _item("Article 1")]
    result = summarize_all(llm, items)
    assert len(result) == 2


def test_parse_llm_json_normalizes_europe_to_west_europe():
    raw = '{"summary": "Test.", "score": 1, "note": "", "market": "欧洲"}'
    result = _parse_llm_json(raw)
    assert result["market"] == "西欧"


def test_parse_llm_json_normalizes_uk_to_west_europe():
    raw = '{"summary": "Test.", "score": 2, "note": "Monitor", "market": "英国"}'
    result = _parse_llm_json(raw)
    assert result["market"] == "西欧"


def test_parse_llm_json_preserves_canonical_market():
    raw = '{"summary": "Test.", "score": 1, "note": "", "market": "东南亚"}'
    result = _parse_llm_json(raw)
    assert result["market"] == "东南亚"


def test_parse_llm_json_unknown_market_falls_back_to_region():
    raw = '{"summary": "Test.", "score": 1, "note": "", "market": "UnknownRegion"}'
    result = _parse_llm_json(raw, fallback_region="东南亚")
    assert result["market"] == "东南亚"


def test_summarize_item_passes_brand_hint_to_llm():
    llm = MagicMock()
    llm.chat.return_value = '{"summary": "Smart #6 EHD launched.", "score": 0, "note": "", "market": "中国"}'
    item = _item()
    item.brand = "Smart"
    summarize_item(llm, item)
    call_kwargs = llm.chat.call_args
    user_msg = call_kwargs[1]["user"] if call_kwargs[1] else call_kwargs[0][1]
    assert "Detected brand: Smart" in user_msg
