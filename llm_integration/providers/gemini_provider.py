# File: llm_integration/providers/gemini_provider.py

import json
import time
import asyncio
from typing import List, Dict, Any, Optional
import httpx
import logging

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Direct Google Gemini API provider.
    Converts between OpenAI format and Gemini format.
    """

    def __init__(self, api_key: str, model_name: str, timeout: Optional[int] = None):
        """
        Initialize Gemini provider.

        Args:
            api_key: Google AI API key
            model_name: Model name (e.g., 'gemini-1.5-pro', 'gemini-1.5-flash')
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, model_name, timeout)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def get_provider_name(self) -> str:
        return "gemini"

    def _convert_messages_to_gemini(self, messages: List[Dict[str, str]]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Convert OpenAI-style messages to Gemini format.

        Returns:
            (system_instruction, contents) tuple
        """
        system_instruction = None
        contents = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'system':
                # Gemini uses systemInstruction for system messages
                if system_instruction is None:
                    system_instruction = content
                else:
                    # If multiple system messages, concatenate
                    system_instruction += "\n\n" + content
            elif role == 'user':
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == 'assistant':
                contents.append({
                    "role": "model",  # Gemini uses 'model' instead of 'assistant'
                    "parts": [{"text": content}]
                })

        return system_instruction, contents

    def _convert_functions_to_gemini(self, functions: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """
        Convert OpenAI function format to Gemini function declarations.
        """
        if not functions:
            return None

        declarations = []
        for func in functions:
            declaration = {
                "name": func.get("name"),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {})
            }
            declarations.append(declaration)

        return declarations

    def _convert_gemini_response_to_openai(self, gemini_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Gemini response to OpenAI format.
        """
        candidates = gemini_response.get('candidates', [])
        if not candidates:
            logger.warning("Gemini response has no candidates")
            return {
                "choices": [],
                "model": self.model_name,
                "usage": {}
            }

        candidate = candidates[0]
        content_part = candidate.get('content', {})
        parts = content_part.get('parts', [])
        finish_reason = candidate.get('finishReason', 'stop')

        # Map Gemini finish reasons to OpenAI format
        finish_reason_map = {
            'STOP': 'stop',
            'MAX_TOKENS': 'length',
            'SAFETY': 'content_filter',
            'RECITATION': 'content_filter',
            'OTHER': 'stop'
        }
        openai_finish_reason = finish_reason_map.get(finish_reason, 'stop')

        # Extract content and function call
        message_content = ""
        function_call = None

        for part in parts:
            if 'text' in part:
                message_content += part['text']
            elif 'functionCall' in part:
                # Gemini function call format
                func_call = part['functionCall']
                function_call = {
                    "name": func_call.get('name'),
                    "arguments": json.dumps(func_call.get('args', {}))
                }

        # Build OpenAI-compatible response
        message = {"role": "assistant"}
        if message_content:
            message["content"] = message_content
        if function_call:
            message["function_call"] = function_call

        openai_response = {
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": openai_finish_reason
            }],
            "model": self.model_name,
            "usage": gemini_response.get('usageMetadata', {})
        }

        return openai_response

    async def request(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request to Gemini API.

        Returns:
            Response in OpenAI format with 'choices' array
        """
        # Convert messages to Gemini format
        system_instruction, contents = self._convert_messages_to_gemini(messages)

        # Build Gemini request payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            }
        }

        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Add function declarations if provided
        if functions:
            gemini_functions = self._convert_functions_to_gemini(functions)
            if gemini_functions:
                payload["tools"] = [{
                    "functionDeclarations": gemini_functions
                }]

                # If function_call is specified, add tool config
                if function_call and function_call.get("name"):
                    payload["toolConfig"] = {
                        "functionCallingConfig": {
                            "mode": "ANY",
                            "allowedFunctionNames": [function_call["name"]]
                        }
                    }

        # Construct endpoint URL
        endpoint = f"{self.base_url}/models/{self.model_name}:generateContent?key={self.api_key}"

        # Calculate metrics
        try:
            messages_text = "\n".join([m.get('content', '') for m in messages if isinstance(m, dict)])
            chars = len(messages_text)
            est_tokens = max(1, int(chars / 4))
        except Exception:
            chars = 0
            est_tokens = 0

        logger.info(
            f"Gemini request -> model={self.model_name} messages={len(messages)} "
            f"chars={chars} est_tokens~{est_tokens} max_tokens={max_tokens or 'default'} "
            f"functions={len(functions) if functions else 0}"
        )
        logger.debug(f"Gemini payload: {json.dumps(payload, indent=2)}")

        # Retry logic for network issues
        max_attempts = 2
        backoff_seconds = 0.8

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    start_time = time.time()
                    response = await client.post(endpoint, json=payload)
                    duration = time.time() - start_time

                    response.raise_for_status()
                    gemini_response = response.json()

                    logger.debug(f"Gemini raw response: {json.dumps(gemini_response, indent=2)}")

                    # Convert to OpenAI format
                    openai_response = self._convert_gemini_response_to_openai(gemini_response)

                    # Log finish reason
                    try:
                        choices = openai_response.get('choices', [])
                        if choices:
                            finish_reason = choices[0].get('finish_reason')
                            logger.info(
                                f"Gemini response finish_reason={finish_reason} "
                                f"duration_s={duration:.2f} est_tokens_sent~{est_tokens}"
                            )
                            if finish_reason == 'length':
                                logger.warning(
                                    "Gemini response was truncated (finish_reason: 'length'). "
                                    "Consider reducing prompt size or increasing max_tokens."
                                )
                    except Exception:
                        pass

                    return openai_response

                except httpx.ReadTimeout:
                    logger.warning(f"Gemini request read timeout on attempt {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        await asyncio.sleep(backoff_seconds * attempt)
                        continue
                    logger.error(f"Gemini request timed out after {max_attempts} attempts")

                except httpx.HTTPStatusError as e:
                    error_body = e.response.text[:500]
                    logger.error(
                        f"Gemini API error: status={e.response.status_code} "
                        f"response={error_body}"
                    )
                    # Try to parse error message
                    try:
                        error_json = e.response.json()
                        error_msg = error_json.get('error', {}).get('message', error_body)
                        logger.error(f"Gemini error details: {error_msg}")
                    except Exception:
                        pass
                    return None

                except httpx.TimeoutException:
                    logger.warning(f"Gemini request timeout on attempt {attempt}/{max_attempts}")
                    if attempt < max_attempts:
                        await asyncio.sleep(backoff_seconds * attempt)
                        continue
                    logger.error(f"Gemini request timed out after {max_attempts} attempts")

                except httpx.RequestError as e:
                    logger.error(f"Gemini network error: {e}", exc_info=True)
                    return None

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode Gemini JSON response: {response.text[:500]}")
                    return None

                except Exception as e:
                    logger.error(f"Unexpected error during Gemini request: {e}", exc_info=True)
                    return None

        return None
