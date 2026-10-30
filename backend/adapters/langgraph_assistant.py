"""Grafo LangGraph del asistente del chat. El modelo solo genera texto; el grafo decide si invoca la tool de datos."""

import json
import logging
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from application.onboarding_service import WalletPersistenceError
from application.wallet_data_message import DATA_INTRO, format_wallet_data
from ports.conversational_model import ChatMessage, ConversationalModel, ModelUnavailableError

logger = logging.getLogger(__name__)

CLASSIFY_NODE = "classify"
SHOW_DATA_NODE = "show_data"

INTENT_CHAT = "chat"
INTENT_SHOW_MY_DATA = "show_my_data"

HISTORY_LIMIT = 10
REDACTED_KEY = "redacted"

UNAVAILABLE_MESSAGE = "El asistente no está disponible por ahora. Puedes continuar con el formulario."
LOOKUP_ERROR_MESSAGE = "No pude consultar tus datos en este momento. Inténtalo de nuevo más tarde."
FALLBACK_REPLY = "No pude entender tu mensaje. ¿Puedes reformularlo?"

SYSTEM_PROMPT = """Eres el asistente del onboarding de una wallet de bajo monto. Respondes siempre en español, de forma breve y amable.

Contexto del proceso: el usuario completa 5 pasos en un formulario junto al chat: datos personales (nombre y apellidos), contacto (teléfono y email), documento (DNI de exactamente 8 dígitos), monto máximo por operación (mayor que 0 y hasta 500 PEN, en soles) y activación. La sesión se mantiene 5 minutos sin actividad y luego el proceso se reinicia. Tras activarse, la wallet queda lista para pagos de bajo monto.

Responde SIEMPRE con un único objeto JSON, sin texto adicional ni bloques de código:
{"intent": "chat", "reply": "<tu respuesta>"}
o bien
{"intent": "show_my_data", "reply": ""}

Usa "show_my_data" únicamente cuando el usuario pida ver o consultar los datos que él mismo registró (nombre, DNI, teléfono, email, monto máximo, estado o identificador de su wallet). La aplicación mostrará esos datos; tú no los conoces ni debes inventarlos.
Si el usuario pide datos de otra persona, usa "chat" y explica que solo puedes mostrar los datos registrados en su propia sesión.
No pidas ni repitas datos personales. Si no sabes algo, dilo con claridad."""


class AssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: str


def _text(message: AnyMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


def _is_redacted(message: AnyMessage) -> bool:
    """Un mensaje con datos registrados se reconoce por su encabezado fijo: el cliente puede reenviar la conversación sin los metadatos."""
    if not isinstance(message, AIMessage):
        return False
    return bool(message.additional_kwargs.get(REDACTED_KEY)) or _text(message).startswith(DATA_INTRO)


def _model_messages(messages: list[AnyMessage]) -> list[ChatMessage]:
    """Conversación que se envía al modelo: sin los mensajes con datos registrados y con historial acotado."""
    chat: list[ChatMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            chat.append(ChatMessage("user", _text(message)))
        elif isinstance(message, AIMessage) and not _is_redacted(message):
            chat.append(ChatMessage("assistant", _text(message)))
    return chat[-HISTORY_LIMIT:]


def parse_model_reply(text: str) -> tuple[str, str]:
    """Devuelve (intent, reply). Una salida que no sea el JSON esperado se trata como respuesta de chat."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`").removeprefix("json").strip()
    try:
        parsed = json.loads(candidate)
    except ValueError:
        return INTENT_CHAT, text.strip()
    if not isinstance(parsed, dict) or parsed.get("intent") not in (INTENT_CHAT, INTENT_SHOW_MY_DATA):
        return INTENT_CHAT, text.strip()
    reply = parsed.get("reply")
    return parsed["intent"], reply.strip() if isinstance(reply, str) else ""


def _classify_node(model: ConversationalModel):
    async def node(state: AssistantState) -> dict[str, Any]:
        messages = state["messages"]
        # Sin un mensaje nuevo del usuario no hay nada que responder.
        if not messages or not isinstance(messages[-1], HumanMessage):
            return {"intent": INTENT_CHAT}
        try:
            text = await model.complete(SYSTEM_PROMPT, _model_messages(messages))
        except ModelUnavailableError:
            return {"messages": [AIMessage(content=UNAVAILABLE_MESSAGE)], "intent": INTENT_CHAT}
        intent, reply = parse_model_reply(text)
        if intent == INTENT_SHOW_MY_DATA:
            return {"intent": INTENT_SHOW_MY_DATA}
        return {"messages": [AIMessage(content=reply or FALLBACK_REPLY)], "intent": INTENT_CHAT}

    return node


def _show_data_node(wallet_data_tool: BaseTool):
    async def node(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
        # El hilo lo fija el servidor; ni el modelo ni el usuario eligen qué registro se muestra.
        thread_id = (config.get("configurable") or {}).get("thread_id") or ""
        try:
            result = await wallet_data_tool.ainvoke({"thread_id": thread_id})
        except WalletPersistenceError:
            logger.warning("No se pudo leer el registro de la sesión para el asistente.")
            return {"messages": [AIMessage(content=LOOKUP_ERROR_MESSAGE)]}
        return {"messages": [AIMessage(content=format_wallet_data(result), additional_kwargs={REDACTED_KEY: True})]}

    return node


def _route_after_classify(state: AssistantState) -> str:
    return SHOW_DATA_NODE if state.get("intent") == INTENT_SHOW_MY_DATA else END


def build_assistant_graph(
    model: ConversationalModel,
    wallet_data_tool: BaseTool,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compila el grafo del asistente con su propio checkpointer, distinto del de onboarding."""
    builder = StateGraph(AssistantState)
    builder.add_node(CLASSIFY_NODE, _classify_node(model))
    builder.add_node(SHOW_DATA_NODE, _show_data_node(wallet_data_tool))
    builder.add_edge(START, CLASSIFY_NODE)
    builder.add_conditional_edges(CLASSIFY_NODE, _route_after_classify, [SHOW_DATA_NODE, END])
    builder.add_edge(SHOW_DATA_NODE, END)
    return builder.compile(checkpointer=checkpointer or MemorySaver())
