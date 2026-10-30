"""Tool de LangChain que activa la wallet. Envuelve el caso de uso; el grafo no conoce el gateway ni el repositorio."""

from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool, tool

from application.onboarding_service import OnboardingService, WalletNotActivatedError, WalletPersistenceError
from domain.onboarding import OnboardingSession, Step

TOOL_NAME = "activate_wallet"
REGISTRY_ERROR_REASON = "REGISTRY_ERROR"


def build_activation_tool(service: OnboardingService) -> BaseTool:
    @tool(TOOL_NAME)
    def activate_wallet(data: dict[str, str], confirmed_at: str) -> dict[str, Any]:
        """Activa la wallet: verifica el KYC con la API externa y registra el resultado.

        Args:
            data: datos del onboarding (nombre, apellidos, telefono, email, dni, monto_maximo).
            confirmed_at: instante en que el usuario confirmó la activación, en ISO 8601.

        Returns:
            activated, wallet_id, kyc_id y reason (motivo cuando no se activa, si no es None).
            kyc_id identifica el registro guardado, también cuando la wallet no se activa; es None si no hay registro.
        """
        now = datetime.fromisoformat(confirmed_at)
        session = OnboardingSession(step=Step.ACTIVATION, data=dict(data), last_progress_at=now)
        try:
            activation = service.activate(session, now)
        except WalletNotActivatedError as exc:
            return {"activated": False, "wallet_id": None, "kyc_id": exc.kyc_id, "reason": exc.reason}
        except WalletPersistenceError:
            return {"activated": False, "wallet_id": None, "kyc_id": None, "reason": REGISTRY_ERROR_REASON}
        return {
            "activated": activation.activated,
            "wallet_id": activation.wallet_id,
            "kyc_id": activation.kyc_id,
            "reason": None,
        }

    return activate_wallet
