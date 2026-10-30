import pytest

from application.onboarding_service import WalletPersistenceError
from ports.conversational_model import ModelUnavailableError
from ports.wallet_gateway import WalletActivation
from ports.wallet_repository import WalletRecord


class FakeWalletGateway:
    """Con `status` simula una verificación respondida por la API; sin él, una API sin respuesta útil."""

    def __init__(self, activated: bool = True, reason: str | None = None, status: str | None = None) -> None:
        self.activated = activated
        self.reason = reason
        self.status = status
        self.requests: list = []

    def activate_wallet(self, request):
        self.requests.append(request)
        if self.activated:
            return WalletActivation(activated=True, wallet_id="W-TEST-1", kyc_id="KYC-TEST-1", status="ACTIVE")
        if self.status:
            return WalletActivation(
                activated=False, wallet_id="W-TEST-2", reason=self.status, kyc_id="KYC-TEST-2", status=self.status
            )
        return WalletActivation(activated=False, reason=self.reason or "KYC rechazado")


class FakeWalletRepository:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.records: list[WalletRecord] = []

    def save(self, record: WalletRecord) -> None:
        if self.fail:
            raise WalletPersistenceError("almacén no disponible")
        self.records.append(record)

    def find(self, kyc_id: str) -> WalletRecord | None:
        if self.fail:
            raise WalletPersistenceError("almacén no disponible")
        return next((record for record in self.records if record.kyc_id == kyc_id), None)


class FakeConversationalModel:
    """Devuelve las respuestas en orden (repite la última) y guarda las llamadas para inspeccionarlas."""

    def __init__(self, *replies: str, fail: bool = False) -> None:
        self.replies = list(replies) or ['{"intent": "chat", "reply": "Hola."}']
        self.fail = fail
        self.calls: list[tuple[str, list]] = []

    async def complete(self, system, messages):
        self.calls.append((system, list(messages)))
        if self.fail:
            raise ModelUnavailableError("sin modelo")
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


@pytest.fixture
def fake_gateway() -> FakeWalletGateway:
    return FakeWalletGateway()


@pytest.fixture
def fake_repository() -> FakeWalletRepository:
    return FakeWalletRepository()


@pytest.fixture
def fake_model() -> FakeConversationalModel:
    return FakeConversationalModel()
