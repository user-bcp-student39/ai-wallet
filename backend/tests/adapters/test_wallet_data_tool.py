from dataclasses import asdict

import pytest

from adapters.wallet_data_tool import TOOL_NAME, build_wallet_data_tool
from application.onboarding_service import WalletPersistenceError
from application.wallet_data_message import DATA_INTRO, NO_DATA_MESSAGE, format_wallet_data
from ports.wallet_repository import WalletRecord

RECORD = WalletRecord(
    kyc_id="KYC-1",
    wallet_id="W-1",
    state="ACTIVE",
    document_number="12345678",
    name="Ana",
    last_name="Pérez",
    phone="999999999",
    email="ana@example.com",
    max_amount="300",
)
VISIBLE = {"wallet_id", "state", "document_number", "document_type", "name", "last_name", "phone", "email", "max_amount"}


class FakeLookup:
    def __init__(self, mapping: dict[str, str | None]) -> None:
        self.mapping = mapping
        self.asked: list[str] = []

    def kyc_id_for(self, thread_id: str) -> str | None:
        self.asked.append(thread_id)
        return self.mapping.get(thread_id)


def _tool(fake_repository, mapping):
    fake_repository.save(RECORD)
    lookup = FakeLookup(mapping)
    return build_wallet_data_tool(fake_repository, lookup), lookup


def test_tool_has_expected_name_and_only_a_thread_id_argument(fake_repository):
    tool, _ = _tool(fake_repository, {})

    assert tool.name == TOOL_NAME == "get_my_wallet_data"
    assert tool.description
    assert set(tool.args) == {"thread_id"}


def test_tool_returns_the_nine_visible_fields_without_kyc_id(fake_repository):
    tool, lookup = _tool(fake_repository, {"hilo-1": "KYC-1"})

    result = tool.invoke({"thread_id": "hilo-1"})

    assert result["found"] is True
    assert set(result["record"]) == VISIBLE
    assert "kyc_id" not in result["record"]
    assert result["record"] == {k: v for k, v in asdict(RECORD).items() if k != "kyc_id"}
    assert lookup.asked == ["hilo-1"]


def test_tool_finds_nothing_for_a_session_without_registration(fake_repository):
    tool, _ = _tool(fake_repository, {"hilo-1": "KYC-1"})

    assert tool.invoke({"thread_id": "otro-hilo"}) == {"found": False}


def test_tool_finds_nothing_when_the_registered_kyc_id_has_no_record(fake_repository):
    tool, _ = _tool(fake_repository, {"hilo-1": "KYC-INEXISTENTE"})

    assert tool.invoke({"thread_id": "hilo-1"}) == {"found": False}


def test_tool_propagates_a_read_failure(fake_repository):
    tool, _ = _tool(fake_repository, {"hilo-1": "KYC-1"})
    fake_repository.fail = True

    with pytest.raises(WalletPersistenceError):
        tool.invoke({"thread_id": "hilo-1"})


def test_message_lists_every_visible_field_one_per_line_and_hides_kyc_id(fake_repository):
    tool, _ = _tool(fake_repository, {"hilo-1": "KYC-1"})

    message = format_wallet_data(tool.invoke({"thread_id": "hilo-1"}))

    assert message.splitlines() == [
        DATA_INTRO,
        "- ID de wallet: W-1",
        "- Estado: ACTIVE",
        "- DNI: 12345678",
        "- Tipo de documento: TEST",
        "- Nombre: Ana",
        "- Apellidos: Pérez",
        "- Teléfono: 999999999",
        "- Email: ana@example.com",
        "- Monto máximo por operación: 300 PEN",
    ]
    assert "KYC-1" not in message


def test_message_never_prints_kyc_id_even_if_the_result_carries_it():
    message = format_wallet_data({"found": True, "record": {**asdict(RECORD)}})

    assert "KYC-1" not in message and "kyc" not in message.lower()


def test_message_without_registration_says_there_is_no_data():
    assert format_wallet_data({"found": False}) == NO_DATA_MESSAGE


def test_markdown_special_characters_in_values_are_escaped_so_the_chat_shows_them_unchanged():
    record = {**{k: v for k, v in asdict(RECORD).items() if k != "kyc_id"}}
    record.update(wallet_id="wallet_9381_ab", email="ana_perez@example.com", name="*Ana* [x] <b>", last_name="a`b~c\\d")

    message = format_wallet_data({"found": True, "record": record})

    assert "- ID de wallet: wallet\\_9381\\_ab" in message
    assert "- Email: ana\\_perez@example.com" in message
    assert "- Nombre: \\*Ana\\* \\[x\\] \\<b\\>" in message
    assert "- Apellidos: a\\`b\\~c\\\\d" in message
