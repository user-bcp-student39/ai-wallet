"""Adaptador SQLite del puerto WalletRepository, con la biblioteca estándar."""

import sqlite3
from contextlib import closing
from os import PathLike

from application.onboarding_service import WalletPersistenceError
from ports.wallet_repository import WalletRecord

# Cada guardado abre su propia conexión: el servidor atiende cada petición en un hilo distinto
# y sqlite3 no permite compartir una conexión entre hilos.
CONNECT_TIMEOUT_SECONDS = 15.0

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS wallets (
    kyc_id TEXT PRIMARY KEY,
    wallet_id TEXT NOT NULL,
    state TEXT NOT NULL,
    document_number TEXT NOT NULL,
    document_type TEXT NOT NULL,
    name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL,
    max_amount TEXT NOT NULL
)
"""

INSERT = """
INSERT INTO wallets (
    kyc_id, wallet_id, state, document_number, document_type, name, last_name, phone, email, max_amount
) VALUES (
    :kyc_id, :wallet_id, :state, :document_number, :document_type, :name, :last_name, :phone, :email, :max_amount
)
"""


class SqliteWalletRepository:
    def __init__(self, path: str | PathLike[str]) -> None:
        self._path = str(path)
        self._execute(CREATE_TABLE)

    def save(self, record: WalletRecord) -> None:
        self._execute(INSERT, record.__dict__)

    def _execute(self, statement: str, parameters: dict[str, str] | None = None) -> None:
        try:
            with closing(sqlite3.connect(self._path, timeout=CONNECT_TIMEOUT_SECONDS)) as connection:
                with connection:
                    connection.execute(statement, parameters or {})
        except sqlite3.Error as exc:
            raise WalletPersistenceError(f"No se pudo escribir en el almacén de wallets ({type(exc).__name__})") from exc
