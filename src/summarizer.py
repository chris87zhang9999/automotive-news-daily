"""Concurrent GLM-4-flash summarizer: 100-word English summary per NewsItem."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.llm_client import LLMClient
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an automotive industry analyst. Summarize the following news item "
    "in exactly 100 English words. Cover: what happened, which brand/model, "
    "which market/region, and why it matters to the industry. "
    "Do not invent facts not present in the source."
)

def summarize_item(llm: LLMClient, item: NewsItem) -> NewsItem:
    try:
        item.summary = llm.chat(
            system=_SYSTEM,
            user=f"Title: {item.title}\n\nContent: {item.raw_text[:1500]}",
            max_tokens=250,
            temperature=0.2,
        )
    except Exception as ex:
        logger.warning("summarize failed for %s: %s", item.url, ex)
        item.summary = item.title
    return item

def summarize_all(llm: LLMClient, items: list[NewsItem], max_workers: int = 5) -> list[NewsItem]:
    index = {item.hash_id: i for i, item in enumerate(items)}
    results: list[NewsItem] = [None] * len(items)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(summarize_item, llm, item): item for item in items}
        for future in as_completed(futures):
            item = future.result()
            results[index[item.hash_id]] = item

    return results
