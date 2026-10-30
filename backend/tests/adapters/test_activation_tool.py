from adapters.activation_tool import REGISTRY_ERROR_REASON, TOOL_NAME, build_activation_tool
from application.onboarding_service import OnboardingService

CONFIRMED_AT = "2026-10-30T12:00:00+00:00"
DATA = {
    "nombre": "Ana",
    "apellidos": "Pérez",
    "telefono": "999999999",
    "email": "ana@example.com",
    "dni": "12345678",
    "monto_maximo": "300",
}


def _invoke(tool):
    return tool.invoke({"data": DATA, "confirmed_at": CONFIRMED_AT})


def test_tool_has_expected_name_and_description(fake_gateway, fake_repository):
    tool = build_activation_tool(OnboardingService(fake_gateway, fake_repository))

    assert tool.name == TOOL_NAME == "activate_wallet"
    assert tool.description
    assert set(tool.args) == {"data", "confirmed_at"}


def test_successful_activation_returns_ids_and_saves_record(fake_gateway, fake_repository):
    tool = build_activation_tool(OnboardingService(fake_gateway, fake_repository))

    result = _invoke(tool)

    assert result == {"activated": True, "wallet_id": "W-TEST-1", "kyc_id": "KYC-TEST-1", "reason": None}
    assert [record.kyc_id for record in fake_repository.records] == ["KYC-TEST-1"]
    assert fake_gateway.requests[0].dni == "12345678"


def test_not_approved_returns_reason_without_activating(fake_gateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.status = "REJECTED"
    tool = build_activation_tool(OnboardingService(fake_gateway, fake_repository))

    result = _invoke(tool)

    assert result["activated"] is False
    assert result["reason"] == "REJECTED"


def test_api_unavailable_returns_reason_and_saves_nothing(fake_gateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.reason = "API_UNAVAILABLE"
    tool = build_activation_tool(OnboardingService(fake_gateway, fake_repository))

    result = _invoke(tool)

    assert result["activated"] is False and result["reason"] == "API_UNAVAILABLE"
    assert fake_repository.records == []


def test_persistence_failure_returns_registry_error(fake_gateway, fake_repository):
    fake_repository.fail = True
    tool = build_activation_tool(OnboardingService(fake_gateway, fake_repository))

    result = _invoke(tool)

    assert result == {"activated": False, "wallet_id": None, "kyc_id": None, "reason": REGISTRY_ERROR_REASON}
