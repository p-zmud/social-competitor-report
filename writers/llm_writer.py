# writers/llm_writer.py
from openai import OpenAI

from models import Post
from utils.settings import get_model, get_summary_prompt


class LLMWriter:
    """Writes per-brand content summaries via OpenRouter (OpenAI-compatible API).

    The model id is configurable: pass `model=...`, otherwise it is resolved from
    user settings (data/settings.json or OPENROUTER_MODEL), falling back to DEFAULT_MODEL.
    """

    DEFAULT_MODEL = "deepseek/deepseek-v4-flash"

    def __init__(self, api_key: str, model: str | None = None,
                 base_url: str = "https://openrouter.ai/api/v1",
                 summary_prompt: str | None = None):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model or get_model(self.DEFAULT_MODEL)
        self.summary_prompt = summary_prompt or get_summary_prompt()

    def _ask(self, prompt: str, max_tokens: int = 300) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()

    def write_competitor_summary(self, competitor_name: str, posts: list[Post]) -> str:
        """Return a 1-2 sentence English summary of a brand's content this period."""
        if not posts:
            return "No post data for this period."
        captions = "\n".join(f"- [{p.platform}] {p.caption[:100]}" for p in posts[:20])
        prompt = f"{self.summary_prompt}\n\nBrand: {competitor_name}\nPosts:\n{captions}"
        return self._ask(prompt, max_tokens=150)
