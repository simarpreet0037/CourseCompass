from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from langchain.llms.base import LLM
from langchain.schema import LLMResult, Generation
import requests

class GroqLLM(LLM, BaseModel):
    """
    Minimal Groq chat-completions wrapper for LangChain's LLM interface.
    """

    api_key: str = Field(..., exclude=True)
    model: str = "llama-3.1-8b-instant"
    api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    timeout: float = 30.0  # seconds
    temperature: float = 0.0
    max_tokens: Optional[int] = 512

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # For debugging, keep but avoid printing secrets
        print("Payload sent to Groq API:", {**payload, "messages": "[omitted for brevity]"})

        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
        if not resp.ok:
            # Surface Groq's actual error text so you know WHY it's 400
            raise RuntimeError(f"Groq error {resp.status_code}: {resp.text}")

        data = resp.json()
        # Optional debug
        print("Response JSON keys:", list(data.keys()))
        return data

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if stop:
            payload["stop"] = stop

        data = self._post(payload)

        # Defensive extraction
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError(f"Unexpected Groq response format: {data}")

    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None, **kwargs: Any) -> LLMResult:
        generations = []
        for prompt in prompts:
            text = self._call(prompt, stop)
            generations.append([Generation(text=text)])
        return LLMResult(generations=generations)

    @property
    def _llm_type(self) -> str:
        return "groq"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        # Helps LangChain cache/trace different model configs
        return {
            "model": self.model,
            "api_url": self.api_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
