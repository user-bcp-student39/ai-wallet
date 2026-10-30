import pytest

from application.onboarding_service import WalletPersistenceError
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


@pytest.fixture
def fake_gateway() -> FakeWalletGateway:
    return FakeWalletGateway()


@pytest.fixture
def fake_repository() -> FakeWalletRepository:
    return FakeWalletRepository()
