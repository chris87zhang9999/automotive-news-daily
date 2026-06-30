"""Feishu group bot: send one short notification card with site link."""
import logging
import httpx

logger = logging.getLogger(__name__)


def build_notify_card(*, date: str, items: list, brief: str = "", site_url: str) -> dict:
    score3 = sum(1 for it in items if it.score == 3)
    score2 = sum(1 for it in items if it.score == 2)
    score1 = sum(1 for it in items if it.score == 1)
    brief_preview = (brief[:100] + "…") if len(brief) > 100 else brief

    if score3 > 0:
        header_color = "red"
    elif score2 > 0:
        header_color = "orange"
    else:
        header_color = "blue"

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"汽车质量情报 {date}"},
                "template": header_color,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"🚨 紧急 **{score3}** 条  ⚠️ 重要 **{score2}** 条  📊 背景 **{score1}** 条",
                    },
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": brief_preview},
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📖 查看完整情报"},
                            "type": "primary",
                            "url": f"{site_url}?date={date}",
                        }
                    ],
                },
            ],
        },
    }


def send_notify(*, cfg, date: str, items: list, brief: str = "", site_url: str) -> None:
    card = build_notify_card(date=date, items=items, brief=brief, site_url=site_url)
    webhook = cfg.feishu_bot_webhook
    if not webhook:
        logger.warning("FEISHU_BOT_WEBHOOK not set, skipping notification")
        return
    try:
        resp = httpx.post(webhook, json=card, timeout=10)
        resp.raise_for_status()
        logger.info("Feishu notification sent for %s", date)
    except Exception as ex:
        logger.warning("Feishu notification failed: %s", ex)
