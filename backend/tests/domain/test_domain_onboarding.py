import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from domain.onboarding import (
    DEFAULT_SESSION_TTL,
    InvalidTransitionError,
    OnboardingSession,
    OnboardingValidationError,
    Step,
    validate_step,
)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
VALID_BY_STEP = {
    Step.NAME: {"nombre": "Ana", "apellidos": "Pérez"},
    Step.CONTACT: {"telefono": "999999999", "email": "ana@example.com"},
    Step.DNI: {"dni": "12345678"},
    Step.MAX_AMOUNT: {"monto_maximo": "300"},
}


def _completed_session() -> OnboardingSession:
    session = OnboardingSession.start(NOW)
    for step in (Step.NAME, Step.CONTACT, Step.DNI, Step.MAX_AMOUNT):
        session.submit(VALID_BY_STEP[step], NOW)
    return session


@pytest.mark.parametrize("dni", ["1234567", "1234567A", "123456789", " 12345678", "", None])
def test_dni_rejects_anything_but_exactly_eight_digits(dni):
    with pytest.raises(OnboardingValidationError):
        validate_step(Step.DNI, {"dni": dni})


def test_dni_accepts_exactly_eight_digits():
    assert validate_step(Step.DNI, {"dni": "12345678"}) == {"dni": "12345678"}


@pytest.mark.parametrize("amount", ["300", 500, "0.01", 300])
def test_max_amount_accepts_values_in_range(amount):
    assert validate_step(Step.MAX_AMOUNT, {"monto_maximo": amount})["monto_maximo"] == Decimal(str(amount))


@pytest.mark.parametrize("amount", [0, "0", -1, 501, "abc", "NaN", True, "", None])
def test_max_amount_rejects_values_outside_range(amount):
    with pytest.raises(OnboardingValidationError):
        validate_step(Step.MAX_AMOUNT, {"monto_maximo": amount})


def test_empty_name_blocks_step_and_keeps_current_step():
    session = OnboardingSession.start(NOW)
    with pytest.raises(OnboardingValidationError) as excinfo:
        session.submit({"nombre": "  ", "apellidos": "Pérez"}, NOW)
    assert session.step is Step.NAME
    assert [error.field for error in excinfo.value.errors] == ["nombre"]


@pytest.mark.parametrize(
    ("step", "field"),
    [
        (Step.NAME, "nombre"),
        (Step.NAME, "apellidos"),
        (Step.CONTACT, "telefono"),
        (Step.CONTACT, "email"),
        (Step.DNI, "dni"),
    ],
)
def test_empty_required_field_blocks_step(step, field):
    session = OnboardingSession.start(NOW)
    for previous in [s for s in (Step.NAME, Step.CONTACT, Step.DNI) if s < step]:
        session.submit(VALID_BY_STEP[previous], NOW)
    values = {**VALID_BY_STEP[step], field: ""}

    with pytest.raises(OnboardingValidationError) as excinfo:
        session.submit(values, NOW)

    assert session.step is step
    assert [error.field for error in excinfo.value.errors] == [field]


def test_valid_step_advances_to_next():
    session = OnboardingSession.start(NOW)
    session.submit(VALID_BY_STEP[Step.NAME], NOW)
    assert session.step is Step.CONTACT


def test_session_expires_after_default_ttl_of_five_minutes():
    session = OnboardingSession.start(NOW)
    assert DEFAULT_SESSION_TTL == timedelta(minutes=5)
    assert not session.is_expired(NOW + timedelta(minutes=5))
    assert session.is_expired(NOW + timedelta(minutes=5, seconds=1))


def test_session_expiration_accepts_configured_ttl():
    session = OnboardingSession.start(NOW)
    assert session.is_expired(NOW + timedelta(minutes=2), ttl=timedelta(minutes=1))


def test_activation_is_not_allowed_before_final_step():
    session = OnboardingSession.start(NOW)
    with pytest.raises(InvalidTransitionError):
        session.mark_activated(NOW)


def test_complete_data_revalidates_and_defaults_currency_to_pen():
    session = _completed_session()
    assert session.complete_data() == {
        "nombre": "Ana",
        "apellidos": "Pérez",
        "telefono": "999999999",
        "email": "ana@example.com",
        "dni": "12345678",
        "monto_maximo": Decimal("300"),
        "moneda": "PEN",
    }


def test_wallet_can_only_be_activated_once():
    session = _completed_session()
    session.mark_activated(NOW)
    assert session.activated
    with pytest.raises(InvalidTransitionError):
        session.mark_activated(NOW)


def test_core_does_not_import_framework_modules():
    code = (
        "import sys, domain.onboarding, application.onboarding_service, ports.wallet_gateway; "
        "print(sorted(m for m in ('fastapi', 'langgraph', 'httpx') if m in sys.modules))"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "[]"
