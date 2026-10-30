"""Máquina de estados del onboarding de wallet. Sin dependencias de framework."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import IntEnum
from typing import Any, Mapping

MAX_OPERATION_AMOUNT_PEN = Decimal("500")
DEFAULT_CURRENCY = "PEN"
DEFAULT_SESSION_TTL = timedelta(minutes=5)
_DNI_PATTERN = re.compile(r"[0-9]{8}")
_TEXT_LABELS = {
    "nombre": "nombre",
    "apellidos": "apellidos",
    "telefono": "teléfono",
    "email": "email",
}


class Step(IntEnum):
    NAME = 1
    CONTACT = 2
    DNI = 3
    MAX_AMOUNT = 4
    ACTIVATION = 5


STEP_FIELDS: dict[Step, tuple[str, ...]] = {
    Step.NAME: ("nombre", "apellidos"),
    Step.CONTACT: ("telefono", "email"),
    Step.DNI: ("dni",),
    Step.MAX_AMOUNT: ("monto_maximo",),
    Step.ACTIVATION: (),
}
DATA_STEPS = (Step.NAME, Step.CONTACT, Step.DNI, Step.MAX_AMOUNT)


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


class OnboardingValidationError(ValueError):
    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__("; ".join(error.message for error in errors))
        self.errors = tuple(errors)


class InvalidTransitionError(RuntimeError):
    """La operación no está permitida en el paso actual."""


def _clean_text(name: str, value: Any, errors: list[FieldError]) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        errors.append(FieldError(name, f"El campo {_TEXT_LABELS[name]} es obligatorio."))
    return text


def _clean_dni(value: Any, errors: list[FieldError]) -> str:
    if not isinstance(value, str) or not value:
        errors.append(FieldError("dni", "El DNI es obligatorio."))
        return ""
    if not _DNI_PATTERN.fullmatch(value):
        errors.append(FieldError("dni", "El DNI debe tener exactamente 8 dígitos numéricos."))
    return value


def _clean_max_amount(value: Any, errors: list[FieldError]) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(FieldError("monto_maximo", "El monto máximo es obligatorio."))
        return None
    amount: Decimal | None = None
    if not isinstance(value, bool):
        try:
            candidate = Decimal(str(value).strip())
        except InvalidOperation:
            candidate = None
        if candidate is not None and candidate.is_finite():
            amount = candidate
    if amount is None or not (0 < amount <= MAX_OPERATION_AMOUNT_PEN):
        errors.append(
            FieldError(
                "monto_maximo",
                f"El monto máximo debe ser mayor que 0 y no superar {MAX_OPERATION_AMOUNT_PEN} PEN.",
            )
        )
        return None
    return amount


def validate_step(step: Step, values: Mapping[str, Any]) -> dict[str, Any]:
    """Valida los campos de un paso y devuelve los valores normalizados."""
    errors: list[FieldError] = []
    cleaned: dict[str, Any] = {}
    for name in STEP_FIELDS[step]:
        raw = values.get(name)
        if name == "dni":
            cleaned[name] = _clean_dni(raw, errors)
        elif name == "monto_maximo":
            cleaned[name] = _clean_max_amount(raw, errors)
        else:
            cleaned[name] = _clean_text(name, raw, errors)
    if errors:
        raise OnboardingValidationError(errors)
    return cleaned


@dataclass
class OnboardingSession:
    step: Step
    data: dict[str, Any]
    last_progress_at: datetime
    currency: str = DEFAULT_CURRENCY
    activated: bool = False

    @classmethod
    def start(cls, now: datetime) -> "OnboardingSession":
        return cls(step=Step.NAME, data={}, last_progress_at=now)

    def is_expired(self, now: datetime, ttl: timedelta = DEFAULT_SESSION_TTL) -> bool:
        return now - self.last_progress_at > ttl

    def submit(self, values: Mapping[str, Any], now: datetime) -> None:
        """Valida el paso actual y avanza solo si es válido."""
        if self.step is Step.ACTIVATION or self.activated:
            raise InvalidTransitionError("El onboarding ya está en el paso de activación.")
        self.data.update(validate_step(self.step, values))
        self.step = Step(self.step + 1)
        self.last_progress_at = now

    def complete_data(self) -> dict[str, Any]:
        """Revalida todos los pasos antes de activar; no confía en el estado previo."""
        if self.step is not Step.ACTIVATION or self.activated:
            raise InvalidTransitionError("La wallet solo puede activarse en el paso de activación.")
        collected: dict[str, Any] = {}
        for step in DATA_STEPS:
            collected.update(validate_step(step, self.data))
        collected["moneda"] = self.currency
        return collected

    def mark_activated(self, now: datetime) -> None:
        if self.step is not Step.ACTIVATION or self.activated:
            raise InvalidTransitionError("La wallet solo puede activarse una vez, en el paso de activación.")
        self.activated = True
        self.last_progress_at = now
