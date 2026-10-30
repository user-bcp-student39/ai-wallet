from langgraph.types import Command

from adapters.langgraph_onboarding import build_onboarding_graph, initial_state
from adapters.onboarding_session_lookup import OnboardingSessionLookup
from ports.session_wallet_lookup import SessionWalletLookup

ANSWERS = (
    {"nombre": "Ana", "apellidos": "Pérez"},
    {"telefono": "999999999", "email": "ana@example.com"},
    {"dni": "12345678"},
    {"monto_maximo": "300"},
)


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _answer_steps(graph, thread_id: str, confirm: bool) -> None:
    graph.invoke(initial_state(), _config(thread_id))
    for answer in ANSWERS:
        graph.invoke(Command(resume=answer), _config(thread_id))
    if confirm:
        graph.invoke(Command(resume={"confirmar": True}), _config(thread_id))


def test_lookup_satisfies_port(fake_gateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)

    assert isinstance(OnboardingSessionLookup(graph), SessionWalletLookup)


def test_session_with_active_verification_resolves_its_kyc_id(fake_gateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    _answer_steps(graph, "sesion-activa", confirm=True)

    assert OnboardingSessionLookup(graph).kyc_id_for("sesion-activa") == "KYC-TEST-1"


def test_session_with_pending_verification_resolves_its_kyc_id(fake_gateway, fake_repository):
    fake_gateway.activated = False
    fake_gateway.status = "PENDING"
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    _answer_steps(graph, "sesion-pendiente", confirm=True)

    assert OnboardingSessionLookup(graph).kyc_id_for("sesion-pendiente") == "KYC-TEST-2"


def test_session_that_did_not_finish_onboarding_has_no_kyc_id(fake_gateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    _answer_steps(graph, "sesion-a-medias", confirm=False)

    assert OnboardingSessionLookup(graph).kyc_id_for("sesion-a-medias") is None


def test_unknown_thread_has_no_kyc_id(fake_gateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)

    assert OnboardingSessionLookup(graph).kyc_id_for("hilo-que-no-existe") is None


def test_each_session_resolves_only_its_own_kyc_id(fake_gateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    _answer_steps(graph, "sesion-1", confirm=True)
    _answer_steps(graph, "sesion-2", confirm=False)
    lookup = OnboardingSessionLookup(graph)

    assert lookup.kyc_id_for("sesion-1") == "KYC-TEST-1"
    assert lookup.kyc_id_for("sesion-2") is None
