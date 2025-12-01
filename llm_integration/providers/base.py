# File: llm_integration/providers/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers must implement the request method.
    """

    def __init__(self, api_key: str, model_name: str, timeout: Optional[int] = None):
        """
        Initialize the provider.

        Args:
            api_key: API key for authentication
            model_name: Model identifier to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout or 120
        logger.info(f"{self.__class__.__name__} initialized with model '{model_name}'")

    @abstractmethod
    async def request(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request to the LLM API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 - 1.0)
            max_tokens: Maximum tokens to generate
            functions: Optional function definitions for function calling
            function_call: Optional function call directive

        Returns:
            Response dict in OpenAI-compatible format with 'choices' array
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'gemini')"""
        pass

    def supports_function_calling(self) -> bool:
        """Return whether this provider supports function calling"""
        return True
