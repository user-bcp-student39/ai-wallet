import json
from decimal import Decimal

import httpx
import pytest

from adapters.wallet_api_client import BASE_URL_ENV, DOCUMENT_KEY_ENV, WalletApiClient, document_for
from ports.wallet_gateway import WalletActivationRequest

TEST_KEY = b"clave-de-prueba"

REQUEST = WalletActivationRequest(
    nombre="Ana",
    apellidos="Pérez",
    telefono="999999999",
    email="ana@example.com",
    dni="12345678",
    monto_maximo=Decimal("300"),
    moneda="PEN",
)


def _client(handler) -> tuple[WalletApiClient, list[dict]]:
    sent: list[dict] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return handler(request)

    http = httpx.Client(base_url="http://wallet.test", transport=httpx.MockTransport(wrapped))
    return WalletApiClient(http, TEST_KEY), sent


def test_approved_verification_activates_wallet_and_sends_only_test_document():
    client, sent = _client(
        lambda request: httpx.Response(
            201, json={"id": "kyc-1", "wallet_id": "W-1", "scenario": "APPROVED", "status": "ACTIVE"}
        )
    )

    activation = client.activate_wallet(REQUEST)

    assert activation.activated and activation.wallet_id == "W-1"
    assert activation.kyc_id == "kyc-1"
    assert activation.status == "ACTIVE"
    payload = sent[0]
    assert payload["documentType"] == "TEST"
    assert payload["document"].startswith("TEST-")
    assert payload["scenario"] == "APPROVED"
    assert "12345678" not in json.dumps(payload)
    assert "Ana" not in json.dumps(payload)


def test_rejected_verification_does_not_activate():
    client, _ = _client(
        lambda request: httpx.Response(
            201, json={"id": "kyc-2", "wallet_id": "W-2", "scenario": "REJECTED", "status": "REJECTED"}
        )
    )

    activation = client.activate_wallet(REQUEST)

    assert not activation.activated
    assert activation.reason == "REJECTED"


@pytest.mark.parametrize("status", ["PENDING", "REJECTED"])
def test_non_active_status_still_returns_kyc_wallet_and_status(status):
    client, _ = _client(
        lambda request: httpx.Response(
            201, json={"id": "kyc-9", "wallet_id": "W-9", "scenario": "MANUAL_REVIEW", "status": status}
        )
    )

    activation = client.activate_wallet(REQUEST)

    assert not activation.activated
    assert (activation.kyc_id, activation.wallet_id, activation.status) == ("kyc-9", "W-9", status)


def test_error_without_verification_body_has_no_kyc_id():
    client, _ = _client(lambda request: httpx.Response(503, json={"error": "KYC_UNAVAILABLE"}))

    activation = client.activate_wallet(REQUEST)

    assert activation.kyc_id is None and activation.status is None


def test_empty_error_body_has_no_kyc_id():
    client, _ = _client(lambda request: httpx.Response(500))

    activation = client.activate_wallet(REQUEST)

    assert not activation.activated
    assert activation.kyc_id is None


def test_kyc_unavailable_returns_error_code_as_reason():
    client, _ = _client(lambda request: httpx.Response(503, json={"error": "KYC_UNAVAILABLE"}))

    activation = client.activate_wallet(REQUEST)

    assert not activation.activated
    assert activation.reason == "KYC_UNAVAILABLE"


def test_connection_failure_does_not_activate():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client, _ = _client(refuse)

    activation = client.activate_wallet(REQUEST)

    assert not activation.activated
    assert activation.reason == "API_UNAVAILABLE"
    assert activation.kyc_id is None


def test_test_document_is_deterministic_and_hides_dni():
    assert document_for("12345678", TEST_KEY) == document_for("12345678", TEST_KEY)
    assert document_for("12345678", TEST_KEY) != document_for("87654321", TEST_KEY)
    assert "12345678" not in document_for("12345678", TEST_KEY)


def test_test_document_depends_on_secret_key():
    assert document_for("12345678", b"otra-clave") != document_for("12345678", TEST_KEY)


def test_base_url_is_read_from_environment(monkeypatch):
    monkeypatch.setenv(BASE_URL_ENV, "http://api.example.test")
    monkeypatch.setenv(DOCUMENT_KEY_ENV, "clave")
    client = WalletApiClient.from_env(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert str(client._http.base_url) == "http://api.example.test"


def test_base_url_defaults_to_openapi_server(monkeypatch):
    monkeypatch.delenv(BASE_URL_ENV, raising=False)
    monkeypatch.setenv(DOCUMENT_KEY_ENV, "clave")
    client = WalletApiClient.from_env(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert str(client._http.base_url) == "http://127.0.0.1:8787"


def test_from_env_requires_document_key(monkeypatch):
    monkeypatch.delenv(DOCUMENT_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match=DOCUMENT_KEY_ENV):
        WalletApiClient.from_env()
