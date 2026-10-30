"""Puerto de salida que enlaza una sesión (hilo) con la wallet registrada en ella."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SessionWalletLookup(Protocol):
    def kyc_id_for(self, thread_id: str) -> str | None:
        """Devuelve el kyc_id del registro de esa sesión, o None si la sesión no tiene registro."""
        ...
