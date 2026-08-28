# File: cogs/verification_embed_cog.py

import discord
from discord.ext import commands
import logging
import json
import os
from typing import Optional

from utils.i18n import bilingual, CommonMessages

logger = logging.getLogger(__name__)

VERIFICATION_EMBED_DATA_FILE = "data/verification_embed.json"
VERIFY_BUTTON_CUSTOM_ID = "serversage:verify_button"


class VerificationButtonView(discord.ui.View):
    """Persistent view attached to the lobby verification embed."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Verificar / Verify",
        style=discord.ButtonStyle.primary,
        custom_id=VERIFY_BUTTON_CUSTOM_ID,
        emoji="\U0001f510",  # lock emoji
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if member.bot:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        verification_service = getattr(self.bot, "verification_service", None)
        if not verification_service:
            await interaction.followup.send(
                bilingual(
                    es="El servicio de verificacion no esta disponible en este momento. Por favor, contacta a un administrador.",
                    en="The verification service is unavailable at the moment. Please contact an administrator.",
                ),
                ephemeral=True,
            )
            return

        # Retrieve DM channel so we can build a deep-link before the service
        # sends anything. create_dm() never raises Forbidden; only send() does.
        try:
            dm_channel = await member.create_dm()
            dm_url = f"https://discord.com/channels/@me/{dm_channel.id}"
        except Exception as e:
            logger.error(f"VERIFY_BTN: Could not open DM channel for {member.name}: {e}")
            await interaction.followup.send(
                bilingual(
                    es="Ocurrio un error inesperado al preparar tu verificacion. Por favor, contacta a un administrador.",
                    en="An unexpected error occurred while preparing your verification. Please contact an administrator.",
                ),
                ephemeral=True,
            )
            return

        locale_raw = getattr(interaction, "locale", None)
        locale = locale_raw.value if hasattr(locale_raw, "value") else (str(locale_raw) if locale_raw else None)

        try:
            dm_sent = await verification_service.start_verification_process(
                member, None, locale=locale
            )
        except Exception as e:
            logger.error(f"VERIFY_BTN: Unexpected error in start_verification_process for {member.name}: {e}", exc_info=True)
            await interaction.followup.send(
                bilingual(
                    es="Ocurrio un error inesperado al iniciar la verificacion. Por favor, contacta a un administrador.",
                    en="An unexpected error occurred while starting verification. Please contact an administrator.",
                ),
                ephemeral=True,
            )
            return

        if dm_sent:
            go_view = discord.ui.View(timeout=120)
            go_view.add_item(
                discord.ui.Button(
                    label="Ir a Verificacion / Go to Verification",
                    style=discord.ButtonStyle.link,
                    url=dm_url,
                    emoji="\U0001f4ec",  # mailbox emoji
                )
            )
            await interaction.followup.send(
                CommonMessages.VERIFY_BUTTON_DM_SENT,
                view=go_view,
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                CommonMessages.VERIFY_BUTTON_DM_DISABLED,
                ephemeral=True,
            )


class VerificationEmbedCog(commands.Cog, name="VerificationEmbed"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = bot.settings
        self._embed_message_id: Optional[int] = None
        self._load_stored_message_id()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_stored_message_id(self):
        try:
            if os.path.exists(VERIFICATION_EMBED_DATA_FILE):
                with open(VERIFICATION_EMBED_DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._embed_message_id = data.get("message_id")
                    logger.debug(f"Loaded stored verification embed message ID: {self._embed_message_id}")
        except Exception as e:
            logger.error(f"Failed to load verification embed data file: {e}")
            self._embed_message_id = None

    def _save_message_id(self, message_id: int):
        try:
            os.makedirs(os.path.dirname(VERIFICATION_EMBED_DATA_FILE), exist_ok=True)
            with open(VERIFICATION_EMBED_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump({"message_id": message_id}, f)
            self._embed_message_id = message_id
        except Exception as e:
            logger.error(f"Failed to save verification embed message ID: {e}")

    # ------------------------------------------------------------------
    # Embed builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_embed() -> discord.Embed:
        embed = discord.Embed(
            title="Area de Espera  |  Lobby Area",
            color=0x5865F2,
        )
        embed.description = (
            "**Espanol:**\n"
            "Te encuentras en el area de espera del servidor. Para obtener acceso al "
            "servidor completo, debes completar el proceso de verificacion. "
            "Haz clic en el boton de abajo para comenzar.\n\n"
            "**English:**\n"
            "You are currently in the server's lobby area. To gain full access to the "
            "server, you need to complete the verification process. "
            "Click the button below to get started."
        )
        embed.set_footer(text="ServerSage  |  Verification System")
        return embed

    # ------------------------------------------------------------------
    # Embed lifecycle
    # ------------------------------------------------------------------

    async def ensure_verification_embed(self, guild: discord.Guild):
        """Post the verification embed if it does not already exist in the channel."""
        channel_id = getattr(self.settings, "VERIFICATION_CHANNEL_ID", None)
        if not channel_id:
            logger.info("VERIFICATION_CHANNEL_ID not configured. Skipping verification embed setup.")
            return

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            logger.warning(f"Verification channel ID {channel_id} not found or is not a text channel.")
            return

        # Try to confirm the stored message still exists
        if self._embed_message_id:
            try:
                await channel.fetch_message(self._embed_message_id)
                logger.info(f"Verification embed already present (message ID: {self._embed_message_id}).")
                return
            except discord.NotFound:
                logger.info("Stored verification embed message was deleted. Recreating...")
            except Exception as e:
                logger.error(f"Error fetching stored verification embed message: {e}")

        await self._post_embed(channel)

    async def _post_embed(self, channel: discord.TextChannel):
        """Send a fresh verification embed to the channel and persist its ID."""
        try:
            view = VerificationButtonView(self.bot)
            msg = await channel.send(embed=self._build_embed(), view=view)
            self._save_message_id(msg.id)
            logger.info(f"Posted verification embed (ID: {msg.id}) in #{channel.name}.")
        except discord.Forbidden:
            logger.error(f"Missing permissions to post verification embed in #{channel.name}.")
        except Exception as e:
            logger.error(f"Failed to post verification embed: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent view so interactions survive bot restarts
        self.bot.add_view(VerificationButtonView(self.bot))
        logger.info("Registered persistent VerificationButtonView.")

        if self.bot.guilds:
            await self.ensure_verification_embed(self.bot.guilds[0])

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Recreate the embed automatically if someone deletes it."""
        if self._embed_message_id and message.id == self._embed_message_id:
            logger.info("Verification embed message was deleted. Recreating...")
            self._embed_message_id = None
            if message.guild:
                await self.ensure_verification_embed(message.guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationEmbedCog(bot))
