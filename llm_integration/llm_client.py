# File: llm_integration/llm_client_new.py

import logging
import json
from typing import List, Dict, Any, Optional, TypedDict
from string import Template
import os
import re

from .providers import BaseLLMProvider, OpenAIProvider, GeminiProvider

logger = logging.getLogger(__name__)


# TypedDict definitions for structured LLM responses
class LLMClassification(TypedDict, total=False):
    Programming_Language: List[int]
    Experience_Level: List[int]
    Operating_System: List[int]
    Tool: List[int]
    Framework: List[int]


class LLMVerificationResponse(TypedDict):
    classification: Optional[LLMClassification]
    message_to_user: str
    is_complete: bool
    user_has_confirmed: Optional[bool]
    unassignable_skills: Optional[List[Dict[str, str]]]


class LLMClient:
    """
    LLM client with pluggable provider support.
    Supports OpenAI and Google Gemini with direct API calls.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model_name: str,
        user_verification_schema_path: str,
        role_categorization_schema_path: str,
        request_timeout_seconds: Optional[int] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize LLM client with a specific provider.

        Args:
            provider: Provider name ('openai' or 'gemini')
            api_key: API key for the provider
            model_name: Model identifier
            user_verification_schema_path: Path to user verification JSON schema
            role_categorization_schema_path: Path to role categorization JSON schema
            request_timeout_seconds: Request timeout in seconds
            base_url: Optional custom base URL (for OpenAI-compatible APIs)
        """
        self.provider_name = provider.lower()
        self.model_name = model_name

        # Initialize the appropriate provider
        if self.provider_name == 'openai':
            self.provider: BaseLLMProvider = OpenAIProvider(
                api_key=api_key,
                model_name=model_name,
                timeout=request_timeout_seconds,
                base_url=base_url
            )
        elif self.provider_name == 'gemini':
            self.provider: BaseLLMProvider = GeminiProvider(
                api_key=api_key,
                model_name=model_name,
                timeout=request_timeout_seconds
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}. Supported: openai, gemini")

        # Load schemas
        self.user_verification_schema = self._load_json_schema(user_verification_schema_path)
        self.role_categorization_schema = self._load_json_schema(role_categorization_schema_path)

        logger.info(
            f"LLMClient initialized with provider='{self.provider_name}' "
            f"model='{self.model_name}'"
        )

        # Metrics tracking
        self.metrics: Dict[str, Any] = {
            'calls': 0,
            'truncated_responses': 0,
            'total_estimated_prompt_tokens': 0,
            'total_chars_sent': 0,
            'last_call_duration_s': None,
        }

        # Configuration from environment
        try:
            self.default_max_tokens = int(os.getenv('DEFAULT_MAX_TOKENS', '6144'))
        except Exception:
            self.default_max_tokens = 6144

        try:
            self.welcome_temperature = float(os.getenv('WELCOME_TEMPERATURE', '0.7'))
        except Exception:
            self.welcome_temperature = 0.7

        self.welcome_hardcode = os.getenv('WELCOME_HARDCODE', 'false').lower() in ('1', 'true', 'yes')
        self.welcome_hardcode_message = os.getenv('WELCOME_HARDCODE_MESSAGE', '')

        try:
            self.welcome_max_prompt_chars = int(os.getenv('WELCOME_MAX_PROMPT_CHARS', '800'))
        except Exception:
            self.welcome_max_prompt_chars = 800

        try:
            self.welcome_max_response_tokens = int(os.getenv('WELCOME_MAX_RESPONSE_TOKENS', '1024'))
        except Exception:
            self.welcome_max_response_tokens = 1024

    def _load_json_schema(self, schema_path: str) -> Optional[Dict[str, Any]]:
        """Load a JSON schema file."""
        try:
            with open(schema_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"JSON schema file not found at {schema_path}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {schema_path}")
        return None

    async def _make_llm_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
        functions: Optional[List[Dict[str, Any]]] = None,
        function_call: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make a request through the configured provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            functions: Optional function definitions
            function_call: Optional function call directive

        Returns:
            Response dict in OpenAI-compatible format
        """
        # Update metrics
        try:
            messages_text = "\n".join([m.get('content', '') for m in messages if isinstance(m, dict)])
            chars = len(messages_text)
            est_tokens = max(1, int(chars / 4))
            self.metrics['calls'] += 1
            self.metrics['total_estimated_prompt_tokens'] += est_tokens
            self.metrics['total_chars_sent'] += chars
        except Exception:
            pass

        # Make request through provider
        response = await self.provider.request(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or self.default_max_tokens,
            functions=functions,
            function_call=function_call
        )

        if response:
            # Check for truncation
            try:
                choices = response.get('choices', [])
                if choices and isinstance(choices, list):
                    finish_reason = choices[0].get('finish_reason')
                    if finish_reason == 'length':
                        self.metrics['truncated_responses'] += 1
            except Exception:
                pass

        return response

    async def generate_new_user_summary(
        self,
        conversation_history_text: str,
        assigned_roles_names_str: str,
        summary_prompt_template: str,
        conversation_language: str = "English",
        max_response_tokens: Optional[int] = None
    ) -> Optional[str]:
        """Generate a summary of a new user's verification conversation."""
        logger.info(f"Generating new user summary. Language: {conversation_language}")

        try:
            template = Template(summary_prompt_template)
            formatted_prompt = template.substitute(
                language=conversation_language,
                conversation_history=conversation_history_text,
                assigned_roles_names_list=assigned_roles_names_str
            )
        except KeyError as e:
            logger.error(f"KeyError during summary prompt formatting: {e.args[0]}", exc_info=True)
            return "Error: Could not generate summary due to a prompt formatting issue."
        except Exception as e:
            logger.error(f"Unexpected error formatting summary prompt: {e}", exc_info=True)
            return "Error: Could not generate summary due to an unexpected prompt issue."

        messages = [{"role": "system", "content": formatted_prompt}]

        request_max_tokens = int(max_response_tokens) if max_response_tokens is not None else 800
        request_max_tokens = min(request_max_tokens, self.default_max_tokens)

        llm_response_data = await self._make_llm_request(
            messages, temperature=0.6, max_tokens=request_max_tokens
        )

        if llm_response_data:
            try:
                # Extract content from OpenAI-format response
                response_content_str = self._extract_content(llm_response_data)
                if response_content_str is not None:
                    return response_content_str.strip()
                else:
                    logger.warning(f"LLM response for summary was None. Data: {llm_response_data}")
            except Exception as e:
                logger.error(f"Error processing LLM response for summary: {e}", exc_info=True)

        logger.warning("Failed to generate new user summary from LLM, returning None.")
        return None

    def _extract_content(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Extract text content from OpenAI-format response."""
        try:
            choices = response_data.get('choices', [])
            if choices and isinstance(choices, list) and len(choices) > 0:
                message = choices[0].get('message', {})
                if isinstance(message, dict):
                    return message.get('content')
        except Exception:
            pass
        return None

    async def classify_user_for_suspicion(
        self,
        user_messages: str,
        analysis_prompt_template: str,
        max_response_tokens: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run an LLM analysis to detect suspicious user behavior.

        Returns:
            Dict with {"is_suspicious": bool, "reason": str}
        """
        if not analysis_prompt_template:
            logger.error("No analysis prompt template provided for suspicious classification.")
            return None

        # Prepare system prompt
        try:
            if '{messages}' in analysis_prompt_template:
                system_prompt = analysis_prompt_template.replace('{messages}', '{messages}')
            else:
                try:
                    tmpl = Template(analysis_prompt_template)
                    system_prompt = tmpl.safe_substitute(messages='{messages}')
                except Exception:
                    system_prompt = "Please analyze the following user messages for spam, bot-like behavior, or nonsensical content:"
        except Exception as e:
            logger.error(f"Failed to prepare analysis prompt template: {e}", exc_info=True)
            system_prompt = "Please analyze the following user messages for spam, bot-like behavior, or nonsensical content:"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_messages}
        ]

        request_max_tokens = int(max_response_tokens) if max_response_tokens is not None else 200
        request_max_tokens = min(request_max_tokens, self.default_max_tokens)

        # Load suspicious classification schema
        functions_payload = None
        try:
            with open('llm_integration/schemas/suspicious_classification.json', 'r', encoding='utf-8') as sf:
                functions_payload = [json.load(sf)]
        except Exception:
            functions_payload = None

        # Make LLM call
        if functions_payload:
            llm_response = await self._make_llm_request(
                messages, temperature=0.0, max_tokens=request_max_tokens,
                functions=functions_payload, function_call={"name": "classify_user"}
            )
        else:
            llm_response = await self._make_llm_request(
                messages, temperature=0.0, max_tokens=request_max_tokens
            )

        if not llm_response:
            logger.warning("LLM classify_user_for_suspicion returned no response data.")
            return None

        # Parse function-calling style responses
        try:
            choice = llm_response.get("choices", [{}])[0]
            message_obj = choice.get("message", {})

            if message_obj.get("function_call"):
                args = message_obj["function_call"].get("arguments", "{}")
                try:
                    parsed = json.loads(args)
                    logger.info(f"Suspicious classification parsed: {list(parsed.keys())}")
                    return parsed
                except json.JSONDecodeError:
                    logger.warning("function_call.arguments not valid JSON")
                    return {"is_suspicious": False, "reason": args[:800]}

            # Otherwise, look for content
            content = self._extract_content(llm_response) or ""

            # Try to parse as JSON
            try:
                parsed = json.loads(content)
                logger.info(f"Suspicious classification parsed from content: {list(parsed.keys())}")
                return parsed
            except Exception:
                # Fallback heuristic
                lower = content.lower()
                is_suspicious = any(k in lower for k in ("spam", "bot", "nonsense", "scam", "phishing", "malicious"))
                return {"is_suspicious": is_suspicious, "reason": content[:800]}

        except Exception as e:
            logger.error(f"Error processing suspicion classification response: {e}", exc_info=True)

        return None

    async def categorize_server_roles(
        self,
        roles_data: List[Dict[str, Any]],
        categorization_prompt: str
    ) -> Dict[str, List[int]]:
        """
        Call the LLM to categorize server roles.

        Returns:
            Dict mapping category names to lists of role IDs
        """
        logger.info(f"Attempting to categorize {len(roles_data)} roles with LLM.")

        roles_list_str = "\n".join([f"- {role['name']} (ID: {role['id']})" for role in roles_data])
        formatted_prompt = f"{categorization_prompt}\n\nHere is the list of roles to categorize:\n{roles_list_str}"

        messages = [{"role": "system", "content": formatted_prompt}]

        if not self.role_categorization_schema:
            logger.error("Role categorization schema not loaded. Aborting categorization.")
            return {}

        llm_response_data = await self._make_llm_request(
            messages,
            temperature=0.1,
            max_tokens=self.default_max_tokens,
            functions=[self.role_categorization_schema],
            function_call={"name": "categorize_server_roles"}
        )

        categorized_role_ids: Dict[str, List[int]] = {}

        if llm_response_data:
            try:
                choice = llm_response_data.get("choices", [{}])[0]
                message = choice.get("message", {})
                function_call = message.get("function_call")

                if function_call and function_call.get("name") == "categorize_server_roles":
                    arguments_str = function_call.get("arguments", "{}")
                    parsed_categories_by_name = json.loads(arguments_str)
                    role_name_to_id_map = {role['name'].lower(): role['id'] for role in roles_data}

                    for category, role_names in parsed_categories_by_name.items():
                        if not isinstance(role_names, list):
                            logger.warning(f"LLM returned non-list for category '{category}'")
                            continue

                        ids_for_category = []
                        for name in role_names:
                            if not isinstance(name, str):
                                logger.warning(f"LLM returned non-string role name in '{category}'")
                                continue

                            role_id = role_name_to_id_map.get(name.lower())
                            if role_id:
                                ids_for_category.append(role_id)
                            else:
                                logger.warning(f"Role name '{name}' in category '{category}' not found")

                        if ids_for_category:
                            categorized_role_ids[category] = ids_for_category

                    logger.info(f"Successfully categorized roles: {categorized_role_ids}")

                    # Post-process: ensure every role is in exactly one category
                    role_id_to_name = {role['id']: role['name'] for role in roles_data}
                    all_role_ids = set(role_id_to_name.keys())
                    assigned_ids = set()
                    for ids in categorized_role_ids.values():
                        assigned_ids.update(ids)

                    unassigned_ids = sorted(list(all_role_ids - assigned_ids))
                    if unassigned_ids:
                        categorized_role_ids.setdefault('Other', [])
                        for uid in unassigned_ids:
                            categorized_role_ids['Other'].append(uid)
                        other_names = [role_id_to_name.get(uid, str(uid)) for uid in unassigned_ids]
                        logger.info(f"Added {len(unassigned_ids)} roles to 'Other' category: {other_names}")
                else:
                    logger.error(f"Could not find function call in LLM response: {llm_response_data}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM function call: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error processing LLM response for role categorization: {e}", exc_info=True)

        if not categorized_role_ids:
            logger.warning("Role categorization failed or returned no data.")

        return categorized_role_ids

    async def get_verification_guidance(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        categorized_server_roles: Dict[str, List[int]],
        available_roles_map: Dict[int, str],
        verification_prompt_template: str,
        max_response_tokens: Optional[int] = None,
        preferred_locale: Optional[str] = None,
    ) -> Optional[LLMVerificationResponse]:
        """
        Get LLM guidance for user verification.

        Returns:
            Structured verification response with classification and message
        """
        logger.info(f"Getting verification guidance from LLM for user message: '{user_message}'")

        # Build available roles text (names only to reduce tokens)
        available_roles_text_parts = []
        for category, role_ids in categorized_server_roles.items():
            role_names_in_category = [
                f"'{available_roles_map.get(rid, str(rid))}'"
                for rid in role_ids if rid in available_roles_map
            ]
            if role_names_in_category:
                available_roles_text_parts.append(f"- {category}: {', '.join(role_names_in_category)}")

        available_roles_text_list = "\n".join(available_roles_text_parts)
        if not available_roles_text_list:
            available_roles_text_list = "No specific skill/experience/OS roles are currently defined for classification."
        # Cap available roles text to keep prompt small
        available_roles_text_list = self._smart_trim(available_roles_text_list, 4000)

        # Format system prompt
        try:
            template = Template(verification_prompt_template)
            system_prompt_content = template.safe_substitute(
                available_roles_text_list=available_roles_text_list,
                preferred_locale=preferred_locale or "unspecified"
            )
        except KeyError as e:
            logger.error(f"KeyError during template substitution: {e.args[0]}", exc_info=True)
            return {
                "classification": None,
                "message_to_user": "Prompt error.",
                "is_complete": False,
                "user_has_confirmed": False,
                "unassignable_skills": None
            }
        except ValueError as e:
            logger.error(f"ValueError during template substitution: {e}", exc_info=True)
            return {
                "classification": None,
                "message_to_user": "Prompt syntax error.",
                "is_complete": False,
                "user_has_confirmed": False,
                "unassignable_skills": None
            }

        messages = [{"role": "system", "content": system_prompt_content}]
        # Trim history content to avoid large prompts
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": self._trim_message(msg.get("content", ""), 1200)
            })

        messages.append({"role": "user", "content": self._trim_message(user_message, 1200)})

        if not self.user_verification_schema:
            logger.error("User verification schema not loaded. Aborting guidance.")
            return None

        # Use the higher of configured max_response_tokens and default_max_tokens to reduce truncation risk
        effective_max_tokens = max(max_response_tokens or 0, self.default_max_tokens)

        llm_response_data = await self._make_llm_request(
            messages,
            temperature=0.3,
            max_tokens=effective_max_tokens,
            functions=[self.user_verification_schema],
            function_call={"name": "propose_user_roles"}
        )

        if llm_response_data:
            try:
                choice = llm_response_data.get("choices", [{}])[0]

                if choice.get("finish_reason") == "length":
                    logger.warning("LLM response was truncated (finish_reason: 'length').")

                message = choice.get("message", {})
                function_call = message.get("function_call")

                if function_call and function_call.get("name") == "propose_user_roles":
                    arguments_str = function_call.get("arguments", "{}")
                    parsed_response = json.loads(arguments_str)

                    # Validate required fields
                    if all(key in parsed_response for key in ["message_to_user", "is_complete"]) and \
                       isinstance(parsed_response.get("user_has_confirmed"), bool):

                        # Validate classification (names, not IDs)
                        if "classification" in parsed_response and parsed_response["classification"] is not None:
                            if not isinstance(parsed_response["classification"], dict):
                                logger.error("LLM 'classification' field is not a dictionary.")
                                parsed_response["classification"] = None
                            else:
                                for category_key in list(parsed_response["classification"].keys()):
                                    if isinstance(parsed_response["classification"][category_key], list):
                                        valid_names = []
                                        for name in parsed_response["classification"][category_key]:
                                            if isinstance(name, str) and name.strip():
                                                valid_names.append(name.strip())
                                        parsed_response["classification"][category_key] = valid_names
                                    else:
                                        logger.error(f"LLM 'classification' for {category_key} is not a list.")
                                        parsed_response["classification"][category_key] = []

                        logger.info("Successfully parsed verification guidance from LLM.")
                        return parsed_response
                    else:
                        logger.error(f"LLM JSON response missing required keys. Parsed: {parsed_response}")
                else:
                    logger.error(f"Could not find function call in LLM response: {llm_response_data}")

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM function call: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error processing LLM response for verification: {e}", exc_info=True)

        logger.warning("Using fallback response for verification guidance.")
        fallback_response: LLMVerificationResponse = {
            "classification": None,
            "message_to_user": "I'm currently having trouble processing information. Please try again in a few moments.",
            "is_complete": False,
            "user_has_confirmed": False,
            "unassignable_skills": None
        }
        return fallback_response

    async def get_additional_role_suggestions(
        self,
        conversation_text: str,
        available_roles_map: Dict[int, str],
        already_assigned_role_ids: List[int],
        max_suggestions: int = 3,
        max_response_tokens: Optional[int] = None,
        preferred_locale: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Suggest nearby/related roles (Markdown message + role names)."""

        # Build list of candidate roles (exclude already assigned)
        candidate_roles = {
            rid: name for rid, name in available_roles_map.items() if rid not in set(already_assigned_role_ids or [])
        }
        if not candidate_roles:
            logger.debug("No candidate roles available for additional suggestions.")
            return None

        roles_text = "\n".join([f"- {name}" for _, name in candidate_roles.items()])

        trimmed_conversation = self._smart_trim(conversation_text or "", 1800)

        system_prompt = (
            "You are assisting with role assignment follow-up.\n"
            "You will propose up to {max_suggestions} additional Discord roles that might fit the user based on conversation context.\n"
            "Rules:\n"
            "- Only choose role IDs from the provided list (and ONLY those).\n"
            "- Prefer close or related matches (e.g., suggest 'Virtualization' for 'Proxmox').\n"
            "- Do NOT include roles already assigned (IDs provided).\n"
            "- If nothing fits, return an empty list.\n"
            "- Respond in the user's preferred locale if provided; otherwise match conversation language, fallback to Spanish (Mexico).\n"
            "- The response MUST be JSON with keys: message_markdown (string) and suggested_role_names (array of strings).\n"
            "- message_markdown: short intro + a brief confirmation line telling the user to confirm if they want these roles; do not include IDs.\n"
            "Available roles (names only):\n{roles_text}\n"
            "Already assigned role IDs: {assigned_ids}\n"
        ).format(max_suggestions=max_suggestions, roles_text=roles_text, assigned_ids=list(already_assigned_role_ids or []))

        user_prompt = (
            "Conversation summary/context to base suggestions on:\n" + (trimmed_conversation or "(no conversation text)") +
            (f"\nPreferred locale: {preferred_locale}" if preferred_locale else "")
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        llm_response = await self._make_llm_request(
            messages,
            temperature=0.4,
            max_tokens=(max_response_tokens or self.default_max_tokens),
        )

        if not llm_response:
            return None

        try:
            content = self._extract_content(llm_response)
            parsed = None
            if isinstance(content, str):
                stripped = self._strip_code_fences(content)
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    logger.debug("Could not parse additional-role suggestions as JSON.")

            if not isinstance(parsed, dict):
                return None

            message_md = parsed.get("message_markdown") or parsed.get("message")
            suggested_names_raw = parsed.get("suggested_role_names") or parsed.get("suggested_roles") or []
            suggested_names: List[str] = []
            for nm in suggested_names_raw:
                if isinstance(nm, str) and nm.strip():
                    suggested_names.append(nm.strip())

            return {
                "message_markdown": message_md,
                "suggested_role_names": list(dict.fromkeys(suggested_names)),  # dedupe, preserve order
            }
        except Exception as e:
            logger.error(f"Error parsing additional role suggestions: {e}", exc_info=True)
            return None

    async def generate_welcome_message(
        self,
        member_name: str,
        server_name: str,
        member_id: int,
        welcome_prompt_template_str: str
    ) -> dict:
        """
        Generate welcome message as embed data (title, description, color).

        Returns:
            Dict with 'title', 'description', and 'color' keys
        """
        logger.info(f"Generating welcome message for '{member_name}' in '{server_name}'")

        # Substitute template variables
        try:
            tmpl = Template(welcome_prompt_template_str)
            system_message_content = tmpl.safe_substitute(
                server_name=server_name,
                member_name=member_name,
                member_id=member_id
            )
        except Exception as e:
            logger.error(f"Error formatting welcome prompt template: {e}", exc_info=True)
            system_message_content = (
                "Eres un asistente amigable. Genera contenido JSON para un embed de Discord de bienvenida. "
                f"Incluye title, description mencionando <@{member_id}>, y color. Responde en español."
            )

        # Ensure Spanish output
        if 'español' not in system_message_content.lower() and 'spanish' not in system_message_content.lower():
            system_message_content = "Responde en español.\n\n" + system_message_content

        # User message for generating embed
        user_message_content = (
            f"Un nuevo usuario llamado '{member_name}' (ID: {member_id}) se ha unido al servidor. "
            f"Genera contenido para un embed de Discord de bienvenida:\n"
            f"1. title: Un título breve y amistoso (máximo 50 caracteres)\n"
            f"2. description: Mensaje de bienvenida mencionando EXACTAMENTE <@{member_id}> (máximo 300 caracteres)\n"
            f"3. color: Un color hex apropiado (ej: #3498DB)\n"
            f"Responde en español con un objeto JSON válido."
        ).format(member_id=member_id)

        # Cap message size
        if len(user_message_content) > 800:
            user_message_content = user_message_content[:800]

        # Smart trim system prompt
        normalized_system = re.sub(r"\s+", " ", system_message_content).strip()
        final_system = self._smart_trim(normalized_system, self.welcome_max_prompt_chars)

        messages = [
            {"role": "system", "content": final_system},
            {"role": "user", "content": user_message_content}
        ]

        # Fallback embed
        fallback_embed = {
            "title": f"¡Bienvenido a {server_name}!",
            "description": f"¡Hola <@{member_id}>! Estamos encantados de tenerte aquí. Ejecuta `/assign-roles` para verificar tu cuenta y recibir roles apropiados.",
            "color": 0x3498DB
        }
        if self.welcome_hardcode_message:
            fallback_embed["description"] = self.welcome_hardcode_message

        # Return hardcoded message if configured
        if self.welcome_hardcode:
            logger.info("Using hardcoded welcome message (WELCOME_HARDCODE=true)")
            return fallback_embed

        # Make LLM request
        llm_response_data = await self._make_llm_request(
            messages,
            temperature=self.welcome_temperature,
            max_tokens=self.welcome_max_response_tokens
        )

        # Retry on truncation with no content
        try:
            if llm_response_data and isinstance(llm_response_data.get('choices'), list) and llm_response_data['choices']:
                choice0 = llm_response_data['choices'][0]
                finish_reason = choice0.get('finish_reason')
                content_here = choice0.get('message', {}).get('content')

                if finish_reason == 'length' and not content_here:
                    retry_tokens = min(
                        self.default_max_tokens,
                        max(self.welcome_max_response_tokens * 3, self.welcome_max_response_tokens + 400)
                    )
                    if retry_tokens > self.welcome_max_response_tokens:
                        logger.warning(f"Welcome truncated and empty. Retrying with max_tokens={retry_tokens}")
                        llm_response_retry = await self._make_llm_request(
                            messages, temperature=self.welcome_temperature, max_tokens=retry_tokens
                        )
                        if llm_response_retry:
                            llm_response_data = llm_response_retry
        except Exception:
            pass

        if llm_response_data:
            embed_data = self._parse_welcome_response(llm_response_data, member_id, server_name)
            if embed_data:
                logger.info("Welcome embed generated by LLM.")
                return embed_data

        logger.warning("Failed to generate LLM welcome embed, using fallback.")
        return fallback_embed

    async def generate_initial_verification_message(
        self,
        member_name: str,
        server_name: str,
        preferred_locale: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a short, localized greeting to start DM verification."""
        try:
            locale_hint = preferred_locale or ""
            system_prompt = (
                "You are a friendly Discord bot helping with role verification. "
                "Greet the user briefly and ask them to describe their skills (programming languages, experience, operating systems, tools). "
                "Respond in the user's preferred locale if provided; otherwise match the language in your reply to the user name. "
                "Keep it concise (<= 80 words)."
            )

            user_prompt = (
                f"User: {member_name} on server {server_name}. Preferred locale: {locale_hint}."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            llm_response_data = await self._make_llm_request(
                messages,
                temperature=0.4,
                max_tokens=320,
            )

            if llm_response_data:
                content = self._extract_content(llm_response_data)
                if isinstance(content, str):
                    return content.strip()
        except Exception as e:
            logger.error(f"Error generating initial verification message: {e}", exc_info=True)

        return None

    def _smart_trim(self, text: str, max_chars: int) -> str:
        """Smart trim: keep head and tail to preserve context."""
        if not text or len(text) <= max_chars:
            return text

        marker = "\n\n...[truncated to avoid exceeding token limit]...\n\n"
        reserve = len(marker)

        if max_chars <= reserve + 20:
            return text[:max_chars]

        head_chars = int((max_chars - reserve) * 0.6)
        tail_chars = max_chars - reserve - head_chars
        head = text[:head_chars].rstrip()
        tail = text[-tail_chars:].lstrip()

        return head + marker + tail

    def _trim_message(self, content: Any, max_chars: int = 1200) -> Any:
        """Trim message content to avoid oversized prompts."""
        if isinstance(content, str) and len(content) > max_chars:
            return self._smart_trim(content, max_chars)
        return content

    def _strip_code_fences(self, text: str) -> str:
        """Remove Markdown code fences from a string if present."""
        if not isinstance(text, str):
            return text

        fenced = re.match(r"^```(?:[a-zA-Z0-9]+)?\n(.*)\n```$", text.strip(), re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        return text.strip()

    def _parse_welcome_response(
        self,
        response_data: Dict[str, Any],
        member_id: int,
        server_name: str
    ) -> Optional[Dict[str, Any]]:
        """Parse LLM response for welcome embed data."""
        try:
            response_content_str = self._extract_content(response_data)

            if response_content_str and isinstance(response_content_str, str):
                stripped = self._strip_code_fences(response_content_str)

                # Try parsing as JSON
                try:
                    parsed_json = json.loads(stripped)
                    if isinstance(parsed_json, dict) and ("title" in parsed_json or "description" in parsed_json):
                        description = parsed_json.get("description", f"¡Hola <@{member_id}>!")

                        # Fix malformed mentions
                        if f"<@{member_id}>" not in description and str(member_id) in description:
                            description = description.replace(str(member_id), f"<@{member_id}>")

                        return {
                            "title": parsed_json.get("title", f"¡Bienvenido a {server_name}!"),
                            "description": description,
                            "color": self._parse_color(parsed_json.get("color", "#3498DB"))
                        }
                except json.JSONDecodeError:
                    # Treat as plain text
                    if stripped:
                        if f"<@{member_id}>" not in stripped and str(member_id) in stripped:
                            stripped = stripped.replace(str(member_id), f"<@{member_id}>")

                        return {
                            "title": f"¡Bienvenido a {server_name}!",
                            "description": stripped[:2000],
                            "color": 0x3498DB
                        }

            # Check for function call
            choice = response_data.get('choices', [{}])[0]
            func = choice.get('message', {}).get('function_call')
            if func and 'arguments' in func:
                args_str = func.get('arguments', '')
                try:
                    parsed_args = json.loads(args_str)
                    if isinstance(parsed_args, dict):
                        description = parsed_args.get("description", f"¡Hola <@{member_id}>!")
                        if f"<@{member_id}>" not in description and str(member_id) in description:
                            description = description.replace(str(member_id), f"<@{member_id}>")

                        return {
                            "title": parsed_args.get("title", f"¡Bienvenido a {server_name}!"),
                            "description": description,
                            "color": self._parse_color(parsed_args.get("color", "#3498DB"))
                        }
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            logger.error(f"Error parsing welcome response: {e}", exc_info=True)

        return None

    def _parse_color(self, color_input) -> int:
        """Parse color from hex string or return default blue."""
        try:
            if isinstance(color_input, str):
                color_str = color_input.lstrip('#')
                return int(color_str, 16)
            elif isinstance(color_input, int):
                return color_input
        except (ValueError, TypeError):
            pass
        return 0x3498DB  # Default blue
