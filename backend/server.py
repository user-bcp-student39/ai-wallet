"""Punto de entrada del servidor (composición de dependencias). Ejecutar con: uvicorn server:app"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from adapters.agui_endpoint import create_app
from adapters.copilot_chat_model import CopilotChatModel, CopilotSettings, copilot_lifespan
from adapters.sqlite_wallet_repository import SqliteWalletRepository
from adapters.wallet_api_client import WalletApiClient
from domain.onboarding import DEFAULT_SESSION_TTL

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH_ENV = "WALLET_DB_PATH"
DEFAULT_DB_PATH = "wallet.db"

load_dotenv(BACKEND_DIR / ".env")

ttl = timedelta(seconds=int(os.environ["ONBOARDING_SESSION_TTL_SECONDS"])) if "ONBOARDING_SESSION_TTL_SECONDS" in os.environ else DEFAULT_SESSION_TTL

# Una ruta relativa se resuelve respecto a backend/, no al directorio desde el que se lanza uvicorn.
db_path = BACKEND_DIR / os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH)

# El cliente de Copilot se inicia al arrancar la aplicación y se cierra al apagarla.
model = CopilotChatModel(CopilotSettings.from_env())

app = create_app(
    WalletApiClient.from_env(), SqliteWalletRepository(db_path), model, ttl=ttl, lifespan=copilot_lifespan(model)
)
