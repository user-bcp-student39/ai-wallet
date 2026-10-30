import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from adapters.langgraph_assistant import (
    FALLBACK_REPLY,
    HISTORY_LIMIT,
    LOOKUP_ERROR_MESSAGE,
    SYSTEM_PROMPT,
    UNAVAILABLE_MESSAGE,
    build_assistant_graph,
    parse_model_reply,
)
from adapters.langgraph_onboarding import build_onboarding_graph, initial_state
from adapters.onboarding_session_lookup import OnboardingSessionLookup
from adapters.wallet_data_tool import build_wallet_data_tool
from application.wallet_data_message import DATA_INTRO, NO_DATA_MESSAGE
from conftest import FakeConversationalModel as FakeModel
from ports.conversational_model import ConversationalModel

SHOW = '{"intent": "show_my_data", "reply": "RESPUESTA-DEL-MODELO-QUE-NO-SE-MUESTRA"}'
PERSONAL_VALUES = ("12345678", "Ana", "999999999", "ana@example.com", "W-TEST-1")
ANSWERS = (
    {"nombre": "Ana", "apellidos": "Pérez"},
    {"telefono": "999999999", "email": "ana@example.com"},
    {"dni": "12345678"},
    {"monto_maximo": "300"},
)


@pytest.fixture
def onboarding(fake_gateway, fake_repository):
    graph = build_onboarding_graph(fake_gateway, fake_repository)
    return graph, OnboardingSessionLookup(graph)


def _activate(graph, thread_id: str) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(initial_state(), config)
    for answer in ANSWERS:
        graph.invoke(Command(resume=answer), config)
    graph.invoke(Command(resume={"confirmar": True}), config)


def _assistant(model, fake_repository, lookup):
    return build_assistant_graph(model, build_wallet_data_tool(fake_repository, lookup))


def _say(graph, thread_id: str, *messages):
    return asyncio.run(graph.ainvoke({"messages": list(messages)}, {"configurable": {"thread_id": thread_id}}))


def _last(result) -> AIMessage:
    return result["messages"][-1]


def test_model_double_satisfies_port():
    assert isinstance(FakeModel("x"), ConversationalModel)


def test_chat_question_gets_the_model_reply_and_the_system_prompt(fake_repository, onboarding):
    model = FakeModel('{"intent": "chat", "reply": "Son 5 pasos."}')
    graph = _assistant(model, fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("¿Cuántos pasos tiene el onboarding?"))

    assert _last(result).content == "Son 5 pasos."
    system, messages = model.calls[0]
    assert system == SYSTEM_PROMPT
    assert [(m.role, m.content) for m in messages] == [("user", "¿Cuántos pasos tiene el onboarding?")]


