"""Tool de LangChain que obtiene los datos registrados de la wallet de la sesión actual."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from application.wallet_data_message import VISIBLE_FIELDS
from ports.session_wallet_lookup import SessionWalletLookup
from ports.wallet_repository import WalletRepository

TOOL_NAME = "get_my_wallet_data"


def build_wallet_data_tool(repository: WalletRepository, lookup: SessionWalletLookup) -> BaseTool:
    @tool(TOOL_NAME)
    def get_my_wallet_data(thread_id: str) -> dict[str, Any]:
        """Obtiene los datos registrados de la wallet de la sesión actual, sin el identificador de verificación.

        Args:
            thread_id: identificador de la sesión actual. Lo fija el servidor; nunca lo decide el modelo
                ni lo escribe el usuario.

        Returns:
            found y, si hay registro, record con los campos visibles.
        """
        kyc_id = lookup.kyc_id_for(thread_id)
        record = repository.find(kyc_id) if kyc_id else None
        if record is None:
            return {"found": False}
        return {"found": True, "record": {field: getattr(record, field) for field, _label in VISIBLE_FIELDS}}

    return get_my_wallet_data
