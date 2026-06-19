from __future__ import annotations

from typing import Optional

from ticktick_mcp.client import (
    TickTickClient,
    build_client,
    _make_retry_session,
    _session_headers,
)
from ticktick_mcp.api import list_projects as _cli_list_projects

from config import get_api_key, get_web_credentials


class TickTickMCPSession:
    def __init__(self):
        self._web_client: Optional[TickTickClient] = None
        self._web_client_built: bool = False
        self._projects_cache: Optional[list] = None

    @property
    def api_key(self) -> str:
        return get_api_key()

    def get_web_client(self) -> TickTickClient:
        if self._web_client is not None:
            return self._web_client
        username, password = get_web_credentials()
        self._web_client = TickTickClient(
            username=username,
            password=password,
            session=_make_retry_session(),
            headers=_session_headers(),
        )
        return self._web_client

    def list_projects(self) -> list[dict]:
        return _cli_list_projects()

    @property
    def projects(self) -> list[dict]:
        if self._projects_cache is None:
            self._projects_cache = _cli_list_projects()
        return self._projects_cache

    def invalidate_cache(self):
        self._projects_cache = None

    def resolve_project_id(self, identifier: str) -> str:
        if not identifier:
            raise RuntimeError("project identifier is required")

        for p in self.projects:
            if p["id"] == identifier:
                return identifier
            if p["name"].casefold() == identifier.casefold():
                return p["id"]

        raise RuntimeError(f"project not found: {identifier}")

    def list_tags(self) -> list[dict]:
        client = self.get_web_client()
        return client.state.get("tags", [])


def _create_session() -> TickTickMCPSession:
    return TickTickMCPSession()


_session: Optional[TickTickMCPSession] = None


def get_session() -> TickTickMCPSession:
    global _session
    if _session is None:
        _session = _create_session()
    return _session
