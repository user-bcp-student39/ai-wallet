"""Adaptador de SessionWalletLookup: lee el kyc_id del estado del hilo en el grafo de onboarding."""

from typing import Any


class OnboardingSessionLookup:
    def __init__(self, onboarding_graph: Any) -> None:
        self._graph = onboarding_graph

    def kyc_id_for(self, thread_id: str) -> str | None:
        snapshot = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        return (snapshot.values or {}).get("kyc_id")
