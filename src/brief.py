"""Generate a quality-director daily brief from high-score articles."""
import logging
from src.llm_client import LLMClient
from src.schemas import NewsItem

logger = logging.getLogger(__name__)

_BRIEF_SYSTEM = """你是理想汽车海外质量业务的情报主管。
根据今日筛选出的重要情报，用≤200字中文写一段质量总监视角的每日简报。
要求：指出关键风险点、竞品动态启示、需要跟进的行动建议。
语气专业简练，不要重复罗列新闻标题，要做业务判断和推论。"""

_NO_INTEL_PLACEHOLDER = "今日无 score≥2 的重要质量情报，市场整体平稳。"


def generate_brief(llm: LLMClient, items: list[NewsItem]) -> str:
    high_value = [it for it in items if it.score >= 2]
    if not high_value:
        return _NO_INTEL_PLACEHOLDER

    bullets = "\n".join(
        f"- [{it.market}] {it.title} (score={it.score}): {it.summary} | 含义: {it.note}"
        for it in high_value
    )
    try:
        return llm.chat(
            system=_BRIEF_SYSTEM,
            user=f"今日重要情报列表：\n{bullets}",
            max_tokens=400,
            temperature=0.3,
        )
    except Exception as ex:
        logger.warning("brief generation failed: %s", ex)
        return _NO_INTEL_PLACEHOLDER
