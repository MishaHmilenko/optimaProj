"""HTTP transport abstraction.

Everything above this module (GenshinApiClient, services, CLI) depends
only on IHttpClient. The real network implementation uses urllib from
the standard library; FileHttpClient serves the same URLs from local
JSON files, which is what the tests and the --offline mode use.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class RemoteServiceError(Exception):
    """Any failure talking to a remote service: network, HTTP status,
    or a response that isn't the JSON we expected."""


class IHttpClient(ABC):
    @abstractmethod
    def get_json(self, url: str) -> Any:
        """GET the URL and return the decoded JSON body."""
        raise NotImplementedError


class UrllibHttpClient(IHttpClient):
    """Real network client built on urllib.request."""

    def __init__(self, timeout: float = 10.0, user_agent: str = "oop-course-cli/1.0") -> None:
        self._timeout = timeout
        self._user_agent = user_agent

    def get_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": self._user_agent}
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise RemoteServiceError(f"HTTP {exc.code} for {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RemoteServiceError(f"Network error for {url}: {exc}") from exc

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteServiceError(f"Invalid JSON from {url}") from exc


class FileHttpClient(IHttpClient):
    """Serves URLs from a directory: the URL path `/characters/albedo`
    maps to `<root>/characters/albedo.json`. Used for offline mode and
    as a deterministic transport in tests."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def get_json(self, url: str) -> Any:
        path = urllib.parse.unquote(urllib.parse.urlparse(url).path).strip("/")
        file_path = self._root / f"{path}.json"
        if not file_path.is_file():
            raise RemoteServiceError(f"404 (offline sample not found) for {url}")
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RemoteServiceError(f"Invalid JSON in {file_path}") from exc
