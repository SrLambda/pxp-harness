"""Contrato neutral de lanzamiento de agentes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .mcp import MCPServer


@dataclass(frozen=True)
class LaunchRequest:
    """Contexto independiente del transporte."""

    root: Path
    context: str
    user_request: str
    base_prompt: Path | None = None
    servers: tuple[MCPServer, ...] = ()
    developer_notes: tuple[str, ...] = ()


class AgentStrategy(Protocol):
    """Permite adaptadores externos explícitos."""

    def launch(
        self, request: LaunchRequest
    ) -> int:
        """Inicia y retorna su código."""
        ...
