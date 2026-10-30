from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from application.onboarding_service import OnboardingService, SessionExpiredError, WalletNotActivatedError
from domain.onboarding import InvalidTransitionError, OnboardingSession, OnboardingValidationError, Step
from ports.wallet_gateway import WalletGateway

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
NAME = {"nombre": "Ana", "apellidos": "Pérez"}
CONTACT = {"telefono": "999999999", "email": "ana@example.com"}
DNI = {"dni": "12345678"}
AMOUNT = {"monto_maximo": "300"}


def _ready_session(service: OnboardingService) -> OnboardingSession:
    session = service.submit_step(None, NAME, NOW)
    session = service.submit_step(session, CONTACT, NOW)
    session = service.submit_step(session, DNI, NOW)
    return service.submit_step(session, AMOUNT, NOW)


def test_gateway_double_satisfies_port(fake_gateway):
    assert isinstance(fake_gateway, WalletGateway)


def test_activation_calls_gateway_once_and_marks_session(fake_gateway):
    service = OnboardingService(fake_gateway)
    session = _ready_session(service)

    activation = service.activate(session, NOW)

    assert activation.wallet_id == "W-TEST-1"
    assert session.activated
    assert len(fake_gateway.requests) == 1
    request = fake_gateway.requests[0]
    assert request.dni == "12345678"
    assert request.monto_maximo == Decimal("300")
    assert request.moneda == "PEN"


def test_activation_before_final_step_does_not_call_gateway(fake_gateway):
    service = OnboardingService(fake_gateway)
    session = service.submit_step(None, NAME, NOW)

    with pytest.raises(InvalidTransitionError):
        service.activate(session, NOW)
    assert fake_gateway.requests == []


def test_rejected_activation_keeps_session_inactive(fake_gateway):
    fake_gateway.activated = False
    service = OnboardingService(fake_gateway)
    session = _ready_session(service)

    with pytest.raises(WalletNotActivatedError):
        service.activate(session, NOW)
    assert not session.activated


def test_expired_session_restarts_from_step_one(fake_gateway):
    service = OnboardingService(fake_gateway)
    session = service.submit_step(None, NAME, NOW)
    later = NOW + timedelta(minutes=6)

    restarted = service.resume(session, later)

    assert restarted.step is Step.NAME
    assert restarted.data == {}


def test_submit_after_expiration_is_validated_against_step_one(fake_gateway):
    service = OnboardingService(fake_gateway)
    session = service.submit_step(None, NAME, NOW)
    session = service.submit_step(session, CONTACT, NOW)
    with pytest.raises(OnboardingValidationError):
        service.submit_step(session, CONTACT, NOW + timedelta(minutes=6))


def test_activation_fails_when_session_expired(fake_gateway):
    service = OnboardingService(fake_gateway)
    session = _ready_session(service)

    with pytest.raises(SessionExpiredError):
        service.activate(session, NOW + timedelta(minutes=6))
    assert fake_gateway.requests == []
