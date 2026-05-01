from __future__ import annotations

import json
import os
import time
from typing import Any, TypedDict
from urllib import error as urllib_error
from urllib import request as urllib_request

import logging

from .llm_configurations import LLM, ModelInfo

logger = logging.getLogger(__name__)


class OpenRouterMessage(TypedDict, total=False):
    role: str
    content: str | list[dict[str, Any]]


class OpenRouterChoice(TypedDict):
    message: OpenRouterMessage


class OpenRouterUsage(TypedDict, total=False):
    completion_tokens_details: dict[str, Any]
    reasoning_tokens: int


class OpenRouterResponse(TypedDict, total=False):
    choices: list[OpenRouterChoice]
    usage: OpenRouterUsage


class OpenRouter_LLM(LLM):
    def __init__(self, name: str, model: ModelInfo, verbose: bool = False):
        super().__init__(name, model)
        self.model = model
        self.verbose = verbose
        self.chat_history: list[dict[str, Any]] = []
        self.system_prompt = "You are a specialist in code fault localization"
        self.request_delay_seconds = 0.4
        self.response_delay_seconds = 0.5
        self.api_url = os.getenv(
            "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
        )

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("NO OPENROUTER_API_KEY, set it")
            self.api_key = None
            return

        self.api_key = api_key
        logger.info("OPENROUTER KEY PROVIDED")

    def _build_messages(self, prompt: str) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        system_prompt = self.system_prompt.strip()
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in self.chat_history:
            role = msg.get("role")
            content = msg.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})
        return messages

    def _extract_reply(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return ""

        message = first_choice.get("message")
        if not isinstance(message, dict):
            return ""

        content = message.get("content")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_blocks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        text_blocks.append(text_value)
            return "".join(text_blocks)

        return ""

    def _get_response(self, prompt: str) -> str:
        time.sleep(2)
        if self.api_key is None:
            return "Mock Reply"

        messages = self._build_messages(prompt)
        payload: dict[str, Any] = {
            "model": self.model.model_id,
            "messages": messages,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "verifixer_fault_localization"),
        }

        if self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)

        request = urllib_request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenRouter request failed with HTTP {exc.code}: {error_body}"
            ) from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

        response_payload = json.loads(body)
        if not isinstance(response_payload, dict):
            raise RuntimeError("OpenRouter request failed: invalid JSON response")
        reply = self._extract_reply(response_payload)
        usage = response_payload.get("usage")
        if isinstance(usage, dict):
            completion_details = usage.get("completion_tokens_details")
            if isinstance(completion_details, dict):
                reasoning_tokens = completion_details.get("reasoning_tokens")
                if isinstance(reasoning_tokens, int):
                    self.reasoning_tokens_output += reasoning_tokens
            reasoning_tokens = usage.get("reasoning_tokens")
            if isinstance(reasoning_tokens, int):
                self.reasoning_tokens_output += reasoning_tokens

        self.chat_history.append({"role": "user", "content": prompt})
        self.chat_history.append({"role": "assistant", "content": reply})

        return reply
