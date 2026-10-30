"""Adaptador HTTP del puerto WalletGateway contra la API W1 (openspec/changes/archive/2026-10-30-onboarding-wallet-bajo-monto/external-api/openapi.yaml)."""

import hashlib
import hmac
import os

import httpx

from ports.wallet_gateway import WalletActivation, WalletActivationRequest

BASE_URL_ENV = "WALLET_API_BASE_URL"
DEFAULT_BASE_URL = "http://127.0.0.1:8787"
DOCUMENT_KEY_ENV = "WALLET_DOCUMENT_KEY"
KYC_PATH = "/kyc/verifications"
APPROVED_SCENARIO = "APPROVED"


def document_for(dni: str, key: bytes) -> str:
    """El contrato solo admite documentos TEST-; HMAC evita que el DNI sea recuperable por fuerza bruta."""
    digest = hmac.new(key, dni.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"TEST-{digest}"


class WalletApiClient:
    def __init__(self, http: httpx.Client, document_key: bytes) -> None:
        self._http = http
        self._document_key = document_key

    @classmethod
    def from_env(cls, transport: httpx.BaseTransport | None = None) -> "WalletApiClient":
        base_url = os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)
        document_key = os.environ.get(DOCUMENT_KEY_ENV)
        if not document_key:
            raise RuntimeError(f"Falta la variable de entorno {DOCUMENT_KEY_ENV} (clave HMAC del documento TEST)")
        return cls(
            httpx.Client(base_url=base_url, timeout=10.0, transport=transport),
            document_key.encode("utf-8"),
        )

    def activate_wallet(self, request: WalletActivationRequest) -> WalletActivation:
        payload = {
            "documentType": "TEST",
            "document": document_for(request.dni, self._document_key),
            "scenario": APPROVED_SCENARIO,
        }
        try:
            response = self._http.post(KYC_PATH, json=payload)
        except httpx.TransportError:
            return WalletActivation(activated=False, reason="API_UNAVAILABLE")

        body = response.json() if response.content else {}
        if not response.is_success:
            return WalletActivation(activated=False, reason=body.get("error", "HTTP_ERROR"))

        if body.get("status") == "ACTIVE":
            return WalletActivation(
                activated=True, wallet_id=body["wallet_id"], kyc_id=body.get("id"), status="ACTIVE"
            )
        status = body.get("status")
        return WalletActivation(
            activated=False,
            wallet_id=body.get("wallet_id"),
            reason=status or "NOT_ACTIVE",
            kyc_id=body.get("id"),
            status=status,
        )
