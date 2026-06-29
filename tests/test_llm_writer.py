# tests/test_llm_writer.py
from unittest.mock import MagicMock

from models import Post
from writers.llm_writer import LLMWriter


def make_post(caption, platform="instagram"):
    return Post(id="1", platform=platform, url="http://x.com",
                caption=caption, published_at="2026-02-10T10:00:00",
                likes=100, comments=10, shares=5, reach=2000, views=None)


def test_competitor_summary_returns_text_and_forwards_model(mocker):
    mock_openai = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "  Pizza Hut promoted new pizzas.  "
    mock_openai.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    mocker.patch("writers.llm_writer.OpenAI", return_value=mock_openai)

    writer = LLMWriter(api_key="fake", model="openai/gpt-4o-mini")
    summary = writer.write_competitor_summary("Pizza Hut Polska", [make_post("Nowa pizza!")])

    assert summary == "Pizza Hut promoted new pizzas."  # stripped
    _, kwargs = mock_openai.chat.completions.create.call_args
    assert kwargs["model"] == "openai/gpt-4o-mini"


def test_competitor_summary_empty_posts_short_circuits(mocker):
    mock_openai = MagicMock()
    mocker.patch("writers.llm_writer.OpenAI", return_value=mock_openai)
    writer = LLMWriter(api_key="fake", model="x")
    assert writer.write_competitor_summary("KFC Polska", []) == "No post data for this period."
    assert not mock_openai.chat.completions.create.called


def test_default_model_resolved_when_unspecified(mocker, monkeypatch):
    from utils import settings as st
    monkeypatch.setattr(st, "SETTINGS_PATH", "/nonexistent/settings.json")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    mocker.patch("writers.llm_writer.OpenAI", return_value=MagicMock())
    writer = LLMWriter(api_key="fake")
    assert writer.model == LLMWriter.DEFAULT_MODEL


def test_ask_returns_empty_when_content_none(mocker):
    fake_resp = mocker.MagicMock()
    fake_resp.choices = [mocker.MagicMock()]
    fake_resp.choices[0].message.content = None
    writer = LLMWriter(api_key="test", model="x")
    mocker.patch.object(writer.client.chat.completions, "create", return_value=fake_resp)
    assert writer._ask("prompt") == ""


def test_custom_summary_prompt_used_and_brand_posts_appended(mocker):
    mock_openai = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "ok"
    mock_openai.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    mocker.patch("writers.llm_writer.OpenAI", return_value=mock_openai)

    writer = LLMWriter(api_key="fake", model="x", summary_prompt="CUSTOM INSTRUCTIONS")
    writer.write_competitor_summary("KFC Polska", [make_post("Bucket time", platform="tiktok")])

    _, kwargs = mock_openai.chat.completions.create.call_args
    sent = kwargs["messages"][0]["content"]
    assert sent.startswith("CUSTOM INSTRUCTIONS")
    assert "Brand: KFC Polska" in sent
    assert "Posts:" in sent
    assert "[tiktok] Bucket time" in sent


def test_summary_prompt_defaults_from_settings(mocker, monkeypatch):
    from utils import settings as st
    monkeypatch.setattr(st, "SETTINGS_PATH", "/nonexistent/settings.json")
    monkeypatch.delenv("SUMMARY_PROMPT", raising=False)
    mocker.patch("writers.llm_writer.OpenAI", return_value=MagicMock())
    writer = LLMWriter(api_key="fake", model="x")
    assert writer.summary_prompt == st.DEFAULT_SUMMARY_PROMPT
