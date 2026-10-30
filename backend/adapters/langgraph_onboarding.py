"""Workflow LangGraph del onboarding: un nodo por paso, con interrupciones para esperar al usuario."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Callable, TypedDict

from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from adapters.activation_tool import build_activation_tool
from application.onboarding_service import OnboardingService
from domain.onboarding import (
    DEFAULT_CURRENCY,
    DEFAULT_SESSION_TTL,
    STEP_FIELDS,
    OnboardingSession,
    OnboardingValidationError,
    Step,
    validate_step,
)
from ports.wallet_gateway import WalletGateway
from ports.wallet_repository import WalletRepository

BOOTSTRAP_NODE = "bootstrap"

NODE_BY_STEP = {
    Step.NAME: "name",
    Step.CONTACT: "contact",
    Step.DNI: "dni",
    Step.MAX_AMOUNT: "max_amount",
    Step.ACTIVATION: "activation",
}


class OnboardingState(TypedDict):
    messages: Annotated[list, add_messages]
    step: int
    data: dict[str, str]
    errors: list[dict[str, str | None]]
    activated: bool
    wallet_id: str | None
    reason: str | None
    last_progress_at: str | None
    done: bool


def initial_state() -> OnboardingState:
    return {
        "messages": [],
        "step": int(Step.NAME),
        "data": {},
        "errors": [],
        "activated": False,
        "wallet_id": None,
        "reason": None,
        "last_progress_at": None,
        "done": False,
    }


SESSION_EXPIRED_MESSAGE = "La sesión expiró por inactividad. Empezamos de nuevo desde el paso 1."


def _is_expired(state: OnboardingState, now: datetime, ttl: timedelta) -> bool:
    last = state["last_progress_at"]
    if last is None:
        return False
    session = OnboardingSession(step=Step(state["step"]), data={}, last_progress_at=datetime.fromisoformat(last))
    return session.is_expired(now, ttl)


def _restart(now: datetime) -> dict[str, Any]:
    return {
        "step": int(Step.NAME),
        "data": {},
        "errors": [{"field": None, "message": SESSION_EXPIRED_MESSAGE}],
        "activated": False,
        "wallet_id": None,
        "reason": None,
        "done": False,
        "last_progress_at": now.isoformat(),
    }


def _bootstrap_node(clock: Callable[[], datetime]) -> Callable[[OnboardingState], dict[str, Any]]:
    def node(state: OnboardingState) -> dict[str, Any]:
        # El cliente AG-UI puede enviar un estado vacío; se completan solo las claves ausentes.
        defaults = initial_state()
        update = {key: value for key, value in defaults.items() if key not in state and key != "messages"}
        if not state.get("last_progress_at"):
            update["last_progress_at"] = clock().isoformat()
        return update

    return node


def _route_after(state: OnboardingState) -> str:
    return END if state.get("done") else NODE_BY_STEP[Step(state["step"])]


def _data_step_node(
    step: Step, clock: Callable[[], datetime], ttl: timedelta
) -> Callable[[OnboardingState], dict[str, Any]]:
    def node(state: OnboardingState) -> dict[str, Any]:
        payload: dict[str, Any] = {"step": int(step), "fields": list(STEP_FIELDS[step]), "errors": state["errors"]}
        if step is Step.MAX_AMOUNT:
            payload["moneda"] = DEFAULT_CURRENCY
        answer = interrupt(payload)
        now = clock()
        if _is_expired(state, now, ttl):
            return _restart(now)
        try:
            cleaned = validate_step(step, answer if isinstance(answer, dict) else {})
        except OnboardingValidationError as exc:
            return {"errors": [{"field": error.field, "message": error.message} for error in exc.errors]}
        normalized = {key: str(value) for key, value in cleaned.items()}
        return {
            "step": int(step) + 1,
            "data": {**state["data"], **normalized},
            "errors": [],
            "last_progress_at": now.isoformat(),
        }

    return node


def _activation_node(
    activate_wallet: BaseTool, clock: Callable[[], datetime], ttl: timedelta
) -> Callable[[OnboardingState], dict[str, Any]]:
    def node(state: OnboardingState) -> dict[str, Any]:
        answer = interrupt({"step": int(Step.ACTIVATION), "confirm": True, "errors": state["errors"]})
        now = clock()
        if _is_expired(state, now, ttl):
            return _restart(now)
        if not (isinstance(answer, dict) and answer.get("confirmar") is True):
            return {"errors": [{"field": None, "message": "Confirma la activación para continuar."}]}
        result = activate_wallet.invoke({"data": dict(state["data"]), "confirmed_at": now.isoformat()})
        return {
            "activated": result["activated"],
            "wallet_id": result["wallet_id"],
            "reason": result["reason"],
            "errors": [],
            "done": True,
        }

    return node


def build_onboarding_graph(
    gateway: WalletGateway,
    repository: WalletRepository,
    checkpointer: BaseCheckpointSaver | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ttl: timedelta = DEFAULT_SESSION_TTL,
):
    """Compila el grafo. Cada invocación debe usar config["configurable"]["thread_id"].

    ttl: inactividad máxima entre pasos; al superarla el onboarding vuelve al paso 1.
    """
    builder = StateGraph(OnboardingState)
    activate_wallet = build_activation_tool(OnboardingService(gateway, repository, ttl))
    builder.add_node(BOOTSTRAP_NODE, _bootstrap_node(clock))
    for step in Step:
        if step is Step.ACTIVATION:
            builder.add_node(NODE_BY_STEP[step], _activation_node(activate_wallet, clock, ttl))
        else:
            builder.add_node(NODE_BY_STEP[step], _data_step_node(step, clock, ttl))

    builder.add_edge(START, BOOTSTRAP_NODE)
    targets = [*NODE_BY_STEP.values(), END]
    for node_name in [BOOTSTRAP_NODE, *NODE_BY_STEP.values()]:
        builder.add_conditional_edges(node_name, _route_after, targets)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
