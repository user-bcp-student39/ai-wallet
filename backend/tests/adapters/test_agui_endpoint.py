from fastapi.testclient import TestClient

from adapters.agui_endpoint import create_app


def _run_body(thread_id: str, run_id: str, resume: list | None = None) -> dict:
    body = {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [{"id": "m1", "role": "user", "content": "Quiero abrir mi wallet"}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    if resume is not None:
        body["resume"] = resume
    return body


def _events(response_text: str) -> list[dict]:
    import json

    return [json.loads(line[len("data: "):]) for line in response_text.splitlines() if line.startswith("data: ")]


def test_agui_run_pauses_on_first_step_and_resumes_on_same_thread(fake_gateway, fake_repository, fake_model):
    client = TestClient(create_app(fake_gateway, fake_repository, fake_model))

    first = client.post("/agent", json=_run_body("hilo-test-1", "run-1"))
    assert first.status_code == 200
    first_events = _events(first.text)
    assert first_events[0]["type"] == "RUN_STARTED"
    interrupts = [e for e in first_events if e.get("name") == "on_interrupt"]
    assert len(interrupts) == 1
    interrupt_id = interrupts[0]["rawEvent"]["id"]
    assert interrupts[0]["rawEvent"]["value"]["step"] == 1
    assert first_events[-1]["type"] == "RUN_FINISHED"

    resume = [{"interruptId": interrupt_id, "status": "resolved", "payload": {"nombre": "Ana", "apellidos": "Pérez"}}]
    second = client.post("/agent", json=_run_body("hilo-test-1", "run-2", resume=resume))
    assert second.status_code == 200
    second_interrupts = [e for e in _events(second.text) if e.get("name") == "on_interrupt"]
    assert second_interrupts[0]["rawEvent"]["value"]["step"] == 2


def test_agui_cors_allows_angular_dev_server(fake_gateway, fake_repository, fake_model):
    client = TestClient(create_app(fake_gateway, fake_repository, fake_model))

    response = client.options(
        "/agent",
        headers={"Origin": "http://localhost:4200", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:4200"


def _complete_onboarding(client: TestClient, thread_id: str) -> None:
    answers = [
        {"nombre": "Ana", "apellidos": "Pérez"},
        {"telefono": "999999999", "email": "ana@example.com"},
        {"dni": "12345678"},
        {"monto_maximo": "300"},
        {"confirmar": True},
    ]
    response = client.post("/agent", json=_run_body(thread_id, "run-0"))
    for index, answer in enumerate(answers, start=1):
        interrupts = [e for e in _events(response.text) if e.get("name") == "on_interrupt"]
        resume = [{"interruptId": interrupts[0]["rawEvent"]["id"], "status": "resolved", "payload": answer}]
        response = client.post("/agent", json=_run_body(thread_id, f"run-{index}", resume=resume))
    assert response.status_code == 200


def _assistant_body(thread_id: str, run_id: str, messages: list[dict]) -> dict:
    return {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": messages,
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }


def _user(message_id: str, text: str) -> dict:
    return {"id": message_id, "role": "user", "content": text}


def _last_snapshot_messages(response_text: str) -> list[dict]:
    snapshots = [e for e in _events(response_text) if e["type"] == "MESSAGES_SNAPSHOT"]
    return snapshots[-1]["messages"]


def test_agui_full_flow_saves_record_in_injected_repository(fake_gateway, fake_repository, fake_model):
    client = TestClient(create_app(fake_gateway, fake_repository, fake_model))

    _complete_onboarding(client, "hilo-registro")

    assert [(record.kyc_id, record.state, record.document_number) for record in fake_repository.records] == [
        ("KYC-TEST-1", "ACTIVE", "12345678")
    ]


def test_assistant_endpoint_answers_a_chat_message_with_the_model_reply(fake_gateway, fake_repository):
    from conftest import FakeConversationalModel

    model = FakeConversationalModel('{"intent": "chat", "reply": "Son cinco pasos."}')
    client = TestClient(create_app(fake_gateway, fake_repository, model))

    response = client.post("/assistant", json=_assistant_body("hilo-chat", "run-1", [_user("u1", "¿Cuántos pasos?")]))

    assert response.status_code == 200
    assert "Son cinco pasos." in response.text
    assert _events(response.text)[-1]["type"] == "RUN_FINISHED"


def test_assistant_endpoint_shows_the_registered_data_of_the_onboarding_session(fake_gateway, fake_repository):
    from conftest import FakeConversationalModel

    model = FakeConversationalModel('{"intent": "show_my_data", "reply": ""}')
    client = TestClient(create_app(fake_gateway, fake_repository, model))
    _complete_onboarding(client, "hilo-datos")

    response = client.post("/assistant", json=_assistant_body("hilo-datos", "run-a", [_user("u1", "mis datos")]))

    assert "Estos son tus datos registrados:" in response.text
    assert "12345678" in response.text and "ana@example.com" in response.text
    assert "KYC-TEST-1" not in response.text


def test_assistant_endpoint_does_not_show_data_to_a_session_without_registration(fake_gateway, fake_repository):
    from conftest import FakeConversationalModel

    model = FakeConversationalModel('{"intent": "show_my_data", "reply": ""}')
    client = TestClient(create_app(fake_gateway, fake_repository, model))
    _complete_onboarding(client, "hilo-con-datos")

    response = client.post("/assistant", json=_assistant_body("hilo-sin-datos", "run-a", [_user("u1", "mis datos")]))

    assert "Todavía no hay datos registrados en esta sesión." in response.text
    assert "12345678" not in response.text


def test_assistant_endpoint_keeps_registered_data_out_of_the_next_prompt_when_the_client_resends_history(
    fake_gateway, fake_repository
):
    from conftest import FakeConversationalModel

    model = FakeConversationalModel('{"intent": "show_my_data", "reply": ""}', '{"intent": "chat", "reply": "Con gusto."}')
    client = TestClient(create_app(fake_gateway, fake_repository, model))
    _complete_onboarding(client, "hilo-historial")
    first = client.post("/assistant", json=_assistant_body("hilo-historial", "run-a", [_user("u1", "mis datos")]))
    history = _last_snapshot_messages(first.text)
    assert any("Estos son tus datos registrados:" in str(message.get("content")) for message in history)

    client.post("/assistant", json=_assistant_body("hilo-historial", "run-b", [*history, _user("u2", "gracias")]))

    sent = " ".join(message.content for message in model.calls[-1][1])
    assert "gracias" in sent
    for value in ("12345678", "ana@example.com", "999999999", "W-TEST-1"):
        assert value not in sent


def test_assistant_endpoint_reports_an_unavailable_model_without_failing_the_run(fake_gateway, fake_repository):
    from conftest import FakeConversationalModel

    client = TestClient(create_app(fake_gateway, fake_repository, FakeConversationalModel(fail=True)))

    response = client.post("/assistant", json=_assistant_body("hilo-caido", "run-1", [_user("u1", "hola")]))

    assert response.status_code == 200
    assert "El asistente no está disponible por ahora." in response.text
    assert _events(response.text)[-1]["type"] == "RUN_FINISHED"


def test_onboarding_endpoint_keeps_working_while_the_assistant_model_is_down(fake_gateway, fake_repository):
    from conftest import FakeConversationalModel

    client = TestClient(create_app(fake_gateway, fake_repository, FakeConversationalModel(fail=True)))

    _complete_onboarding(client, "hilo-formulario")

    assert [record.kyc_id for record in fake_repository.records] == ["KYC-TEST-1"]
