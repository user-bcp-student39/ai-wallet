from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from application.onboarding_service import (
    OnboardingService,
    SessionExpiredError,
    WalletNotActivatedError,
    WalletPersistenceError,
)
from domain.onboarding import InvalidTransitionError, OnboardingSession, OnboardingValidationError, Step
from ports.wallet_gateway import WalletGateway
from ports.wallet_repository import WalletRecord, WalletRepository

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


def test_repository_double_satisfies_port(fake_repository):
    assert isinstance(fake_repository, WalletRepository)


def test_activation_calls_gateway_once_and_marks_session(fake_gateway, fake_repository):
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    activation = service.activate(session, NOW)

    assert activation.wallet_id == "W-TEST-1"
    assert session.activated
    assert len(fake_gateway.requests) == 1
    request = fake_gateway.requests[0]
    assert request.dni == "12345678"
    assert request.monto_maximo == Decimal("300")
    assert request.moneda == "PEN"


def test_activation_before_final_step_does_not_call_gateway(fake_gateway, fake_repository):
    service = OnboardingService(fake_gateway, fake_repository)
    session = service.submit_step(None, NAME, NOW)

    with pytest.raises(InvalidTransitionError):
        service.activate(session, NOW)
    assert fake_gateway.requests == []
    assert fake_repository.records == []


def test_rejected_activation_keeps_session_inactive(fake_gateway, fake_repository):
    fake_gateway.activated = False
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    with pytest.raises(WalletNotActivatedError):
        service.activate(session, NOW)
    assert not session.activated


def test_expired_session_restarts_from_step_one(fake_gateway, fake_repository):
    service = OnboardingService(fake_gateway, fake_repository)
    session = service.submit_step(None, NAME, NOW)
    later = NOW + timedelta(minutes=6)

    restarted = service.resume(session, later)

    assert restarted.step is Step.NAME
    assert restarted.data == {}


def test_submit_after_expiration_is_validated_against_step_one(fake_gateway, fake_repository):
    service = OnboardingService(fake_gateway, fake_repository)
    session = service.submit_step(None, NAME, NOW)
    session = service.submit_step(session, CONTACT, NOW)
    with pytest.raises(OnboardingValidationError):
        service.submit_step(session, CONTACT, NOW + timedelta(minutes=6))


def test_activation_fails_when_session_expired(fake_gateway, fake_repository):
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    with pytest.raises(SessionExpiredError):
        service.activate(session, NOW + timedelta(minutes=6))
    assert fake_gateway.requests == []
    assert fake_repository.records == []


def test_successful_activation_saves_active_record_with_owner_data(fake_gateway, fake_repository):
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    service.activate(session, NOW)

    assert fake_repository.records == [
        WalletRecord(
            kyc_id="KYC-TEST-1",
            wallet_id="W-TEST-1",
            state="ACTIVE",
            document_number="12345678",
            document_type="TEST",
            name="Ana",
            last_name="Pérez",
            phone="999999999",
            email="ana@example.com",
            max_amount="300",
        )
    ]


@pytest.mark.parametrize("status", ["PENDING", "REJECTED"])
def test_non_active_verification_is_saved_with_its_state_but_does_not_activate(fake_gateway, fake_repository, status):
    fake_gateway.activated = False
    fake_gateway.status = status
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    with pytest.raises(WalletNotActivatedError) as error:
        service.activate(session, NOW)

    assert not session.activated
    assert error.value.kyc_id == "KYC-TEST-2"
    assert [record.state for record in fake_repository.records] == [status]
    assert fake_repository.records[0].kyc_id == "KYC-TEST-2"


def test_unavailable_api_saves_nothing(fake_gateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.reason = "API_UNAVAILABLE"
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    with pytest.raises(WalletNotActivatedError) as error:
        service.activate(session, NOW)

    assert error.value.kyc_id is None
    assert fake_repository.records == []


@pytest.mark.parametrize("status", [None, "PENDING"])
def test_persistence_failure_is_propagated_and_session_stays_inactive(fake_gateway, fake_repository, status):
    fake_repository.fail = True
    if status:
        fake_gateway.activated = False
        fake_gateway.status = status
    service = OnboardingService(fake_gateway, fake_repository)
    session = _ready_session(service)

    with pytest.raises(WalletPersistenceError):
        service.activate(session, NOW)

    assert not session.activated
