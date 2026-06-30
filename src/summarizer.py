"""Concurrent GLM-4-flash quality-intel evaluator: score + summary + note + market per NewsItem."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.llm_client import LLMClient
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_SYSTEM = """You are an intelligence analyst for Li Auto's overseas quality operations team.
Li Auto exports to: Middle East, Central Asia, Russia, Southeast Asia, South Korea, and Europe.

Analyze the automotive news article and return ONLY valid JSON with these exact keys:
- "summary": factual summary in ≤80 English words covering what happened, which brand/model, which market, and impact
- "score": integer 0-3 using this rubric:
    3 = Urgent: Li Auto product recall/safety investigation/regulatory mandate in export market
    2 = Important: competitor Chinese brand quality incident in export market; regulatory change affecting Li Auto markets; supplier safety issue
    1 = Background: market trends, competitive dynamics, indirect reference value
    0 = Noise: pure sales/financial news, new model launches with no quality angle, unrelated to Li Auto export markets
- "note": ≤30-word business implication in Chinese for Li Auto quality ops (required when score≥2, empty string otherwise)
- "market": the specific primary market this article concerns — use one of: 北美/西欧/中欧东欧/中东/俄罗斯/中亚/东南亚/韩国/日本/澳大利亚/中国/全球 (only use 全球 when genuinely multi-region)

Return only the JSON object, no markdown, no explanation."""

_FALLBACK_MARKET_MAP = {
    "北美": "北美", "欧洲": "西欧", "西欧": "西欧",
    "中东": "中东", "俄罗斯/中亚": "俄罗斯", "东南亚": "东南亚",
    "东亚": "韩国", "中国": "中国", "质量召回": "全球",
    "国际": "全球",
}


def _parse_llm_json(raw: str, fallback_region: str = "") -> dict:
    """Parse LLM JSON response; return safe fallback dict on any parse error."""
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        score = int(data.get("score", 1))
        if score not in (0, 1, 2, 3):
            score = 1
        return {
            "summary": str(data.get("summary", "")),
            "score": score,
            "note": str(data.get("note", "")),
            "market": str(data.get("market", _FALLBACK_MARKET_MAP.get(fallback_region, "全球"))),
        }
    except Exception:
        return {
            "summary": "",
            "score": 1,
            "note": "",
            "market": _FALLBACK_MARKET_MAP.get(fallback_region, "全球"),
        }


def summarize_item(llm: LLMClient, item: NewsItem) -> NewsItem:
    try:
        raw = llm.chat(
            system=_SYSTEM,
            user=f"Title: {item.title}\n\nContent: {item.raw_text[:1500]}",
            max_tokens=350,
            temperature=0.1,
        )
        parsed = _parse_llm_json(raw, fallback_region=item.region)
        item.summary = parsed["summary"] or item.title
        item.score = parsed["score"]
        item.note = parsed["note"]
        item.market = parsed["market"] or item.region
    except Exception as ex:
        logger.warning("summarize failed for %s: %s", item.url, ex)
        item.summary = item.title
        item.score = 1
        item.market = item.region
    return item


def summarize_all(llm: LLMClient, items: list[NewsItem], max_workers: int = 5) -> list[NewsItem]:
    # Use object identity (id) as index key to handle items that may share the same URL/hash_id.
    index = {id(item): i for i, item in enumerate(items)}
    results: list[NewsItem] = [None] * len(items)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(summarize_item, llm, item): item for item in items}
        for future in as_completed(futures):
            item = future.result()
            results[index[id(item)]] = item

    return results
