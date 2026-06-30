from unittest.mock import patch, MagicMock
from src.schemas import NewsItem
from src.delivery.feishu import build_notify_card, send_notify

def _item(priority: str, brand: str = "") -> NewsItem:
    item = NewsItem(url="https://x.com", title="t", source_name="s",
                    region="r", published_at="", raw_text="")
    item.priority = priority
    item.brand = brand
    return item

def test_build_notify_card_returns_dict():
    items = [_item("P0", "Li Auto"), _item("P1", "Li Auto"), _item("P2", "BYD")]
    card = build_notify_card(items, date="2026-06-29",
                             site_url="https://user.github.io/automotive-news-daily")
    assert card["msg_type"] == "interactive"
    assert "card" in card

def test_build_notify_card_includes_counts():
    items = [_item("P0"), _item("P1"), _item("P2"), _item("P2"), _item("P3")]
    card = build_notify_card(items, date="2026-06-29", site_url="https://s.io")
    content = str(card)
    assert "P0" in content or "🚨" in content
    assert "5" in content  # total count

def test_send_notify_posts_once():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_notify([_item("P3")], webhook="https://wh.example.com",
                    date="2026-06-29", site_url="https://s.io")
    assert mock_post.call_count == 1
