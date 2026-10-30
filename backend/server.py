"""Punto de entrada del servidor (composición de dependencias). Ejecutar con: uvicorn server:app"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from adapters.agui_endpoint import create_app
from adapters.wallet_api_client import WalletApiClient
from domain.onboarding import DEFAULT_SESSION_TTL

load_dotenv(Path(__file__).resolve().parent / ".env")

ttl = timedelta(seconds=int(os.environ["ONBOARDING_SESSION_TTL_SECONDS"])) if "ONBOARDING_SESSION_TTL_SECONDS" in os.environ else DEFAULT_SESSION_TTL

app = create_app(WalletApiClient.from_env(), ttl=ttl)
