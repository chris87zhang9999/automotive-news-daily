import json
from unittest.mock import patch, MagicMock
from src.config import Config
from src.schemas import NewsItem
from src.delivery.feishu import build_notify_card, send_notify


def _item(score=1):
    it = NewsItem(url="https://x.com", title="t", source_name="s",
                  region="r", published_at="", raw_text="")
    it.score = score
    return it


def test_build_notify_card_shows_score_counts():
    items = [_item(3), _item(2), _item(2), _item(1), _item(1), _item(1)]
    card = build_notify_card(
        date="2026-06-30",
        items=items,
        brief="今日重点：东南亚出现电池事件。",
        site_url="https://example.com"
    )
    body = json.dumps(card, ensure_ascii=False)
    assert "🚨" in body
    assert "⚠️" in body
    assert "📊" in body
    # counts: 1 urgent, 2 important, 3 background
    assert "紧急 **1**" in body
    assert "重要 **2**" in body
    assert "背景 **3**" in body


def test_build_notify_card_brief_preview_truncated():
    brief = "A" * 200   # longer than 100 chars
    card = build_notify_card(date="2026-06-30", items=[_item()],
                             brief=brief, site_url="https://example.com")
    body = json.dumps(card, ensure_ascii=False)
    assert "A" * 100 in body
    assert "A" * 101 not in body
    assert "…" in body


def test_build_notify_card_header_red_when_urgent():
    card = build_notify_card(date="2026-06-30", items=[_item(3)],
                             brief="", site_url="https://example.com")
    assert card["card"]["header"]["template"] == "red"


def test_build_notify_card_header_orange_when_important_only():
    card = build_notify_card(date="2026-06-30", items=[_item(2)],
                             brief="", site_url="https://example.com")
    assert card["card"]["header"]["template"] == "orange"


def test_build_notify_card_header_blue_when_background_only():
    card = build_notify_card(date="2026-06-30", items=[_item(1)],
                             brief="", site_url="https://example.com")
    assert card["card"]["header"]["template"] == "blue"


def test_build_notify_card_has_link_button():
    card = build_notify_card(date="2026-06-30", items=[_item()],
                             brief="", site_url="https://example.com")
    body = json.dumps(card)
    assert "https://example.com?date=2026-06-30" in body


def test_send_notify_posts_card():
    cfg = Config(llm_api_key="k", llm_base_url="u", llm_model="m",
                 feishu_bot_webhook="https://webhook.example.com")
    with patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        send_notify(cfg=cfg, date="2026-06-30", items=[_item()],
                    brief="Brief text", site_url="https://example.com")
    assert mock_post.called
