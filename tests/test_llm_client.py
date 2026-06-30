from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient
from src.config import Config

def _cfg():
    return Config(llm_api_key="k", llm_base_url="https://x.com/v4/",
                  llm_model="glm-4-flash", feishu_bot_webhook="https://w")

def test_chat_returns_content(monkeypatch):
    client = LLMClient(_cfg())
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "hello"
    monkeypatch.setattr(client._client.chat.completions, "create",
                        lambda **_: mock_resp)
    result = client.chat(system="sys", user="usr")
    assert result == "hello"
