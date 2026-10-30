"""Puerto de salida hacia la API de wallet. El núcleo solo conoce este contrato."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class WalletActivationRequest:
    nombre: str
    apellidos: str
    telefono: str
    email: str
    dni: str
    monto_maximo: Decimal
    moneda: str


@dataclass(frozen=True)
class WalletActivation:
    activated: bool
    wallet_id: str | None = None
    reason: str | None = None


@runtime_checkable
class WalletGateway(Protocol):
    def activate_wallet(self, request: WalletActivationRequest) -> WalletActivation: ...
