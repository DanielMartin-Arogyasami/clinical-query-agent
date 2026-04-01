"""
Shared utility functions.
[FIX C2] parse_llm_json() strips markdown fences from LLM output.
[FIX C4] Retry/backoff via tenacity.
"""
from __future__ import annotations
import json
import re
import yaml
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from config.settings import PROJECT_ROOT


def load_agent_config(agent_name: str) -> dict:
    config_path = PROJECT_ROOT / "config" / "agents.yaml"
    with open(config_path, encoding="utf-8") as f:
        all_configs = yaml.safe_load(f)
    if agent_name not in all_configs:
        raise KeyError(f"No config for agent '{agent_name}' in agents.yaml")
    return all_configs[agent_name]


def load_all_agent_configs() -> dict:
    config_path = PROJECT_ROOT / "config" / "agents.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_llm(model: str | None = None):
    """Construct the appropriate LangChain LLM based on config."""
    from config.settings import settings
    model = model or settings.llm_model
    if model.startswith("claude"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=settings.anthropic_api_key)
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=settings.openai_api_key)


def parse_llm_json(raw: str) -> dict:
    """
    Parse JSON from LLM output, stripping markdown fences and preamble. [FIX C2]

    Handles:
    - ```json ... ``` code fences
    - Leading/trailing non-JSON text
    - Nested braces
    """
    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find the first { ... } block
    brace_start = cleaned.find("{")
    if brace_start == -1:
        raise json.JSONDecodeError("No JSON object found in LLM output", cleaned, 0)

    depth = 0
    for i in range(brace_start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[brace_start : i + 1])

    raise json.JSONDecodeError("Unterminated JSON object in LLM output", cleaned, brace_start)


def _is_retryable_error(exc: BaseException) -> bool:
    """Return True only for transient errors worth retrying. [BUG4 FIX]"""
    # Always retry on network-level errors
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    # Check for rate-limit / transient HTTP errors by class name
    # (avoids hard dependency on openai/anthropic SDK exception classes)
    exc_name = type(exc).__name__
    if exc_name in (
        "RateLimitError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
        "ServiceUnavailableError",
    ):
        return True
    # Check HTTP status codes if available (e.g., httpx, requests)
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int) and status in (429, 500, 502, 503, 504):
        return True
    return False


def invoke_llm_with_retry(llm, messages: list[dict], max_retries: int = 3):
    """
    Invoke LLM with exponential backoff retry. [FIX C4]
    [BUG4 FIX] Only retries transient errors — auth/permission failures fail fast.
    """
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def _call():
        return llm.invoke(messages)

    return _call()
