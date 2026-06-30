from unittest.mock import patch, MagicMock
from src.schemas import NewsItem

def _fake_item(url: str, title: str, priority: str = "P3") -> NewsItem:
    item = NewsItem(url=url, title=title, source_name="s",
                    region="北美", published_at="", raw_text="content")
    item.priority = priority
    item.summary = "100-word English summary."
    return item

def test_main_runs_without_error(tmp_path):
    fake_items = [_fake_item(f"https://x.com/{i}", f"Car News {i}") for i in range(5)]
    with (
        patch("entrypoints.collect_daily.RssCollector") as MockRss,
        patch("entrypoints.collect_daily.SamrCollector") as MockSamr,
        patch("entrypoints.collect_daily.RapexCollector") as MockRapex,
        patch("entrypoints.collect_daily.NhtsaCollector") as MockNhtsa,
        patch("entrypoints.collect_daily.filter_and_prioritize", return_value=fake_items),
        patch("entrypoints.collect_daily.deduplicate", return_value=fake_items),
        patch("entrypoints.collect_daily.summarize_all", return_value=fake_items),
        patch("entrypoints.collect_daily.generate_brief", return_value="Test brief."),
        patch("entrypoints.collect_daily.send_notify"),
        patch("entrypoints.collect_daily.load_config",
              return_value=MagicMock(llm_api_key="k", llm_base_url="u",
                                     llm_model="m", feishu_bot_webhook="w")),
        patch("entrypoints.collect_daily.REPORTS_DIR", tmp_path),
    ):
        for Mock in [MockRss, MockSamr, MockRapex, MockNhtsa]:
            Mock.return_value.collect.return_value = fake_items
        from entrypoints.collect_daily import main
        exit_code = main()
    assert exit_code == 0

def test_main_exits_zero_when_no_items(tmp_path):
    with (
        patch("entrypoints.collect_daily.RssCollector") as MockRss,
        patch("entrypoints.collect_daily.SamrCollector") as MockSamr,
        patch("entrypoints.collect_daily.RapexCollector") as MockRapex,
        patch("entrypoints.collect_daily.NhtsaCollector") as MockNhtsa,
        patch("entrypoints.collect_daily.filter_and_prioritize", return_value=[]),
        patch("entrypoints.collect_daily.deduplicate", return_value=[]),
        patch("entrypoints.collect_daily.load_config",
              return_value=MagicMock(llm_api_key="k", llm_base_url="u",
                                     llm_model="m", feishu_bot_webhook="w")),
        patch("entrypoints.collect_daily.REPORTS_DIR", tmp_path),
    ):
        for Mock in [MockRss, MockSamr, MockRapex, MockNhtsa]:
            Mock.return_value.collect.return_value = []
        from entrypoints.collect_daily import main
        exit_code = main()
    assert exit_code == 0
