import pytest

from ports.wallet_gateway import WalletActivation


class FakeWalletGateway:
    def __init__(self, activated: bool = True, reason: str | None = None) -> None:
        self.activated = activated
        self.reason = reason
        self.requests: list = []

    def activate_wallet(self, request):
        self.requests.append(request)
        if self.activated:
            return WalletActivation(activated=True, wallet_id="W-TEST-1")
        return WalletActivation(activated=False, reason=self.reason or "KYC rechazado")


@pytest.fixture
def fake_gateway() -> FakeWalletGateway:
    return FakeWalletGateway()
