# File: utils/i18n.py
"""
Internationalization utilities for bilingual Spanish/English messages.
"""

from typing import Optional


def locale_to_flag(locale: Optional[str]) -> str:
    """Convert a locale like 'es-MX' or 'en-US' to a flag emoji; fallback smartly."""
    if not locale:
        return "🌐"

    parts = locale.replace('_', '-').split('-')
    language = parts[0].lower() if parts else ""
    region = parts[1].upper() if len(parts) > 1 and parts[1] else ""

    if region.isalpha() and len(region) == 2:
        base = ord('🇦') - ord('A')
        return chr(base + ord(region[0])) + chr(base + ord(region[1]))

    # Fallback defaults by language if no region provided
    default_flags = {
        "es": "🇲🇽",  # default Spanish to Mexico for this bot audience
        "en": "🇺🇸",
        "fr": "🇫🇷",
        "de": "🇩🇪",
        "pt": "🇧🇷",
        "it": "🇮🇹",
        "ja": "🇯🇵",
        "ko": "🇰🇷",
        "zh": "🇨🇳",
    }
    return default_flags.get(language, "🌐")


def bilingual(es: str, en: str, separator: str = "\n\n", flags: bool = True) -> str:
    """
    Create a bilingual message with Spanish first, then English.

    Args:
        es: Spanish text
        en: English text
        separator: Separator between languages (default: double newline)
        flags: Whether to include flag emojis and language labels (default: True)

    Returns:
        Formatted bilingual message

    Example:
        >>> bilingual(
        ...     es="¡Hola! Bienvenido al servidor.",
        ...     en="Hello! Welcome to the server."
        ... )
        '🇲🇽 **Español:**\n¡Hola! Bienvenido al servidor.\n\n🇺🇸 **English:**\nHello! Welcome to the server.'
    """
    if flags:
        return (
            f"🇲🇽 **Español:**\n{es}{separator}"
            f"🇺🇸 **English:**\n{en}"
        )
    else:
        return f"{es}{separator}{en}"


def bilingual_field(
    es_name: str,
    es_value: str,
    en_name: str,
    en_value: str,
    inline: bool = False
) -> list[dict]:
    """
    Create bilingual embed fields (Spanish first, then English).

    Args:
        es_name: Spanish field name
        es_value: Spanish field value
        en_name: English field name
        en_value: English field value
        inline: Whether fields should be inline

    Returns:
        List of two field dictionaries for Discord embed

    Example:
        >>> fields = bilingual_field(
        ...     es_name="Descripción",
        ...     es_value="Este es un ejemplo",
        ...     en_name="Description",
        ...     en_value="This is an example"
        ... )
    """
    return [
        {"name": f"🇲🇽 {es_name}", "value": es_value, "inline": inline},
        {"name": f"🇺🇸 {en_name}", "value": en_value, "inline": inline}
    ]


# Common bilingual messages for reuse
class CommonMessages:
    """Common bilingual messages used throughout the bot."""

    DM_DISABLED = bilingual(
        es="No pude enviarte un mensaje directo. Por favor, verifica que tengas los mensajes directos habilitados para este servidor.",
        en="I couldn't send you a DM. Please check if you have DMs enabled for this server."
    )

    VERIFICATION_STARTED = bilingual(
        es="¡Te he enviado un mensaje directo para iniciar/actualizar tu verificación de roles!",
        en="I've sent you a DM to start/update your role verification!",
        flags=False
    )

    ERROR_GENERIC = bilingual(
        es="Ocurrió un error inesperado. Por favor, contacta a un administrador.",
        en="An unexpected error occurred. Please contact an administrator.",
        flags=False
    )

    ROLES_UPDATED = bilingual(
        es="Tus roles han sido actualizados exitosamente.",
        en="Your roles were updated successfully.",
        flags=False
    )

    VERIFY_BUTTON_DM_SENT = bilingual(
        es=(
            "Te hemos enviado un mensaje directo para comenzar tu verificacion. "
            "Haz clic en el boton de abajo para ir directamente a la conversacion."
        ),
        en=(
            "We have sent you a direct message to begin your verification. "
            "Click the button below to navigate directly to the conversation."
        ),
    )

    VERIFY_BUTTON_DM_DISABLED = bilingual(
        es=(
            "No fue posible enviarte un mensaje directo. Tu verificacion no pudo completarse "
            "porque los mensajes directos estan desactivados en tu cuenta. "
            "Por favor, habilita los mensajes directos para este servidor en tu configuracion "
            "de privacidad y vuelve a intentarlo."
        ),
        en=(
            "We were unable to send you a direct message. Your verification could not be "
            "completed because direct messages are disabled on your account. "
            "Please enable direct messages for this server in your privacy settings and try again."
        ),
    )

    @staticmethod
    def verification_timeout() -> str:
        """Message for when verification times out."""
        return bilingual(
            es="Parece que has estado inactivo. La verificación ha expirado. Usa `/assign-roles` para reiniciar.",
            en="It looks like you've been inactive. Verification timed out. Use `/assign-roles` to restart."
        )

    @staticmethod
    def bot_only() -> str:
        """Message when command is used by a bot."""
        return bilingual(
            es="Los bots no pueden usar este comando.",
            en="Bots cannot use this command.",
            flags=False
        )

    @staticmethod
    def server_only() -> str:
        """Message when command must be used in a server."""
        return bilingual(
            es="Este comando solo puede usarse dentro de un servidor.",
            en="This command can only be used within a server.",
            flags=False
        )
