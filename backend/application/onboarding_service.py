"""Casos de uso del onboarding. Depende solo del dominio y del puerto WalletGateway."""

from datetime import datetime, timedelta
from typing import Any, Mapping

from domain.onboarding import DEFAULT_SESSION_TTL, OnboardingSession
from ports.wallet_gateway import WalletActivation, WalletActivationRequest, WalletGateway


class SessionExpiredError(RuntimeError):
    """La sesión expiró; el onboarding debe reiniciarse desde el paso 1."""


class WalletNotActivatedError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class OnboardingService:
    def __init__(self, gateway: WalletGateway, session_ttl: timedelta = DEFAULT_SESSION_TTL) -> None:
        self._gateway = gateway
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
        if not activation.activated:
            raise WalletNotActivatedError(activation.reason or "La wallet no pudo activarse.")
        session.mark_activated(now)
        return activation
