"""Texto fijo con los datos registrados de la wallet. Lo genera la aplicación, nunca el modelo."""

from typing import Any, Mapping

from domain.onboarding import DEFAULT_CURRENCY

# Campos visibles, en orden. El identificador de verificación (kyc_id) no se muestra.
VISIBLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("wallet_id", "ID de wallet"),
    ("state", "Estado"),
    ("document_number", "DNI"),
    ("document_type", "Tipo de documento"),
    ("name", "Nombre"),
    ("last_name", "Apellidos"),
    ("phone", "Teléfono"),
    ("email", "Email"),
    ("max_amount", "Monto máximo por operación"),
)

NO_DATA_MESSAGE = "Todavía no hay datos registrados en esta sesión."
DATA_INTRO = "Estos son tus datos registrados:"

# El chat renderiza markdown: sin escapar, un `_` en un valor (p. ej. wallet_123) altera el texto mostrado.
_MARKDOWN_SPECIAL = "\\`*_[]<>~"


def _escape_markdown(value: object) -> str:
    return "".join(f"\\{char}" if char in _MARKDOWN_SPECIAL else char for char in str(value))


def format_wallet_data(result: Mapping[str, Any]) -> str:
    """Convierte el resultado de la tool get_my_wallet_data en el mensaje que se muestra al usuario."""
    record = result.get("record") if result.get("found") else None
    if not record:
        return NO_DATA_MESSAGE
    lines = []
    for field, label in VISIBLE_FIELDS:
        value = _escape_markdown(record[field])
        lines.append(f"- {label}: {value} {DEFAULT_CURRENCY}" if field == "max_amount" else f"- {label}: {value}")
    return "\n".join([DATA_INTRO, *lines])
