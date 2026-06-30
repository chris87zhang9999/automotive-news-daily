from unittest.mock import MagicMock
from src.schemas import NewsItem
from src.brief import generate_brief


def _scored_item(title, score, note="", market="东南亚"):
    item = NewsItem(url=f"https://x.com/{title}", title=title, source_name="s",
                    region="r", published_at="", raw_text="")
    item.score = score
    item.note = note
    item.market = market
    item.summary = f"Summary of {title}"
    return item


def test_generate_brief_calls_llm_with_high_score_articles():
    llm = MagicMock()
    llm.chat.return_value = "今日重点：东南亚出现两起电池安全事件。"
    items = [
        _scored_item("NIO recall Thailand", score=2, note="Monitor supplier"),
        _scored_item("BYD sales record", score=0),
        _scored_item("Li Auto safety probe", score=3, note="Urgent"),
    ]
    brief = generate_brief(llm, items)
    assert "今日" in brief
    call_args = llm.chat.call_args
    assert "NIO recall Thailand" in call_args.kwargs["user"]
    assert "Li Auto safety probe" in call_args.kwargs["user"]
    assert "BYD sales record" not in call_args.kwargs["user"]


def test_generate_brief_returns_placeholder_when_no_high_score():
    llm = MagicMock()
    items = [_scored_item("BYD sales", score=0), _scored_item("Toyota launch", score=1)]
    brief = generate_brief(llm, items)
    assert brief != ""
    llm.chat.assert_not_called()


def test_generate_brief_returns_placeholder_on_llm_error():
    llm = MagicMock()
    llm.chat.side_effect = Exception("API error")
    items = [_scored_item("NIO recall", score=2, note="Monitor")]
    brief = generate_brief(llm, items)
    assert brief != ""   # placeholder, not empty


def test_generate_brief_includes_score3_and_score2_articles():
    llm = MagicMock()
    llm.chat.return_value = "Brief text."
    items = [
        _scored_item("Urgent item", score=3, note="Act now", market="中东"),
        _scored_item("Important item", score=2, note="Watch", market="西欧"),
        _scored_item("Background item", score=1),
    ]
    generate_brief(llm, items)
    call_user = llm.chat.call_args.kwargs["user"]
    assert "Urgent item" in call_user
    assert "Important item" in call_user
    assert "Background item" not in call_user
