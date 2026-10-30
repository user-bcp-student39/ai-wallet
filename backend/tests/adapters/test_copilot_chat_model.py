import asyncio
from types import SimpleNamespace

import pytest
from copilot.generated.rpc import PermissionDecisionReject
from copilot.session_events import AssistantMessageData
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.copilot_chat_model import (
    DEFAULT_MODEL,
    CopilotChatModel,
    CopilotSettings,
    build_prompt,
    copilot_lifespan,
)
from ports.conversational_model import ChatMessage, ConversationalModel, ModelUnavailableError


class FakeSession:
    def __init__(self, client: "FakeClient") -> None:
        self._client = client

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc) -> None:
        self._client.closed_sessions += 1

    async def send_and_wait(self, prompt: str, timeout: float):
        self._client.prompts.append((prompt, timeout))
        if self._client.error:
            raise self._client.error
        if self._client.reply is None:
            return None
        return SimpleNamespace(data=AssistantMessageData(content=self._client.reply, message_id="m1"))


class FakeClient:
    def __init__(self, reply: str | None = "Hola", error: Exception | None = None, fail_start: bool = False) -> None:
        self.reply = reply
        self.error = error
        self.fail_start = fail_start
        self.started = 0
        self.stopped = 0
        self.session_kwargs: list[dict] = []
        self.prompts: list[tuple[str, float]] = []
        self.closed_sessions = 0

    async def start(self) -> None:
        if self.fail_start:
            raise RuntimeError("sin sesión de Copilot")
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1

    async def create_session(self, **kwargs) -> FakeSession:
        self.session_kwargs.append(kwargs)
        return FakeSession(self)


def _model(client: FakeClient, settings: CopilotSettings | None = None) -> CopilotChatModel:
    return CopilotChatModel(settings or CopilotSettings(), client_factory=lambda _settings: client)


def _complete(model: CopilotChatModel, text: str = "hola"):
    return asyncio.run(_run(model, text))


async def _run(model: CopilotChatModel, text: str):
    await model.start()
    return await model.complete("sistema", [ChatMessage("user", text)])


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("COPILOT_MODEL", "COPILOT_USE_LOGGED_IN_USER", "COPILOT_REASONING_EFFORT", "COPILOT_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)


def test_model_satisfies_port():
    assert isinstance(CopilotChatModel(), ConversationalModel)


def test_settings_defaults_use_gpt_6_luna_and_local_login():
    settings = CopilotSettings.from_env()

    assert settings.model == DEFAULT_MODEL == "gpt-6-luna"
    assert settings.use_logged_in_user is True
    assert settings.reasoning_effort == "low"
    assert settings.timeout_seconds == 60.0


def test_settings_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("COPILOT_MODEL", "otro-modelo")
    monkeypatch.setenv("COPILOT_USE_LOGGED_IN_USER", "false")
    monkeypatch.setenv("COPILOT_REASONING_EFFORT", "high")
    monkeypatch.setenv("COPILOT_TIMEOUT_SECONDS", "12.5")

    settings = CopilotSettings.from_env()

    assert (settings.model, settings.use_logged_in_user, settings.reasoning_effort, settings.timeout_seconds) == (
        "otro-modelo",
        False,
        "high",
        12.5,
    )


def test_invalid_timeout_fails_fast(monkeypatch):
    monkeypatch.setenv("COPILOT_TIMEOUT_SECONDS", "mucho")

    with pytest.raises(ValueError):
        CopilotSettings.from_env()


def test_prompt_labels_each_message_by_role():
    prompt = build_prompt([ChatMessage("user", "Hola"), ChatMessage("assistant", "Buenas"), ChatMessage("user", "Gracias")])

    assert prompt == "[USUARIO]\nHola\n\n[ASISTENTE]\nBuenas\n\n[USUARIO]\nGracias"


def test_complete_returns_text_from_a_text_only_session():
    client = FakeClient(reply="Respuesta")

    result = _complete(_model(client, CopilotSettings(timeout_seconds=7.0)), "¿Cómo activo mi wallet?")

    assert result == "Respuesta"
    kwargs = client.session_kwargs[0]
    assert kwargs["model"] == "gpt-6-luna"
    assert kwargs["available_tools"] == []
    assert kwargs["skip_custom_instructions"] is True
    assert kwargs["system_message"] == {"mode": "replace", "content": "sistema"}
    assert client.prompts == [("[USUARIO]\n¿Cómo activo mi wallet?", 7.0)]
    assert client.closed_sessions == 1


def test_permission_requests_are_denied():
    client = FakeClient()
    _complete(_model(client))

    decision = client.session_kwargs[0]["on_permission_request"]({"kind": "shell"})

    assert isinstance(decision, PermissionDecisionReject)


def test_session_error_becomes_model_unavailable_without_leaking_the_prompt():
    client = FakeClient(error=RuntimeError("falló"))

    with pytest.raises(ModelUnavailableError) as error:
        _complete(_model(client), "mi DNI es 12345678")

    assert "12345678" not in str(error.value)
    assert client.closed_sessions == 1


def test_timeout_becomes_model_unavailable():
    client = FakeClient(error=TimeoutError())

    with pytest.raises(ModelUnavailableError):
        _complete(_model(client))


def test_reply_without_text_becomes_model_unavailable():
    with pytest.raises(ModelUnavailableError):
        _complete(_model(FakeClient(reply=None)))


def test_model_that_was_never_started_is_unavailable():
    model = _model(FakeClient())

    with pytest.raises(ModelUnavailableError):
        asyncio.run(model.complete("sistema", [ChatMessage("user", "hola")]))


def test_client_is_created_once_at_startup_reused_across_messages_and_closed_at_shutdown():
    client = FakeClient()
    created: list[CopilotSettings] = []

    def factory(settings: CopilotSettings) -> FakeClient:
        created.append(settings)
        return client

    model = CopilotChatModel(CopilotSettings(), client_factory=factory)

    with TestClient(FastAPI(lifespan=copilot_lifespan(model))):
        assert (client.started, client.stopped, len(created)) == (1, 0, 1)
        asyncio.run(model.complete("sistema", [ChatMessage("user", "uno")]))
        asyncio.run(model.complete("sistema", [ChatMessage("user", "dos")]))
        assert (client.started, len(created), len(client.session_kwargs)) == (1, 1, 2)

    assert client.stopped == 1


def test_app_starts_even_when_the_copilot_client_cannot_start():
    client = FakeClient(fail_start=True)
    model = _model(client)

    with TestClient(FastAPI(lifespan=copilot_lifespan(model))):
        with pytest.raises(ModelUnavailableError):
            asyncio.run(model.complete("sistema", [ChatMessage("user", "hola")]))

    assert client.stopped == 0


def test_model_can_be_restarted_after_shutdown():
    client = FakeClient()
    model = _model(client)

    with TestClient(FastAPI(lifespan=copilot_lifespan(model))):
        pass
    with TestClient(FastAPI(lifespan=copilot_lifespan(model))):
        assert asyncio.run(model.complete("sistema", [ChatMessage("user", "hola")])) == "Hola"

    assert (client.started, client.stopped) == (2, 2)
