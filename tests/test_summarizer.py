from unittest.mock import MagicMock
from src.schemas import NewsItem
from src.summarizer import summarize_item, summarize_all

def _item(url: str, title: str) -> NewsItem:
    return NewsItem(url=url, title=title, source_name="s",
                    region="r", published_at="", raw_text="some content")

def test_summarize_item_fills_summary():
    llm = MagicMock()
    llm.chat.return_value = "Li Auto recalled 1200 units in Kazakhstan."
    item = _item("https://a.com", "Li Auto recall")
    result = summarize_item(llm, item)
    assert result.summary == "Li Auto recalled 1200 units in Kazakhstan."
    assert llm.chat.called

def test_summarize_item_fallback_on_error():
    llm = MagicMock()
    llm.chat.side_effect = Exception("API error")
    item = _item("https://b.com", "Fallback title")
    result = summarize_item(llm, item)
    assert result.summary == "Fallback title"

def test_summarize_all_preserves_order():
    llm = MagicMock()
    llm.chat.side_effect = lambda **_: "summary"
    items = [_item(f"https://x.com/{i}", f"title {i}") for i in range(5)]
    results = summarize_all(llm, items, max_workers=2)
    assert [r.url for r in results] == [i.url for i in items]

def test_summarize_all_returns_all_even_with_errors():
    llm = MagicMock()
    llm.chat.side_effect = [Exception("err"), "good summary", Exception("err")]
    items = [_item(f"https://x.com/{i}", f"t{i}") for i in range(3)]
    results = summarize_all(llm, items, max_workers=3)
    assert len(results) == 3