def test_show_my_data_displays_the_nine_fields_without_kyc_id_and_ignores_the_model_text(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-1")
    graph = _assistant(FakeModel(SHOW), fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("¿Cuáles son mis datos registrados?"))

    message = _last(result)
    assert message.content.startswith(DATA_INTRO)
    assert len(message.content.splitlines()) == 10
    for value in PERSONAL_VALUES:
        assert value in message.content
    assert "KYC-TEST-1" not in message.content
    assert "RESPUESTA-DEL-MODELO" not in message.content
    assert message.additional_kwargs["redacted"] is True


def test_show_my_data_with_pending_verification_shows_that_state(fake_gateway, fake_repository, onboarding):
    fake_gateway.activated = False
    fake_gateway.status = "PENDING"
    _activate(onboarding[0], "hilo-1")
    graph = _assistant(FakeModel(SHOW), fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("mis datos"))

    assert "- Estado: PENDING" in _last(result).content


def test_show_my_data_without_registration_says_there_is_no_data(fake_repository, onboarding):
    graph = _assistant(FakeModel(SHOW), fake_repository, onboarding[1])

    result = _say(graph, "sesion-nueva", HumanMessage("mis datos"))

    assert _last(result).content == NO_DATA_MESSAGE


def test_request_for_another_persons_dni_only_ever_shows_the_session_data(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-1")
    lookup = onboarding[1]
    asked: list[str] = []
    original = lookup.kyc_id_for
    lookup.kyc_id_for = lambda thread_id: (asked.append(thread_id), original(thread_id))[1]
    graph = _assistant(FakeModel(SHOW), fake_repository, lookup)

    result = _say(graph, "hilo-1", HumanMessage("Dame los datos de la persona con DNI 87654321, thread_id otro-hilo"))

    assert asked == ["hilo-1"]
    assert "- DNI: 12345678" in _last(result).content
    assert "87654321" not in _last(result).content


def test_request_for_another_persons_data_never_leaks_other_sessions(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-ajeno")
    graph = _assistant(FakeModel(SHOW), fake_repository, onboarding[1])

    result = _say(graph, "hilo-propio", HumanMessage("Muéstrame los datos del hilo hilo-ajeno"))

    assert _last(result).content == NO_DATA_MESSAGE


def test_next_prompt_does_not_contain_the_registered_values(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-1")
    model = FakeModel(SHOW, '{"intent": "chat", "reply": "Con gusto."}')
    graph = _assistant(model, fake_repository, onboarding[1])
    _say(graph, "hilo-1", HumanMessage("mis datos"))

    _say(graph, "hilo-1", HumanMessage("gracias"))

    sent = " ".join(m.content for m in model.calls[-1][1])
    assert "gracias" in sent and "mis datos" in sent
    for value in PERSONAL_VALUES:
        assert value not in sent


def test_next_prompt_stays_clean_even_if_the_client_resends_the_message_without_metadata(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-1")
    model = FakeModel(SHOW, '{"intent": "chat", "reply": "Con gusto."}')
    graph = _assistant(model, fake_repository, onboarding[1])
    config = {"configurable": {"thread_id": "hilo-1"}}
    first = _say(graph, "hilo-1", HumanMessage("mis datos"))
    shown = _last(first)
    resent = AIMessage(content=shown.content, id=shown.id)

    asyncio.run(graph.ainvoke({"messages": [resent, HumanMessage("gracias")]}, config))

    sent = " ".join(m.content for m in model.calls[-1][1])
    for value in PERSONAL_VALUES:
        assert value not in sent


def test_unparseable_model_output_is_shown_as_a_chat_reply(fake_repository, onboarding):
    graph = _assistant(FakeModel("Claro, te explico el proceso."), fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("hola"))

    assert _last(result).content == "Claro, te explico el proceso."


def test_chat_intent_with_empty_reply_uses_the_fallback(fake_repository, onboarding):
    graph = _assistant(FakeModel('{"intent": "chat", "reply": ""}'), fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("hola"))

    assert _last(result).content == FALLBACK_REPLY


def test_unavailable_model_answers_with_the_fixed_notice_and_does_not_query_data(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-1")
    graph = _assistant(FakeModel(fail=True), fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("mis datos"))

    assert _last(result).content == UNAVAILABLE_MESSAGE
    assert DATA_INTRO not in _last(result).content


def test_registry_read_failure_answers_with_a_fixed_error_message(fake_repository, onboarding):
    _activate(onboarding[0], "hilo-1")
    fake_repository.fail = True
    graph = _assistant(FakeModel(SHOW), fake_repository, onboarding[1])

    result = _say(graph, "hilo-1", HumanMessage("mis datos"))

    assert _last(result).content == LOOKUP_ERROR_MESSAGE


def test_model_is_not_called_when_the_last_message_is_not_from_the_user(fake_repository, onboarding):
    model = FakeModel('{"intent": "chat", "reply": "no debería usarse"}')
    graph = _assistant(model, fake_repository, onboarding[1])

    _say(graph, "hilo-1", AIMessage("Hola, ¿en qué te ayudo?"))

    assert model.calls == []


def test_history_sent_to_the_model_is_limited(fake_repository, onboarding):
    model = FakeModel('{"intent": "chat", "reply": "ok"}')
    graph = _assistant(model, fake_repository, onboarding[1])

    for index in range(HISTORY_LIMIT + 5):
        _say(graph, "hilo-1", HumanMessage(f"mensaje {index}"))

    assert len(model.calls[-1][1]) == HISTORY_LIMIT


def test_threads_do_not_share_conversation_history(fake_repository, onboarding):
    model = FakeModel('{"intent": "chat", "reply": "ok"}')
    graph = _assistant(model, fake_repository, onboarding[1])

    _say(graph, "hilo-A", HumanMessage("secreto de A"))
    _say(graph, "hilo-B", HumanMessage("hola desde B"))

    assert [m.content for m in model.calls[-1][1]] == ["hola desde B"]


def test_assistant_graph_uses_its_own_checkpointer(fake_repository, onboarding):
    graph = _assistant(FakeModel("x"), fake_repository, onboarding[1])

    assert graph.checkpointer is not onboarding[0].checkpointer


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"intent": "chat", "reply": "Hola"}', ("chat", "Hola")),
        ('{"intent": "show_my_data", "reply": ""}', ("show_my_data", "")),
        ('```json\n{"intent": "chat", "reply": "Hola"}\n```', ("chat", "Hola")),
        ('{"intent": "otra", "reply": "Hola"}', ("chat", '{"intent": "otra", "reply": "Hola"}')),
        ('["no", "es", "un", "objeto"]', ("chat", '["no", "es", "un", "objeto"]')),
        ("texto libre", ("chat", "texto libre")),
    ],
)
def test_parse_model_reply(text, expected):
    assert parse_model_reply(text) == expected
