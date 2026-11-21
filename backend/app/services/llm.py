import abc
import re

import httpx

from app.core.config import settings


class BaseLLMProvider(abc.ABC):
    """Abstract interface for LLM completion providers."""

    @abc.abstractmethod
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        pass


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini API Provider using direct HTTP REST requests."""
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"{system_prompt}\n\nUser Question:\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "maxOutputTokens": 2048,
            }
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API returned error {resp.status_code}: {resp.text}")
            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError):
                raise RuntimeError(f"Unexpected response structure from Gemini API: {data}")


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI API Provider."""
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API returned error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic Mock LLM Provider for offline evaluation and unit tests.
    Generates evidence-backed answers strictly quoting the provided context.
    """
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        # Extract cited sources from context prompt
        source_pattern = r'\[SOURCE:\s*([^\s#\]]+)#L(\d+)-L(\d+)\]'
        sources = re.findall(source_pattern, user_prompt)

        if not sources:
            return (
                "Based on the analyzed codebase, the requested information could not be established "
                "from the available source files."
            )

        citations_text = ", ".join([f"`{src[0]}#L{src[1]}-L{src[2]}`" for src in sources[:3]])
        first_src = sources[0]

        return (
            f"Based on the repository source code in {citations_text}:\n\n"
            f"The implementation addresses '{user_prompt.split('Question: ')[-1].strip()}' within `{first_src[0]}` "
            f"(lines {first_src[1]} to {first_src[2]}). The extracted logic handles this operation deterministically.\n\n"
            f"Reference citations: [{first_src[0]}#L{first_src[1]}-L{first_src[2]}]."
        )


def get_llm_provider() -> BaseLLMProvider:
    """Factory selecting the appropriate LLM provider based on configured API keys."""
    if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return GeminiLLMProvider(api_key=settings.GEMINI_API_KEY)
    elif settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMProvider(api_key=settings.OPENAI_API_KEY)
    return MockLLMProvider()
