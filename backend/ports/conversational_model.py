"""Puerto de salida hacia el modelo de lenguaje conversacional. El núcleo no conoce el proveedor."""

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" o "assistant"
    content: str


class ModelUnavailableError(RuntimeError):
    """El modelo no respondió, devolvió un error, agotó el tiempo de espera o no está iniciado."""


@runtime_checkable
class ConversationalModel(Protocol):
    async def complete(self, system: str, messages: Sequence[ChatMessage]) -> str:
        """Devuelve el texto de la respuesta. Debe lanzar ModelUnavailableError si no puede obtenerlo."""
        ...
