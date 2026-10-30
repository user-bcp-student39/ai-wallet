from datetime import datetime, timedelta, timezone

from langgraph.types import Command

from adapters.langgraph_onboarding import SESSION_EXPIRED_MESSAGE, build_onboarding_graph, initial_state
from ports.wallet_gateway import WalletGateway

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
NAME = {"nombre": "Ana", "apellidos": "Pérez"}
CONTACT = {"telefono": "999999999", "email": "ana@example.com"}
DNI_VALID = {"dni": "12345678"}
AMOUNT = {"monto_maximo": "300"}


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _pending_step(result: dict) -> int:
    return result["__interrupt__"][0].value["step"]


def test_valid_flow_walks_all_steps_and_activates_wallet(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    config = _config("flujo-valido")

    result = graph.invoke(initial_state(), config)
    assert _pending_step(result) == 1
    for answer, expected_next in ((NAME, 2), (CONTACT, 3), (DNI_VALID, 4), (AMOUNT, 5)):
        result = graph.invoke(Command(resume=answer), config)
        assert _pending_step(result) == expected_next

    final = graph.invoke(Command(resume={"confirmar": True}), config)

    assert "__interrupt__" not in final
    assert final["activated"] is True
    assert final["wallet_id"] == "W-TEST-1"
    assert len(fake_gateway.requests) == 1


def test_invalid_dni_loops_back_to_same_step_with_error(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    config = _config("dni-invalido")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)
    graph.invoke(Command(resume=CONTACT), config)

    result = graph.invoke(Command(resume={"dni": "1234567"}), config)

    assert _pending_step(result) == 3
    assert result["errors"]
    assert result["activated"] is False
    assert fake_gateway.requests == []

    result = graph.invoke(Command(resume=DNI_VALID), config)
    assert _pending_step(result) == 4


def test_amount_step_shows_pen_currency(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    config = _config("moneda-pen")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)
    graph.invoke(Command(resume=CONTACT), config)
    result = graph.invoke(Command(resume=DNI_VALID), config)

    assert _pending_step(result) == 4
    assert result["__interrupt__"][0].value["moneda"] == "PEN"


def test_server_rejects_invalid_amount_sent_without_interface(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    config = _config("monto-invalido-servidor")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)
    graph.invoke(Command(resume=CONTACT), config)
    graph.invoke(Command(resume=DNI_VALID), config)

    result = graph.invoke(Command(resume={"monto_maximo": "501"}), config)

    assert _pending_step(result) == 4
    assert result["errors"]


def test_new_thread_id_starts_a_fresh_onboarding(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    graph.invoke(initial_state(), _config("hilo-A"))
    graph.invoke(Command(resume=NAME), _config("hilo-A"))

    result = graph.invoke(initial_state(), _config("hilo-B"))

    assert _pending_step(result) == 1
    assert graph.get_state(_config("hilo-A")).values["step"] == 2
    assert graph.get_state(_config("hilo-B")).values["data"] == {}


def test_activation_requires_confirmation(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    config = _config("sin-confirmar")
    graph.invoke(initial_state(), config)
    for answer in (NAME, CONTACT, DNI_VALID, AMOUNT):
        graph.invoke(Command(resume=answer), config)

    result = graph.invoke(Command(resume={"confirmar": False}), config)

    assert _pending_step(result) == 5
    assert fake_gateway.requests == []


def test_rejected_activation_ends_without_wallet(fake_gateway: WalletGateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.reason = "REJECTED"
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    config = _config("rechazada")
    graph.invoke(initial_state(), config)
    for answer in (NAME, CONTACT, DNI_VALID, AMOUNT):
        graph.invoke(Command(resume=answer), config)

    final = graph.invoke(Command(resume={"confirmar": True}), config)

    assert "__interrupt__" not in final
    assert final["activated"] is False
    assert final["reason"] == "REJECTED"


def _confirm_activation(graph, thread_id: str) -> dict:
    config = _config(thread_id)
    graph.invoke(initial_state(), config)
    for answer in (NAME, CONTACT, DNI_VALID, AMOUNT):
        graph.invoke(Command(resume=answer), config)
    return graph.invoke(Command(resume={"confirmar": True}), config)


def test_activation_saves_record_through_the_tool(fake_gateway: WalletGateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)

    final = _confirm_activation(graph, "registro-activo")

    assert final["activated"] is True
    assert [(r.kyc_id, r.wallet_id, r.state, r.max_amount) for r in fake_repository.records] == [
        ("KYC-TEST-1", "W-TEST-1", "ACTIVE", "300")
    ]


def test_non_active_verification_is_saved_but_wallet_stays_inactive(fake_gateway: WalletGateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.status = "PENDING"
    graph = build_onboarding_graph(fake_gateway, fake_repository)

    final = _confirm_activation(graph, "registro-pendiente")

    assert final["activated"] is False
    assert final["reason"] == "PENDING"
    assert [r.state for r in fake_repository.records] == ["PENDING"]


def test_unavailable_api_leaves_no_record(fake_gateway: WalletGateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.reason = "API_UNAVAILABLE"
    graph = build_onboarding_graph(fake_gateway, fake_repository)

    final = _confirm_activation(graph, "api-caida")

    assert final["activated"] is False
    assert final["reason"] == "API_UNAVAILABLE"
    assert fake_repository.records == []


def test_persistence_failure_ends_without_activation_and_logs_only_identifiers(
    fake_gateway: WalletGateway, fake_repository, caplog
):
    fake_repository.fail = True
    graph = build_onboarding_graph(fake_gateway, fake_repository)

    with caplog.at_level("ERROR"):
        final = _confirm_activation(graph, "fallo-guardado")

    assert final["activated"] is False
    assert final["wallet_id"] is None
    assert final["reason"] == "REGISTRY_ERROR"
    assert final["done"] is True
    assert "KYC-TEST-1" in caplog.text
    assert "12345678" not in caplog.text and "ana@example.com" not in caplog.text


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_default_ttl_restarts_at_step_one_when_answer_arrives_after_five_minutes(
    fake_gateway: WalletGateway, fake_repository
):
    clock = _Clock(T0)
    graph = build_onboarding_graph(fake_gateway, fake_repository, clock=clock)
    config = _config("ttl-defecto")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)

    clock.now = T0 + timedelta(minutes=5, seconds=1)
    result = graph.invoke(Command(resume=CONTACT), config)

    assert _pending_step(result) == 1
    assert result["errors"] == [{"field": None, "message": SESSION_EXPIRED_MESSAGE}]
    assert result["data"] == {}
    assert fake_gateway.requests == []


def test_progress_within_default_ttl_keeps_session(fake_gateway: WalletGateway, fake_repository):
    clock = _Clock(T0)
    graph = build_onboarding_graph(fake_gateway, fake_repository, clock=clock)
    config = _config("dentro-ttl")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)

    clock.now = T0 + timedelta(minutes=4, seconds=59)
    result = graph.invoke(Command(resume=CONTACT), config)

    assert _pending_step(result) == 3
    assert result["errors"] == []
    assert result["data"]["nombre"] == "Ana"


def test_configured_ttl_is_applied(fake_gateway: WalletGateway, fake_repository):
    clock = _Clock(T0)
    graph = build_onboarding_graph(fake_gateway, fake_repository, clock=clock, ttl=timedelta(minutes=1))
    config = _config("ttl-configurado")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)

    clock.now = T0 + timedelta(minutes=2)
    result = graph.invoke(Command(resume=CONTACT), config)

    assert _pending_step(result) == 1
    assert result["errors"] == [{"field": None, "message": SESSION_EXPIRED_MESSAGE}]


def test_onboarding_continues_normally_after_expired_restart(fake_gateway: WalletGateway, fake_repository):
    clock = _Clock(T0)
    graph = build_onboarding_graph(fake_gateway, fake_repository, clock=clock)
    config = _config("reinicio-continua")
    graph.invoke(initial_state(), config)
    graph.invoke(Command(resume=NAME), config)
    clock.now = T0 + timedelta(minutes=6)
    graph.invoke(Command(resume=CONTACT), config)

    result = graph.invoke(Command(resume=NAME), config)

    assert _pending_step(result) == 2
    assert result["errors"] == []
