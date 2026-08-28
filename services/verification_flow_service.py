# File: services/verification_flow_service.py

import logging
import discord
from discord.ext import commands
import asyncio
from typing import Optional, List, Dict, Any, TypedDict, Tuple
from unicodedata import normalize

from utils.i18n import CommonMessages, locale_to_flag

# ... (TypedDict definitions remain the same) ...
class LLMClassification(TypedDict, total=False):
    Programming_Language: List[str]
    Experience_Level: List[str]
    Operating_System: List[str]

class LLMVerificationResponse(TypedDict):
    classification: Optional[LLMClassification]
    message_to_user: str
    is_complete: bool
    user_has_confirmed: Optional[bool]
    unassignable_skills: Optional[List[Dict[str, str]]]


logger = logging.getLogger(__name__)

class VerificationFlowService:
    def __init__(self, bot: commands.Bot, llm_client, settings):
        self.bot = bot
        self.llm_client = llm_client
        self.settings = settings
        self.active_verifications: Dict[int, Dict[str, Any]] = {}
        self.db_service = getattr(bot, "db_service", None) 
        self._role_name_to_id_cache: Dict[str, int] = {}

    def _system_role_ids(self) -> List[int]:
        """Role IDs managed by workflow (not suggested/assigned as skills)."""
        ids: List[int] = []
        for attr in [
            "VERIFIED_ROLE_ID",
            "UNVERIFIED_ROLE_ID",
            "VERIFICATION_IN_PROGRESS_ROLE_ID",
            "SUSPICIOUS_ROLE_ID",
        ]:
            val = getattr(self.settings, attr, None)
            if isinstance(val, int):
                ids.append(val)
        return ids

    def _build_role_name_lookup(self) -> None:
        """Build lowercase name -> role_id map from server_roles_map for quick lookup."""
        self._role_name_to_id_cache = {}
        try:
            for rid, name in getattr(self.bot, 'server_roles_map', {}).items():
                if isinstance(name, str):
                    self._role_name_to_id_cache[name.lower()] = rid
        except Exception:
            self._role_name_to_id_cache = {}

    def _map_role_names_to_ids(self, role_names: List[str]) -> List[int]:
        if not self._role_name_to_id_cache:
            self._build_role_name_lookup()
        mapped: List[int] = []
        for name in role_names or []:
            if not isinstance(name, str):
                continue
            rid = self._role_name_to_id_cache.get(name.lower())
            if rid:
                mapped.append(rid)
        return mapped

    def _get_member_current_manageable_roles_text(self, member: discord.Member) -> Tuple[str, List[int]]:
        """
        Gets a text list of the member's current roles that are manageable by the bot,
        and a list of their IDs.
        """
        if not self.bot.categorized_server_roles or not self.bot.server_roles_map:
            return "Could not retrieve current roles information.", []

        all_manageable_role_ids = set()
        for cat_role_ids in self.bot.categorized_server_roles.values():
            all_manageable_role_ids.update(cat_role_ids)

        member_manageable_role_names = []
        member_manageable_role_ids = []

        for role in member.roles:
            if role.id in all_manageable_role_ids and role.id in self.bot.server_roles_map:
                member_manageable_role_names.append(self.bot.server_roles_map[role.id])
                member_manageable_role_ids.append(role.id)
        
        if not member_manageable_role_names:
            return "You don't seem to have any skill/experience/OS roles assigned by me yet.", []
        
        return f"I see you currently have the following roles related to skills/experience/OS: {', '.join(member_manageable_role_names)}.", member_manageable_role_ids


    async def start_verification_process(self, member: discord.Member, interaction: Optional[discord.Interaction] = None, locale: Optional[str] = None):
        logger.info(
            f"SVC_START: Attempting to start/update verification for: {member.name} (ID: {member.id}) locale={locale}"
        )

        # Normalize locale (discord.Locale enums have .value)
        if locale is not None and hasattr(locale, "value"):
            locale = str(locale.value)

        # If no locale passed, try to load stored preference
        if not locale and self.db_service:
            try:
                stored_locale = await self.db_service.get_user_locale(member.id)
                if stored_locale:
                    locale = stored_locale
                    logger.debug(f"SVC_START: Loaded stored locale {locale} for {member.name}")
            except Exception as e:
                logger.error(f"SVC_START: Failed to fetch stored locale for {member.name}: {e}")

        if member.bot:
            logger.info(f"SVC_START: Member {member.name} is a bot, skipping verification.")
            if interaction:
                 # Use followup
                 await interaction.followup.send("Bots do not require verification.", ephemeral=True)
            return

        verified_role = member.guild.get_role(self.settings.VERIFIED_ROLE_ID)
        if verified_role and verified_role in member.roles:
            logger.info(f"SVC_START: User {member.name} is already verified. Proceeding as update session if from /assign-roles.")
        
        if member.id in self.active_verifications:
            logger.info(f"SVC_START: Verification process already active for {member.name}.")
            msg_content = f"A verification process is already underway for you, {member.mention}. Please check your DMs."
            if interaction:
                # Use followup
                await interaction.followup.send(msg_content, ephemeral=True)
            else:
                try: await member.send(msg_content)
                except discord.Forbidden: logger.warning(f"SVC_START: Cannot send DM to {member.name} (already active).")
            return
        
        is_update_session = False
        if verified_role and verified_role in member.roles:
            is_update_session = True
        
        _, current_manageable_role_ids_for_user = self._get_member_current_manageable_roles_text(member)
        if current_manageable_role_ids_for_user:
            is_update_session = True
        
        self.active_verifications[member.id] = {
            'retries_left': self.settings.VERIFICATION_RETRIES,
            'conversation_history': [], 
            'last_proposed_classification': None,
            'is_update_session': is_update_session,
            'initial_manageable_role_ids': current_manageable_role_ids_for_user,
            'preferred_locale': locale
        }
        user_state = self.active_verifications[member.id]

        inprogress_role = member.guild.get_role(self.settings.VERIFICATION_IN_PROGRESS_ROLE_ID)
        if inprogress_role:
            try:
                if inprogress_role not in member.roles:
                    await member.add_roles(inprogress_role, reason="Verification process started/updated")
                logger.info(f"SVC_START: Ensured '{inprogress_role.name}' on {member.name}")
            except discord.Forbidden: logger.error(f"SVC_START: Missing permissions to add '{inprogress_role.name}' to {member.name}")
            except discord.HTTPException as e: logger.error(f"SVC_START: Failed to add '{inprogress_role.name}' to {member.name}: {e}")
        else:
            logger.error(f"SVC_START: Role ID 'verificationinprogress' ({self.settings.VERIFICATION_IN_PROGRESS_ROLE_ID}) not found.")
            if interaction:
                 # Use followup
                 await interaction.followup.send("Error: System misconfig (inprogress role). Contact admin.", ephemeral=True)
            self.active_verifications.pop(member.id, None)
            return

        locale_lower = (locale or "").lower()
        user_language = (locale_lower.split("-")[0] if locale_lower else "en") or "en"
        logger.debug(f"SVC_START: Using preferred_language={user_language} for {member.name} (locale={locale})")
        flag = locale_to_flag(locale)

        initial_dm_message = None
        # Try LLM-generated localized greeting first
        if self.llm_client:
            try:
                initial_dm_message = await self.llm_client.generate_initial_verification_message(
                    member_name=member.name,
                    server_name=member.guild.name,
                    preferred_locale=locale,
                )
            except Exception as e:
                logger.error(f"SVC_START: Failed to generate initial DM via LLM for {member.name}: {e}")

        # Fallback messages if LLM fails
        if not initial_dm_message:
            if user_language == "es":
                initial_dm_message = (
                    f"{flag} ¡Hola {member.mention}! Continuaremos en español. Cuéntame sobre tus habilidades (lenguajes, experiencia, sistemas operativos, herramientas)."
                )
            elif user_language == "en":
                initial_dm_message = (
                    f"{flag} Hello {member.mention}! I'll continue in English. Tell me about your skills (programming languages, experience level, operating systems, tools)."
                )
            else:
                initial_dm_message = (
                    f"{flag} I will continue in your preferred language ({user_language})."
                    f" Please tell me about your skills (programming languages, experience level, operating systems, tools)."
                    f" If this looks wrong, reply in your language and I'll follow it."
                )

        # Seed conversation with a system note so the LLM respects language preference
        user_state['conversation_history'].append({
            'role': 'system',
            'content': f"[Preferred language: {user_language} (locale={locale or 'unknown'})]"
        })

        # Persist locale preference for future interactions
        if self.db_service and locale:
            try:
                await self.db_service.upsert_user_locale(member.id, locale)
            except Exception as e:
                logger.error(f"SVC_START: Failed to persist locale {locale} for {member.name}: {e}")
        
        dm_channel = None
        try:
            dm_channel = await member.create_dm()
            await dm_channel.send(initial_dm_message)
            user_state['conversation_history'].append({'role': 'assistant', 'content': initial_dm_message})

            if interaction:
                await interaction.followup.send(f"I've sent you a DM to start/update your role verification, {member.mention}!", ephemeral=True)

            # Run the DM conversation loop as a background task so callers return immediately
            asyncio.ensure_future(self._handle_dm_conversation(member, dm_channel))
            return True
        except discord.Forbidden:
            logger.warning(f"SVC_START: Cannot send initial DM to {member.name}. User might have DMs disabled.")
            if interaction:
                from utils.i18n import CommonMessages
                await interaction.followup.send(f"{member.mention}, {CommonMessages.DM_DISABLED}", ephemeral=True)
            await self._conclude_verification(member, success=False, reason="Failed to send DM (DMs possibly disabled).")
            return False
        except Exception as e:
            logger.error(f"SVC_START: Error starting/updating verification for {member.name}: {e}", exc_info=True)
            if interaction:
                from utils.i18n import CommonMessages
                await interaction.followup.send(CommonMessages.ERROR_GENERIC, ephemeral=True)
            await self._conclude_verification(member, success=False, reason="Internal error during verification initiation.")
            return False

    # ... (the rest of the file remains unchanged) ...
    async def _handle_dm_conversation(self, member: discord.Member, dm_channel: discord.DMChannel):
        user_state = self.active_verifications.get(member.id)
        if not user_state:
            logger.error(f"DM_HANDLER: Called for {member.name} but no active state found.")
            return
        
        verification_prompt_template = ""
        try:
            with open(self.settings.PROMPT_PATH_USER_VERIFICATION_SYSTEM_TEMPLATE, "r", encoding="utf-8") as f:
                verification_prompt_template = f.read().strip()
        except Exception as e:
            logger.error(f"DM_HANDLER: Failed to load user verification prompt: {e}", exc_info=True)
            if dm_channel: await dm_channel.send("I'm having trouble accessing my instructions. Please contact an admin.")
            await self._conclude_verification(member, success=False, reason="System error: Missing verification prompt.")
            return

        if not self.bot.categorized_server_roles or not self.bot.server_roles_map:
             logger.error("DM_HANDLER: Categorized server roles or roles map not available.")
             if dm_channel: await dm_channel.send("The server's role information isn't ready yet. Please try `/assign-roles` again in a few minutes, or contact an admin.")
             await self._conclude_verification(member, success=False, reason="System error: Role data not ready.")
             return

        is_first_substantive_user_reply = (len(user_state['conversation_history']) == 1 and 
                                           user_state['conversation_history'][0]['role'] == 'assistant')

        while user_state.get('retries_left', 0) > 0:
            try:
                logger.debug(f"DM_HANDLER: Waiting for DM from {member.name}. Retries left: {user_state['retries_left']}")
                user_response_message = await self.bot.wait_for(
                    'message',
                    timeout=900.0, 
                    check=lambda m: m.author.id == member.id and m.channel.id == dm_channel.id and not m.is_system() and m.content is not None and m.content.strip() != ""
                )
                user_input = user_response_message.content.strip()
                logger.debug(f"DM_HANDLER: Received DM from {member.name}: '{user_input}'")
                
                if member.id not in self.active_verifications: return 
                
                llm_turn_user_content = user_input 
                
                history_for_llm_call = list(user_state['conversation_history'])

                if is_first_substantive_user_reply and user_state.get('is_update_session'):
                    current_roles_text, _ = self._get_member_current_manageable_roles_text(member)
                    context_note_for_llm = ""
                    if "You don't seem to have any skill" not in current_roles_text:
                        context_note_for_llm = f"[System Note for LLM: User is updating. {current_roles_text} Their new request follows this note in the user's actual message.]"
                    else:
                        context_note_for_llm = "[System Note for LLM: User is initiating/updating verification (may already be 'verified' generally). Their request follows this note in the user's actual message.]"
                    
                    history_for_llm_call.append({'role': 'assistant', 'content': context_note_for_llm})
                    logger.info(f"DM_HANDLER: Added update context to history for {member.name} for this LLM call.")
                
                if user_state['retries_left'] == 1:
                    logger.info(f"DM_HANDLER: This is the final attempt for {member.name}. Instructing LLM for final response.")
                    final_attempt_instruction = (
                        "[System Instruction for LLM: This is the user's final attempt in this session. "
                        "Based on the entire conversation, make your best effort to classify their roles. "
                        "In your 'message_to_user', clearly state the roles that WILL BE ASSIGNED, "
                        "do NOT ask for further textual confirmation (like 'is this correct? say yes'), "
                        "and inform them they can use the /assign-roles command for future changes. "
                        "You MUST set 'user_has_confirmed' to true and 'is_complete' to true in your JSON response if you propose any final set of roles, even if it's based on partial information or no specific skill roles. "
                        "If you cannot determine any roles even on this final attempt, state that clearly in 'message_to_user', set 'classification' to null or empty, but still set 'user_has_confirmed' and 'is_complete' to true to conclude the session.]\n"
                        "The user's actual final input (which you should respond to) follows this system instruction within their message."
                    )
                    llm_turn_user_content = final_attempt_instruction + "\n\nUser's final input: " + user_input
                
                user_state['conversation_history'].append({'role': 'user', 'content': user_input})
                is_first_substantive_user_reply = False

                llm_guidance: Optional[LLMVerificationResponse] = None
                async with dm_channel.typing():
                    # Trim conversation history to avoid oversized prompts. Keep system + most recent N messages.
                    max_msgs = getattr(self.settings, 'LLM_MAX_HISTORY_MESSAGES', 12)
                    trimmed_history = list(history_for_llm_call)
                    trimmed_note = None
                    if len(trimmed_history) > max_msgs:
                        # Keep the first system/assistant message and the last (max_msgs-1) messages
                        head = trimmed_history[:1]
                        tail = trimmed_history[-(max_msgs-1):]
                        trimmed_history = head + tail
                        trimmed_note = "[System Note for LLM: Earlier parts of the conversation were omitted for brevity.]"
                        # insert the trimmed note as an assistant message before the user's current message
                        trimmed_history.append({'role': 'assistant', 'content': trimmed_note})

                    llm_guidance = await self.llm_client.get_verification_guidance(
                        user_message=llm_turn_user_content,
                        conversation_history=trimmed_history,
                        categorized_server_roles=self.bot.categorized_server_roles,
                        available_roles_map=self.bot.server_roles_map,
                        verification_prompt_template=verification_prompt_template,
                        max_response_tokens=getattr(self.settings, 'LLM_MAX_RESPONSE_TOKENS', None),
                        preferred_locale=user_state.get('preferred_locale')
                    )

                if not llm_guidance: 
                    await dm_channel.send("I'm having trouble processing your information. Could you rephrase or try again?")
                    continue 

                if member.id not in self.active_verifications: return 
                user_state['conversation_history'].append({'role': 'assistant', 'content': llm_guidance['message_to_user']})
                user_state['last_proposed_classification'] = llm_guidance.get('classification')

                await dm_channel.send(llm_guidance['message_to_user']) 

                if llm_guidance.get('unassignable_skills'):
                    for skill_info in llm_guidance['unassignable_skills']: 
                        await self.notify_admin_unmappable_skill(member, skill_info)
                        # Save unmapped skill to database
                        if self.db_service:
                            try:
                                await self.db_service.save_unmapped_skill(
                                    user_id=member.id,
                                    user_name=member.name,
                                    skill_name=skill_info.get("skill", "Unknown"),
                                    suggested_category=skill_info.get("category"),
                                    source="verification",
                                )
                            except Exception as e:
                                logger.error(f"Failed to save unmapped skill to database: {e}", exc_info=True)

                if llm_guidance.get('user_has_confirmed') is True: 
                    logger.info(f"DM_HANDLER: LLM signaled confirmation for {member.name}.")
                    assigned_skill_role_ids = []
                    current_classification = llm_guidance.get('classification') 
                    if current_classification: 
                        for cat_roles in current_classification.values(): 
                            if cat_roles and isinstance(cat_roles, list): 
                                assigned_skill_role_ids.extend(self._map_role_names_to_ids(cat_roles)) 
                    
                    skill_roles_to_assign = [member.guild.get_role(rid) for rid in set(assigned_skill_role_ids) if isinstance(rid, int) and member.guild.get_role(rid) is not None]
                    
                    await self._conclude_verification(member, success=True, assigned_skill_roles=skill_roles_to_assign)
                    return 
                
                user_state['retries_left'] -= 1
                logger.info(f"DM_HANDLER: LLM did not signal final confirmation for {member.name}. Retries left: {user_state['retries_left']}")
            
            except asyncio.TimeoutError:
                logger.info(f"DM_HANDLER: Verification DM timed out for {member.name}.")
                await dm_channel.send(CommonMessages.verification_timeout())
                await self._conclude_verification(member, success=False, reason="User inactive in DM.")
                return
            except discord.Forbidden:
                logger.error(f"DM_HANDLER: Cannot send DM to {member.name} during conversation.")
                await self._conclude_verification(member, success=False, reason="Failed to send DM (DMs disabled mid-process).")
                return
            except Exception as e:
                logger.error(f"DM_HANDLER: Error during DM conversation with {member.name}: {e}", exc_info=True)
                await dm_channel.send("An unexpected error occurred. Try `/assign-roles` again or contact an admin.")
                await self._conclude_verification(member, success=False, reason="Internal error during DM conversation.")
                return
            
            if user_state.get('retries_left', 0) <= 0: 
                logger.info(f"DM_HANDLER: Retries exhausted for {member.name} based on count. Loop will terminate.")
                break 
        
        if member.id in self.active_verifications: 
            logger.info(f"DM_HANDLER: Max retries reached (concluding as failure) for {member.name}.")
            await self._conclude_verification(member, success=False, reason="Max retries reached after conversation attempts.")


    

    async def _send_admin_notification(self, guild: discord.Guild, title: str, message: str, color: discord.Color = discord.Color.blue()):
        """Helper to send a styled embed message to the notification channel."""
        if not self.settings.NOTIFICATION_CHANNEL_ID:
            logger.debug("SVC_NOTIFY: NOTIFICATION_CHANNEL_ID not set. Skipping admin notification.")
            return

        channel = guild.get_channel(self.settings.NOTIFICATION_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.error(f"SVC_NOTIFY: Invalid NOTIFICATION_CHANNEL_ID or channel not found: {self.settings.NOTIFICATION_CHANNEL_ID}")
            return
        
        try:
            embed = discord.Embed(title=title, description=message, color=color, timestamp=discord.utils.utcnow())
            await channel.send(embed=embed)
            logger.info(f"SVC_NOTIFY: Sent notification to #{channel.name}: {title}")
        except discord.Forbidden:
            logger.error(f"SVC_NOTIFY: Missing permissions to send message to notification channel #{channel.name} ({channel.id}).")
        except Exception as e:
            logger.error(f"SVC_NOTIFY: Failed to send admin notification: {e}", exc_info=True)


    async def _conclude_verification(self, member: discord.Member, success: bool, 
                                     reason: str = "", assigned_skill_roles: Optional[List[discord.Role]] = None):
        logger.info(f"SVC_CONCLUDE: Concluding for {member.name}. Success: {success}. Reason: {reason}")
        
        user_state = self.active_verifications.pop(member.id, None)
        was_update_session = user_state.get('is_update_session', False) if user_state else False
        conversation_history_for_summary = user_state.get('conversation_history', []) if user_state else []


        guild = member.guild
        if not guild: 
            logger.warning(f"SVC_CONCLUDE: Member {member.name} (ID: {member.id}) not in any guild (likely left).")
            return
        inprogress_role = guild.get_role(self.settings.VERIFICATION_IN_PROGRESS_ROLE_ID)
        verified_role = guild.get_role(self.settings.VERIFIED_ROLE_ID)
        unverified_role = guild.get_role(self.settings.UNVERIFIED_ROLE_ID)
        current_member_obj = guild.get_member(member.id) 
        if not current_member_obj:
            logger.warning(f"SVC_CONCLUDE: Member {member.name} (ID: {member.id}) no longer in guild {guild.name}. Cannot update roles.")
            return

        roles_to_add_final: List[discord.Role] = []
        roles_to_remove_final: List[discord.Role] = []
        final_dm_message_to_send: Optional[str] = None 

        if inprogress_role and inprogress_role in current_member_obj.roles:
            roles_to_remove_final.append(inprogress_role)

        admin_notification_title = ""
        admin_notification_message = ""
        admin_notification_color = discord.Color.green()

        if success:
            if not verified_role:
                final_dm_message_to_send = "A system error occurred (verified role missing). Please contact an admin."
                if unverified_role and unverified_role not in current_member_obj.roles: roles_to_add_final.append(unverified_role)
            else:
                if verified_role not in current_member_obj.roles: roles_to_add_final.append(verified_role)
                if unverified_role and unverified_role in current_member_obj.roles: roles_to_remove_final.append(unverified_role)
                new_target_skill_role_ids = set(r.id for r in assigned_skill_roles if r) if assigned_skill_roles else set()
                all_bot_managed_skill_ids = set()
                if self.bot.categorized_server_roles:
                    for cat_list in self.bot.categorized_server_roles.values():
                        all_bot_managed_skill_ids.update(cat_list)
                
                for role_id in new_target_skill_role_ids:
                    if role_id in all_bot_managed_skill_ids: 
                        role_obj = guild.get_role(role_id)
                        if role_obj and role_obj not in current_member_obj.roles:
                            if role_obj not in roles_to_add_final : roles_to_add_final.append(role_obj)
                for current_role_obj_user_has in current_member_obj.roles:
                    if current_role_obj_user_has.id in all_bot_managed_skill_ids: 
                        if current_role_obj_user_has.id not in new_target_skill_role_ids:
                             if current_role_obj_user_has not in roles_to_remove_final: roles_to_remove_final.append(current_role_obj_user_has)
            
            final_assigned_skill_role_names = sorted([r.name for r in assigned_skill_roles if r]) if assigned_skill_roles else ["None"]

            if not was_update_session:
                admin_notification_title = f"✅ New User Verified: {member.display_name}"
                summary_prompt_template = ""
                try:
                    with open(self.settings.PROMPT_PATH_NEW_USER_SUMMARY_SYSTEM_TEMPLATE, "r", encoding="utf-8") as f:
                        summary_prompt_template = f.read().strip()
                except Exception as e:
                    logger.error(f"SVC_CONCLUDE: Failed to load new user summary prompt: {e}")
                
                if summary_prompt_template and self.llm_client:
                    # Trim conversation history to avoid oversized prompts causing truncated LLM responses.
                    max_history_msgs = getattr(self.settings, 'LLM_MAX_HISTORY_MESSAGES', 12)
                    trimmed_history = conversation_history_for_summary
                    if isinstance(trimmed_history, list) and len(trimmed_history) > max_history_msgs:
                        # keep the first system/assistant message (if present) and the last (max_history_msgs-1) messages
                        head = trimmed_history[:1]
                        tail = trimmed_history[-(max_history_msgs-1):]
                        trimmed_history = head + tail
                        # note for transparency (not sent to user) could be included in the prompt if desired
                    # For summary purposes, include only the user's messages (omit assistant/system messages)
                    user_only_msgs = [msg for msg in trimmed_history if msg.get('role') == 'user']
                    if user_only_msgs:
                        conv_history_text = "\n".join([f"user: {msg['content']}" for msg in user_only_msgs])
                    else:
                        # If no user messages are available, log and provide a short placeholder so the LLM prompt is not empty
                        logger.debug(f"SVC_CONCLUDE: No user messages found in trimmed conversation for {member.name}. Using placeholder in summary prompt.")
                        conv_history_text = "(No user messages captured from the conversation.)"
                    # Truncate conversation text to a safe character limit before calling the LLM
                    max_summary_chars = getattr(self.settings, 'LLM_SUMMARY_MAX_CHARS', 1800)
                    conv_history_text_to_send = conv_history_text
                    if isinstance(conv_history_text, str) and len(conv_history_text) > max_summary_chars:
                        # Keep the tail (most recent user content) for context
                        conv_history_text_to_send = "...(truncated)...\n" + conv_history_text[-max_summary_chars:]
                        logger.debug(f"SVC_CONCLUDE: Conversation history truncated to {max_summary_chars} chars for summary for {member.name}.")

                    llm_summary = await self.llm_client.generate_new_user_summary(
                        conversation_history_text=conv_history_text_to_send,
                        assigned_roles_names_str=", ".join(final_assigned_skill_role_names),
                        summary_prompt_template=summary_prompt_template,
                        conversation_language="English",
                        max_response_tokens=getattr(self.settings, 'LLM_MAX_RESPONSE_TOKENS', None)
                    )
                    admin_notification_message = llm_summary if llm_summary else "LLM summary generation failed."
                else:
                    admin_notification_message = f"User successfully verified.\nAssigned roles: {', '.join(final_assigned_skill_role_names)}.\n(LLM summary prompt missing or LLM client error)"
            else:
                admin_notification_title = f"🔄 User Roles Updated: {member.display_name}"
                admin_notification_message = f"{member.mention} has updated their roles.\n**New Skill/Experience/OS Roles:** {', '.join(final_assigned_skill_role_names)}"
                admin_notification_color = discord.Color.orange()

        else:
            if not unverified_role:
                final_dm_message_to_send = "System error (unverified role missing). Contact admin."
            else:
                if unverified_role not in current_member_obj.roles: roles_to_add_final.append(unverified_role)
                final_dm_message_to_send = (
                    f"🇲🇽 **Español:**\n"
                    f"No se pudo completar el proceso de verificación para **{guild.name}**. Motivo: {reason}\n"
                    f"Se te asignó el estado 'unverified'. Intenta `/assign-roles` de nuevo o contacta a un admin.\n\n"
                    f"🇺🇸 **English:**\n"
                    f"The verification process for **{guild.name}** could not be completed. Reason: {reason}\n"
                    f"You were assigned 'unverified'. Try `/assign-roles` again or contact an admin."
                )
            admin_notification_title = f"❌ Verification Failed: {member.display_name}"
            admin_notification_message = f"{member.mention} could not complete verification.\nReason: {reason}\nStatus: Unverified"
            admin_notification_color = discord.Color.red()

        try:
            valid_roles_to_remove = list(set(r for r in roles_to_remove_final if isinstance(r, discord.Role)))
            valid_roles_to_add = list(set(r for r in roles_to_add_final if isinstance(r, discord.Role)))
            if valid_roles_to_remove: await current_member_obj.remove_roles(*valid_roles_to_remove, reason=f"Verification: {reason}")
            if valid_roles_to_add: await current_member_obj.add_roles(*valid_roles_to_add, reason=f"Verification: {reason}")
            if valid_roles_to_remove: logger.info(f"SVC_CONCLUDE: For {member.name}: Removed: {[r.name for r in valid_roles_to_remove]}.")
            if valid_roles_to_add: logger.info(f"SVC_CONCLUDE: For {member.name}: Added: {[r.name for r in valid_roles_to_add]}.")
            if not valid_roles_to_add and not valid_roles_to_remove: logger.info(f"SVC_CONCLUDE: No role changes actioned for {member.name}.")

            # Save role assignments to database (only save skill roles, not system roles like verified/unverified)
            if self.db_service and success and assigned_skill_roles:
                try:
                    skill_role_ids = [r.id for r in assigned_skill_roles if r]
                    if skill_role_ids:
                        result = await self.db_service.assign_roles_to_user(
                            user_id=member.id,
                            role_ids=skill_role_ids,
                            assigned_by="verification",
                            clear_existing=True,
                        )
                        logger.info(f"SVC_CONCLUDE: Saved {len(result['success'])} roles to database for {member.name}.")

                        # Send notification if any roles failed
                        if result['failed']:
                            logger.warning(f"SVC_CONCLUDE: {len(result['failed'])} roles failed for {member.name}")
                            await self.db_service._send_role_assignment_failure_notification(
                                user_id=member.id,
                                user_name=member.name,
                                failed_role_ids=result['failed'],
                                guild=guild
                            )
                except Exception as e:
                    logger.error(f"SVC_CONCLUDE: Failed to save roles to database for {member.name}: {e}", exc_info=True)

            if final_dm_message_to_send:
                try: await member.send(final_dm_message_to_send)
                except discord.Forbidden: logger.warning(f"SVC_CONCLUDE: Could not send final DM to {member.name}.")
        except discord.Forbidden: logger.error(f"SVC_CONCLUDE: Missing permissions to manage roles for {member.name}.")
        except discord.HTTPException as e: logger.error(f"SVC_CONCLUDE: HTTP error managing roles for {member.name}: {e}")
        except Exception as e: logger.error(f"SVC_CONCLUDE: Unexpected error during role/DM updates for {member.name}: {e}", exc_info=True)

        if success:
            try:
                asyncio.create_task(
                    self._offer_additional_suggested_roles(
                        member=member,
                        conversation_history=conversation_history_for_summary,
                        already_assigned_roles=assigned_skill_roles or [],
                    )
                )
            except Exception as e:
                logger.error(f"SVC_CONCLUDE: Failed to schedule additional role suggestion flow for {member.name}: {e}")

            # Fire-and-forget suspicious analysis should run after suggestion prompt is queued
            try:
                suspicious_service = getattr(self.bot, 'suspicious_account_service', None)
                if suspicious_service:
                    user_msgs = [m['content'] for m in conversation_history_for_summary if m.get('role') == 'user']
                    asyncio.create_task(
                        suspicious_service.analyze_and_mark(
                            member.guild,
                            member,
                            user_msgs,
                            self.settings.PROMPT_PATH_SUSPICIOUS_ANALYSIS_SYSTEM_TEMPLATE if hasattr(self.settings, 'PROMPT_PATH_SUSPICIOUS_ANALYSIS_SYSTEM_TEMPLATE') else ""
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to schedule suspicious account analysis for {member.name}: {e}", exc_info=True)

        if admin_notification_title and admin_notification_message:
            await self._send_admin_notification(guild, admin_notification_title, admin_notification_message, admin_notification_color)

    async def _offer_additional_suggested_roles(
        self,
        member: discord.Member,
        conversation_history: List[Dict[str, str]],
        already_assigned_roles: List[discord.Role],
    ) -> None:
        """Ask user if they want approximate/related role suggestions and assign on consent."""

        if not self.llm_client:
            return

        # Require categorized roles map
        if not self.bot.categorized_server_roles or not self.bot.server_roles_map:
            return

        # Try to reuse stored locale if available
        stored_locale = None
        if self.db_service:
            try:
                stored_locale = await self.db_service.get_user_locale(member.id)
            except Exception:
                stored_locale = None

        try:
            dm = await member.create_dm()
        except Exception:
            logger.warning(f"SUGGEST_ROLES: Could not open DM with {member.name} for suggestions.")
            return

        # Compose conversation text for the LLM
        convo_text_parts = []
        for msg in conversation_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if content:
                convo_text_parts.append(f"{role}: {content}")
        convo_text = "\n".join(convo_text_parts)
        max_chars = getattr(self.settings, 'LLM_SUMMARY_MAX_CHARS', 1800)
        if len(convo_text) > max_chars:
            convo_text = "...(truncated)...\n" + convo_text[-max_chars:]

        # Limit candidates to manageable roles (categorized list) and exclude system/already-assigned
        manageable_role_ids = set()
        for cat_ids in self.bot.categorized_server_roles.values():
            manageable_role_ids.update(cat_ids)

        excluded_ids = set(self._system_role_ids())
        excluded_ids.update([r.id for r in already_assigned_roles if r])
        excluded_ids.update([r.id for r in member.roles])

        filtered_roles_map = {
            rid: name
            for rid, name in self.bot.server_roles_map.items()
            if rid in manageable_role_ids and rid not in excluded_ids
        }

        if not filtered_roles_map:
            logger.debug(f"SUGGEST_ROLES: No manageable roles available for suggestions for {member.name}.")
            return

        suggestions = await self.llm_client.get_additional_role_suggestions(
            conversation_text=convo_text,
            available_roles_map=filtered_roles_map,
            already_assigned_role_ids=list(excluded_ids),
            max_suggestions=3,
            max_response_tokens=getattr(self.settings, 'LLM_MAX_RESPONSE_TOKENS', None),
            preferred_locale=stored_locale,
        )

        if not suggestions or not suggestions.get("suggested_role_ids"):
            logger.info(f"SUGGEST_ROLES: LLM returned no additional roles for {member.name}.")
            return

        candidate_roles: List[discord.Role] = []
        suggested_names = [n.lower() for n in suggestions.get("suggested_role_names", []) if isinstance(n, str)]
        for rid, name in filtered_roles_map.items():
            if isinstance(name, str) and name.lower() in suggested_names and rid not in excluded_ids:
                role_obj = member.guild.get_role(rid)
                if role_obj:
                    candidate_roles.append(role_obj)

        if not candidate_roles:
            logger.info(f"SUGGEST_ROLES: Suggested role names not found in guild for {member.name}.")
            return

        # Build confirmation message from LLM text plus plain names
        msg_md = suggestions.get("message_markdown") or "Tengo algunas sugerencias adicionales basadas en tu experiencia." 
        bullet_lines = [f"- {r.name}" for r in candidate_roles]
        final_message = msg_md.strip() + "\n\n" + "\n".join(bullet_lines)

        try:
            await dm.send(final_message)
        except discord.Forbidden:
            logger.warning(f"SUGGEST_ROLES: Cannot send suggestions DM to {member.name}.")
            return

        def _is_yes(text: str) -> bool:
            if not text:
                return False
            lowered = normalize('NFKD', text.strip().lower()).encode('ascii', 'ignore').decode('ascii')
            return lowered in {"yes", "y", "si", "s", "sure", "ok", "vale", "claro", "add", "agrega"}

        try:
            reply = await self.bot.wait_for(
                'message',
                timeout=180.0,
                check=lambda m: m.author.id == member.id and m.channel.id == dm.id and m.content is not None,
            )
        except asyncio.TimeoutError:
            logger.info(f"SUGGEST_ROLES: User {member.name} did not respond to suggestions.")
            return
        except Exception as e:
            logger.error(f"SUGGEST_ROLES: Error waiting for response from {member.name}: {e}")
            return

        if not _is_yes(reply.content):
            try:
                await dm.send("Entendido, no agregaré roles adicionales / Got it, no extra roles added.")
            except Exception:
                pass
            logger.info(f"SUGGEST_ROLES: {member.name} declined additional roles.")
            return

        roles_to_add = [r for r in candidate_roles if r not in member.roles]
        if not roles_to_add:
            await dm.send("Ya tienes todos esos roles asignados / You already have those roles assigned.")
            return

        try:
            await member.add_roles(*roles_to_add, reason="LLM suggested additional roles")
            if self.db_service:
                for role in roles_to_add:
                    try:
                        await self.db_service.add_role_to_user(
                            user_id=member.id,
                            role_id=role.id,
                            assigned_by="llm_suggestion",
                        )
                    except Exception as e:
                        logger.error(f"SUGGEST_ROLES: Failed to persist role {role.id} for {member.name}: {e}")
            await dm.send("Listo, agregué los roles adicionales / Done, added the suggested roles.")
            logger.info(f"SUGGEST_ROLES: Added suggested roles to {member.name}: {[r.name for r in roles_to_add]}")
        except discord.Forbidden:
            await dm.send("No tengo permisos para agregar esos roles. Avísale a un admin." )
            logger.error(f"SUGGEST_ROLES: Missing permissions to add suggested roles for {member.name}.")
        except Exception as e:
            logger.error(f"SUGGEST_ROLES: Failed to add suggested roles for {member.name}: {e}", exc_info=True)
            try:
                await dm.send("Ocurrió un error al agregar los roles. Intenta luego o contacta a un admin.")
            except Exception:
                pass

    async def notify_admin_unmappable_skill(self, member: discord.Member, skill_info: Dict[str, str]):
        if not self.settings.NOTIFICATION_CHANNEL_ID: return 
        channel = self.bot.get_channel(self.settings.NOTIFICATION_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.error(f"Invalid NOTIFICATION_CHANNEL_ID: {self.settings.NOTIFICATION_CHANNEL_ID}")
            return
        try:
            category = skill_info.get("category", "Unknown Category")
            skill_name = skill_info.get("skill", "Unknown Skill")
            embed = discord.Embed(title="🔔 Unmappable Skill Alert", description=f"User {member.mention} (`{member.id}`) mentioned skill.", color=discord.Color.orange())
            embed.add_field(name="User Name", value=member.name, inline=True)
            embed.add_field(name="Skill Mentioned", value=f"`{skill_name}`", inline=True)
            embed.add_field(name="Suggested Category", value=f"`{category}`", inline=True)
            embed.set_footer(text="Consider adding this as a new role if appropriate.")
            embed.timestamp = discord.utils.utcnow()
            await channel.send(embed=embed)
        except Exception as e: logger.error(f"Failed to send unmappable skill notification: {e}", exc_info=True)


    async def notify_admin_unmappable_skill(self, member: discord.Member, skill_info: Dict[str, str]):
        if not self.settings.NOTIFICATION_CHANNEL_ID:
            return 
        channel = self.bot.get_channel(self.settings.NOTIFICATION_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.error(f"Invalid NOTIFICATION_CHANNEL_ID or channel not found: {self.settings.NOTIFICATION_CHANNEL_ID}")
            return
        try:
            category = skill_info.get("category", "Unknown Category")
            skill_name = skill_info.get("skill", "Unknown Skill")
            embed = discord.Embed(title="🔔 Unmappable Skill Alert", description=f"User {member.mention} (`{member.id}`) mentioned a skill for which no corresponding role was found.", color=discord.Color.orange())
            embed.add_field(name="User Name", value=member.name, inline=True)
            embed.add_field(name="Skill Mentioned", value=f"`{skill_name}`", inline=True)
            embed.add_field(name="Suggested Category", value=f"`{category}`", inline=True)
            embed.set_footer(text="Consider adding this as a new role if appropriate.")
            embed.timestamp = discord.utils.utcnow()
            await channel.send(embed=embed)
            logger.info(f"Sent unmappable skill notification for user {member.name}, skill '{skill_name}'.")
        except discord.Forbidden: logger.error(f"Missing permissions to send message to notification channel {channel.id}.")
        except Exception as e: logger.error(f"Failed to send unmappable skill notification: {e}", exc_info=True)
