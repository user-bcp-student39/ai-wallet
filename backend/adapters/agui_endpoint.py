"""Adaptador de entrada: expone los agentes de onboarding y del asistente a CopilotKit mediante el protocolo AG-UI."""

from datetime import timedelta
from typing import Any, Callable

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.langgraph_assistant import build_assistant_graph
from adapters.langgraph_onboarding import build_onboarding_graph
from adapters.onboarding_session_lookup import OnboardingSessionLookup
from adapters.wallet_data_tool import build_wallet_data_tool
from domain.onboarding import DEFAULT_SESSION_TTL
from ports.conversational_model import ConversationalModel
from ports.wallet_gateway import WalletGateway
from ports.wallet_repository import WalletRepository

AGENT_PATH = "/agent"
ASSISTANT_PATH = "/assistant"
FRONTEND_ORIGINS = ["http://localhost:4200"]


def create_app(
    gateway: WalletGateway,
    repository: WalletRepository,
    model: ConversationalModel,
    ttl: timedelta = DEFAULT_SESSION_TTL,
    lifespan: Callable[[Any], Any] | None = None,
) -> FastAPI:
    app = FastAPI(title="ai-wallet onboarding agent", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    onboarding_graph = build_onboarding_graph(gateway, repository, ttl=ttl)
    # El asistente lee la wallet de la sesión a través del grafo de onboarding, pero con su propio checkpointer.
    wallet_data_tool = build_wallet_data_tool(repository, OnboardingSessionLookup(onboarding_graph))
    onboarding_agent = LangGraphAgent(
        name="onboarding",
        description="Onboarding conversacional de wallet de bajo monto",
        graph=onboarding_graph,
    )
    assistant_agent = LangGraphAgent(
        name="assistant",
        description="Asistente del chat: responde dudas y muestra los datos registrados de la sesión",
        graph=build_assistant_graph(model, wallet_data_tool),
    )
    add_langgraph_fastapi_endpoint(app, onboarding_agent, AGENT_PATH)
    add_langgraph_fastapi_endpoint(app, assistant_agent, ASSISTANT_PATH)
    return app
