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


def test_agui_run_pauses_on_first_step_and_resumes_on_same_thread(fake_gateway):
    client = TestClient(create_app(fake_gateway))

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


def test_agui_cors_allows_angular_dev_server(fake_gateway):
    client = TestClient(create_app(fake_gateway))

    response = client.options(
        "/agent",
        headers={"Origin": "http://localhost:4200", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:4200"
