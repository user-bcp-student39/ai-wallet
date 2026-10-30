"""Puerto de salida hacia el almacén persistente de wallets. El núcleo solo conoce este contrato."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

DEFAULT_DOCUMENT_TYPE = "TEST"


@dataclass(frozen=True)
class WalletRecord:
    """Resultado de una verificación KYC con los datos del titular. `state` es el estado devuelto por la API."""

    kyc_id: str
    wallet_id: str
    state: str
    document_number: str
    name: str
    last_name: str
    phone: str
    email: str
    max_amount: str
    document_type: str = DEFAULT_DOCUMENT_TYPE


@runtime_checkable
class WalletRepository(Protocol):
    def save(self, record: WalletRecord) -> None:
        """Guarda el registro. Debe lanzar WalletPersistenceError si no puede persistirlo."""
        ...
