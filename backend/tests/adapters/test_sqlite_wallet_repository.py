import sqlite3
from dataclasses import asdict

import pytest

from adapters.sqlite_wallet_repository import SqliteWalletRepository
from application.onboarding_service import WalletPersistenceError
from ports.wallet_repository import WalletRecord, WalletRepository

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


def _rows(path) -> list[sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute("SELECT * FROM wallets").fetchall()
    finally:
        connection.close()


def test_repository_satisfies_port(tmp_path):
    assert isinstance(SqliteWalletRepository(tmp_path / "wallet.db"), WalletRepository)


def test_creates_database_file_and_wallets_table(tmp_path):
    path = tmp_path / "wallet.db"

    SqliteWalletRepository(path)

    assert path.exists()
    connection = sqlite3.connect(path)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(wallets)")]
        primary_key = [row[1] for row in connection.execute("PRAGMA table_info(wallets)") if row[5] == 1]
    finally:
        connection.close()
    assert columns == [
        "kyc_id",
        "wallet_id",
        "state",
        "document_number",
        "document_type",
        "name",
        "last_name",
        "phone",
        "email",
        "max_amount",
    ]
    assert primary_key == ["kyc_id"]


def test_saves_all_fields_with_test_document_type_by_default(tmp_path):
    path = tmp_path / "wallet.db"

    SqliteWalletRepository(path).save(RECORD)

    rows = _rows(path)
    assert len(rows) == 1
    assert dict(rows[0]) == asdict(RECORD)
    assert rows[0]["document_type"] == "TEST"


def test_saves_non_active_state(tmp_path):
    path = tmp_path / "wallet.db"

    SqliteWalletRepository(path).save(WalletRecord(**{**asdict(RECORD), "kyc_id": "KYC-2", "state": "PENDING"}))

    assert [row["state"] for row in _rows(path)] == ["PENDING"]


def test_reopening_keeps_existing_records(tmp_path):
    path = tmp_path / "wallet.db"
    SqliteWalletRepository(path).save(RECORD)

    SqliteWalletRepository(path)

    assert [row["kyc_id"] for row in _rows(path)] == ["KYC-1"]


def test_duplicate_kyc_id_is_rejected_and_original_record_is_kept(tmp_path):
    path = tmp_path / "wallet.db"
    repository = SqliteWalletRepository(path)
    repository.save(RECORD)

    with pytest.raises(WalletPersistenceError):
        repository.save(WalletRecord(**{**asdict(RECORD), "wallet_id": "W-OTRA", "name": "Otra"}))

    rows = _rows(path)
    assert len(rows) == 1
    assert rows[0]["wallet_id"] == "W-1" and rows[0]["name"] == "Ana"


def test_unwritable_path_raises_persistence_error(tmp_path):
    with pytest.raises(WalletPersistenceError):
        SqliteWalletRepository(tmp_path / "no-existe" / "wallet.db")


def test_save_failure_after_startup_raises_persistence_error(tmp_path):
    path = tmp_path / "wallet.db"
    repository = SqliteWalletRepository(path)
    connection = sqlite3.connect(path)
    connection.execute("DROP TABLE wallets")
    connection.commit()
    connection.close()

    with pytest.raises(WalletPersistenceError):
        repository.save(RECORD)


def test_persistence_error_does_not_leak_personal_data(tmp_path):
    path = tmp_path / "wallet.db"
    repository = SqliteWalletRepository(path)
    repository.save(RECORD)

    with pytest.raises(WalletPersistenceError) as error:
        repository.save(RECORD)

    assert "12345678" not in str(error.value) and "ana@example.com" not in str(error.value)
