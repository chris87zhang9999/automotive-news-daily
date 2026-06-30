"""Multi-provider LLM client (OpenAI-compatible). Retries 3x then circuit-breaks."""
import logging
from openai import OpenAI, BadRequestError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
from src.config import Config

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)

    # 400 BadRequest = content filter / bad params, never retry (智谱 1301)
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8),
           retry=retry_if_not_exception_type(BadRequestError), reraise=True)
    def chat(self, *, system: str, user: str, max_tokens: int = 300,
             temperature: float = 0.2) -> str:
        resp = self._client.chat.completions.create(
            model=self._cfg.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()
