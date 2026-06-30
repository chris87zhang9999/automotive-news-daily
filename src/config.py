import os
from dataclasses import dataclass
from dotenv import load_dotenv

_REQUIRED = ["LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "FEISHU_BOT_WEBHOOK"]

@dataclass(frozen=True)
class Config:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    feishu_bot_webhook: str

def load_config() -> Config:
    load_dotenv()
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise ValueError(f"missing env vars: {missing}")
    return Config(
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_model=os.environ["LLM_MODEL"],
        feishu_bot_webhook=os.environ["FEISHU_BOT_WEBHOOK"],
    )
