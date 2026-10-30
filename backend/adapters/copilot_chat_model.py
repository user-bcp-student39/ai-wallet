"""Adaptador del puerto ConversationalModel con el SDK de GitHub Copilot.

Usa por defecto la sesión local del CLI de Copilot. La sesión es de solo texto: sin herramientas
y con los permisos denegados, de modo que el modelo no puede tocar archivos ni ejecutar comandos.
"""

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Sequence

import copilot
from copilot.generated.rpc import PermissionDecisionReject
from copilot.session_events import AssistantMessageData

from ports.conversational_model import ChatMessage, ModelUnavailableError

logger = logging.getLogger(__name__)

MODEL_ENV = "COPILOT_MODEL"
USE_LOGGED_IN_USER_ENV = "COPILOT_USE_LOGGED_IN_USER"
REASONING_EFFORT_ENV = "COPILOT_REASONING_EFFORT"
TIMEOUT_ENV = "COPILOT_TIMEOUT_SECONDS"

DEFAULT_MODEL = "gpt-6-luna"
# gpt-6-luna acepta low, medium, high y xhigh (no minimal); low da la respuesta más rápida para un chat.
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_TIMEOUT_SECONDS = 60.0
TRUE_VALUES = {"true", "1", "yes", "s"}

ROLE_LABELS = {"user": "USUARIO", "assistant": "ASISTENTE"}


@dataclass(frozen=True)
class CopilotSettings:
    model: str = DEFAULT_MODEL
    use_logged_in_user: bool = True
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "CopilotSettings":
        return cls(
            model=os.environ.get(MODEL_ENV, DEFAULT_MODEL),
            use_logged_in_user=os.environ.get(USE_LOGGED_IN_USER_ENV, "true").lower() in TRUE_VALUES,
            reasoning_effort=os.environ.get(REASONING_EFFORT_ENV, DEFAULT_REASONING_EFFORT),
            timeout_seconds=float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS)),
        )


def build_prompt(messages: Sequence[ChatMessage]) -> str:
    return "\n\n".join(f"[{ROLE_LABELS.get(m.role, m.role.upper())}]\n{m.content}" for m in messages)


def _deny_permission(*_: Any) -> PermissionDecisionReject:
    return PermissionDecisionReject(feedback="El asistente solo genera texto.")


def _default_client_factory(settings: CopilotSettings) -> Any:
    return copilot.CopilotClient(use_logged_in_user=settings.use_logged_in_user)


class CopilotChatModel:
    """Un cliente de larga vida (start/stop) y una sesión nueva por mensaje."""

    def __init__(
        self,
        settings: CopilotSettings | None = None,
        client_factory: Callable[[CopilotSettings], Any] = _default_client_factory,
    ) -> None:
        self._settings = settings or CopilotSettings()
        self._client_factory = client_factory
        self._client: Any | None = None

    async def start(self) -> None:
        """Inicia el cliente. Si falla, el modelo queda no disponible pero la aplicación sigue arrancando."""
        try:
            client = self._client_factory(self._settings)
            await client.start()
        except Exception:
            logger.exception("No se pudo iniciar el cliente de Copilot; el asistente no estará disponible.")
            self._client = None
            return
        self._client = client

    async def stop(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        try:
            await client.stop()
        except Exception:
            logger.warning("No se pudo cerrar limpiamente el cliente de Copilot.", exc_info=True)

    async def complete(self, system: str, messages: Sequence[ChatMessage]) -> str:
        client = self._client
        if client is None:
            raise ModelUnavailableError("El cliente de Copilot no está iniciado.")
        try:
            async with await client.create_session(
                model=self._settings.model,
                reasoning_effort=self._settings.reasoning_effort,
                available_tools=[],
                on_permission_request=_deny_permission,
                system_message={"mode": "replace", "content": system},
                skip_custom_instructions=True,
                working_directory=os.getcwd(),
            ) as session:
                event = await session.send_and_wait(build_prompt(messages), timeout=self._settings.timeout_seconds)
        except Exception as exc:
            logger.warning("Copilot no pudo responder (%s): %s", type(exc).__name__, str(exc)[:300])
            raise ModelUnavailableError(f"Copilot no pudo responder ({type(exc).__name__}).") from exc
        if event is None or not isinstance(event.data, AssistantMessageData) or not event.data.content:
            raise ModelUnavailableError("Copilot terminó sin devolver texto.")
        return event.data.content


def copilot_lifespan(model: CopilotChatModel) -> Callable[[Any], Any]:
    """Lifespan de FastAPI: inicia el cliente al arrancar la aplicación y lo cierra al apagarla."""

    @asynccontextmanager
    async def lifespan(_app: Any) -> AsyncIterator[None]:
        await model.start()
        try:
            yield
        finally:
            await model.stop()

    return lifespan
