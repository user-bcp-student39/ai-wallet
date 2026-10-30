"""Adaptador de entrada: expone el agente de onboarding a CopilotKit mediante el protocolo AG-UI."""

from datetime import timedelta

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.langgraph_onboarding import build_onboarding_graph
from domain.onboarding import DEFAULT_SESSION_TTL
from ports.wallet_gateway import WalletGateway
from ports.wallet_repository import WalletRepository

AGENT_PATH = "/agent"
FRONTEND_ORIGINS = ["http://localhost:4200"]


def create_app(
    gateway: WalletGateway, repository: WalletRepository, ttl: timedelta = DEFAULT_SESSION_TTL
) -> FastAPI:
    app = FastAPI(title="ai-wallet onboarding agent")
    app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    agent = LangGraphAgent(
        name="onboarding",
        description="Onboarding conversacional de wallet de bajo monto",
        graph=build_onboarding_graph(gateway, repository, ttl=ttl),
    )
    add_langgraph_fastapi_endpoint(app, agent, AGENT_PATH)
    return app
