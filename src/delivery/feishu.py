"""Feishu group bot: send one short notification card with site link."""
import logging
import httpx
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

def build_notify_card(items: list[NewsItem], date: str, site_url: str) -> dict:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in items:
        counts[item.priority] = counts.get(item.priority, 0) + 1

    parts = []
    if counts["P0"]:
        parts.append(f"🚨 质量预警 **{counts['P0']}** 条")
    if counts["P1"]:
        parts.append(f"⭐ 理想汽车 **{counts['P1']}** 条")
    if counts["P2"]:
        parts.append(f"🇨🇳 中国品牌 **{counts['P2']}** 条")
    if counts["P3"]:
        parts.append(f"🌍 国际品牌 **{counts['P3']}** 条")

    summary_line = "  |  ".join(parts)
    page_url = f"{site_url.rstrip('/')}?date={date}"

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚗 汽车日报  {date}  |  {len(items)} 条",
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": summary_line},
                },
                {
                    "tag": "action",
                    "actions": [{
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📖 查看全文"},
                        "url": page_url,
                        "type": "primary",
                    }],
                },
            ],
        },
    }

def send_notify(items: list[NewsItem], webhook: str, date: str, site_url: str) -> None:
    card = build_notify_card(items, date=date, site_url=site_url)
    try:
        resp = httpx.post(webhook, json=card, timeout=15)
        resp.raise_for_status()
        logger.info("feishu notify sent (%d items)", len(items))
    except Exception as ex:
        logger.error("feishu notify failed: %s", ex)
