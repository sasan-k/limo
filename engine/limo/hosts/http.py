from typing import Any

import httpx
from pydantic import SecretStr

from limo.hosts.ports import HostError, HostProject
from limo.hosts.repo_url import parse_repo


class HttpHost:
    """REST plumbing shared by the GitHub and GitLab adapters. Tokens never appear in errors (ADR-9)."""

    label = ""
    user_field = ""

    def __init__(
        self,
        token: SecretStr | None,
        api_url: str,
        timeout_s: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._token = token
        self._client = client or httpx.Client(base_url=api_url, timeout=timeout_s)
        self._login: str | None = None

    def _auth_headers(self, token: str) -> dict[str, str]:
        raise NotImplementedError

    def _request(self, method: str, path: str, json_body: Any = None) -> Any:
        if self._token is None:
            raise HostError(f"{self.label} token not configured")
        headers = self._auth_headers(self._token.get_secret_value())
        try:
            response = self._client.request(method, path, json=json_body, headers=headers)
        except httpx.HTTPError:
            raise HostError(f"{self.label} {method} {path} failed: transport error") from None
        if response.status_code >= 400:
            raise HostError(f"{self.label} {method} {path} failed: {response.status_code}")
        if response.status_code == 204:
            return None
        return response.json()

    def _me(self) -> str:
        if self._login is None:
            self._login = str(self._request("GET", "/user")[self.user_field])
        return self._login

    def _repo(self, project: HostProject) -> str:
        return parse_repo(project.git_url)
