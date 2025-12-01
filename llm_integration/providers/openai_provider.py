# File: llm_integration/providers/openai_provider.py

import json
import time
import asyncio
from typing import List, Dict, Any, Optional
import httpx
import logging

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    Direct OpenAI API provider.
    Uses the official OpenAI REST API for chat completions.
    """

    def __init__(self, api_key: str, model_name: str, timeout: Optional[int] = None, base_url: Optional[str] = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model_name: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')
            timeout: Request timeout in seconds
            base_url: Optional custom base URL (for OpenAI-compatible APIs)
        """
        super().__init__(api_key, model_name, timeout)
        self.base_url = base_url or "https://api.openai.com/v1"
        self.endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

    def get_provider_name(self) -> str:
        return "openai"

    async def request(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request to OpenAI API.

        Returns:
            Response in OpenAI format with 'choices' array
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if functions:
            payload["functions"] = functions

        if function_call:
            payload["function_call"] = function_call

        # Calculate metrics
        try:
            messages_text = "\n".join([m.get('content', '') for m in messages if isinstance(m, dict)])
            chars = len(messages_text)
            est_tokens = max(1, int(chars / 4))
        except Exception:
            chars = 0
            est_tokens = 0

        logger.info(
            f"OpenAI request -> model={self.model_name} messages={len(messages)} "
            f"chars={chars} est_tokens~{est_tokens} max_tokens={max_tokens or 'default'} "
            f"functions={len(functions) if functions else 0}"
        )
        logger.debug(f"OpenAI payload: {json.dumps(payload, indent=2)}")

        # Retry logic for network issues
        max_attempts = 2
        backoff_seconds = 0.8

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    start_time = time.time()
                    response = await client.post(self.endpoint, json=payload, headers=headers)
                    duration = time.time() - start_time

                    response.raise_for_status()
                    response_data = response.json()

                    # Log finish reason
                    try:
                        choices = response_data.get('choices', [])
                        if choices:
                            finish_reason = choices[0].get('finish_reason')
                            logger.info(
                                f"OpenAI response finish_reason={finish_reason} "
                                f"duration_s={duration:.2f} est_tokens_sent~{est_tokens}"
                            )
                            if finish_reason == 'length':
                                logger.warning(
                                    "OpenAI response was truncated (finish_reason: 'length'). "
                                    "Consider reducing prompt size or increasing max_tokens."
                                )
                    except Exception:
                        pass

                    logger.debug(f"OpenAI response: {json.dumps(response_data, indent=2)}")
                    return response_data

                except httpx.ReadTimeout:
                    logger.warning(f"OpenAI request read timeout on attempt {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        await asyncio.sleep(backoff_seconds * attempt)
                        continue
                    logger.error(f"OpenAI request timed out after {max_attempts} attempts")

                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"OpenAI API error: status={e.response.status_code} "
                        f"response={e.response.text[:500]}"
                    )
                    return None

                except httpx.TimeoutException:
                    logger.warning(f"OpenAI request timeout on attempt {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        await asyncio.sleep(backoff_seconds * attempt)
                        continue
                    logger.error(f"OpenAI request timed out after {max_attempts} attempts")

                except httpx.RequestError as e:
                    logger.error(f"OpenAI network error: {e}", exc_info=True)
                    return None

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode OpenAI JSON response: {response.text[:500]}")
                    return None

                except Exception as e:
                    logger.error(f"Unexpected error during OpenAI request: {e}", exc_info=True)
                    return None

        return None
