"""Casos de uso del onboarding. Depende solo del dominio y de los puertos WalletGateway y WalletRepository."""

import logging
from datetime import datetime, timedelta
from typing import Any, Mapping

from domain.onboarding import DEFAULT_SESSION_TTL, OnboardingSession
from ports.wallet_gateway import WalletActivation, WalletActivationRequest, WalletGateway
from ports.wallet_repository import WalletRecord, WalletRepository

logger = logging.getLogger(__name__)


class SessionExpiredError(RuntimeError):
    """La sesión expiró; el onboarding debe reiniciarse desde el paso 1."""


class WalletPersistenceError(RuntimeError):
    """El resultado de la verificación no pudo guardarse en el almacén persistente."""


class WalletNotActivatedError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OnboardingService:
    def __init__(
        self, gateway: WalletGateway, repository: WalletRepository, session_ttl: timedelta = DEFAULT_SESSION_TTL
    ) -> None:
        self._gateway = gateway
        self._repository = repository
        self._session_ttl = session_ttl

    def resume(self, session: OnboardingSession | None, now: datetime) -> OnboardingSession:
        """Devuelve la sesión vigente o una nueva si no existe o expiró."""
        if session is None or session.is_expired(now, self._session_ttl):
            return OnboardingSession.start(now)
        return session

    def submit_step(
        self, session: OnboardingSession | None, values: Mapping[str, Any], now: datetime
    ) -> OnboardingSession:
        current = self.resume(session, now)
        current.submit(values, now)
        return current

    def activate(self, session: OnboardingSession, now: datetime) -> WalletActivation:
        if session.is_expired(now, self._session_ttl):
            raise SessionExpiredError("La sesión de onboarding expiró; reinicia el proceso.")
        collected = session.complete_data()
        activation = self._gateway.activate_wallet(WalletActivationRequest(**collected))
        self._register(collected, activation)
        if not activation.activated:
            raise WalletNotActivatedError(activation.reason or "La wallet no pudo activarse.")
        session.mark_activated(now)
        return activation

    def _register(self, collected: Mapping[str, Any], activation: WalletActivation) -> None:
        """Guarda la verificación con cualquier estado; sin kyc_id o wallet_id no hay registro posible."""
        if not (activation.kyc_id and activation.wallet_id and activation.status):
            return
        try:
            self._repository.save(
                WalletRecord(
                    kyc_id=activation.kyc_id,
                    wallet_id=activation.wallet_id,
                    state=activation.status,
                    document_number=collected["dni"],
                    name=collected["nombre"],
                    last_name=collected["apellidos"],
                    phone=collected["telefono"],
                    email=collected["email"],
                    max_amount=format(collected["monto_maximo"], "f"),
                )
            )
        except WalletPersistenceError:
            # Solo identificadores de la verificación: permiten reconciliar la wallet creada en la API sin exponer datos personales.
            logger.error("No se pudo registrar la verificación kyc_id=%s wallet_id=%s", activation.kyc_id, activation.wallet_id)
            raise
