from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import aiohttp

from mhq.exceptions import ITMatrixConnectionError, ITMatrixHTTPError

_HTTP_ERROR_STATUS = 400


class AiohttpTransport:
    """Small aiohttp GET transport used by async clients."""

    __slots__ = ("_base_url", "_headers", "_session", "_timeout")

    def __init__(self, base_url: str, headers: Mapping[str, str], *, timeout: float) -> None:
        """Store immutable request context for lazy session creation."""

        self._base_url = base_url
        self._headers = dict(headers)
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def get(self, path: str, query: Mapping[str, Any] | None = None) -> bytes:
        """Perform a GET request and return raw response bytes."""

        session = await self._ensure_session()
        try:
            async with session.get(self._url(path), params=_clean_query(query)) as response:
                body = await response.read()
                if response.status >= _HTTP_ERROR_STATUS:
                    raise ITMatrixHTTPError(response.status, response.reason, body=body)
                return body
        except (TimeoutError, aiohttp.ClientError) as error:
            await self.close()
            raise ITMatrixConnectionError(str(error)) from error

    async def close(self) -> None:
        """Close the owned aiohttp session."""

        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Create the aiohttp session only when the first request is made."""

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers, timeout=self._timeout)
        return self._session

    def _url(self, path: str) -> str:
        """Join a normalized API path onto the configured base URL."""

        return f"{self._base_url}{path}"


class SyncTransport:
    """Blocking stdlib GET transport used by synchronous clients."""

    __slots__ = ("_base_url", "_headers", "_timeout")

    def __init__(self, base_url: str, headers: Mapping[str, str], *, timeout: float) -> None:
        """Store request context for direct blocking calls."""

        self._base_url = base_url
        self._headers = dict(headers)
        self._timeout = timeout

    def get(self, path: str, query: Mapping[str, Any] | None = None) -> bytes:
        """Perform a blocking GET request and return raw response bytes."""

        request = Request(self._url(path, query), headers=self._headers, method="GET")
        try:
            with urlopen(request, timeout=self._timeout) as response:
                return response.read()
        except HTTPError as error:
            raise ITMatrixHTTPError(error.code, error.reason, body=error.read()) from error
        except URLError as error:
            raise ITMatrixConnectionError(str(error.reason)) from error

    def _url(self, path: str, query: Mapping[str, Any] | None) -> str:
        """Join the path and query onto the configured base URL."""

        clean = _clean_query(query)
        if not clean:
            return f"{self._base_url}{path}"
        return f"{self._base_url}{path}?{urlencode(clean)}"


def _clean_query(query: Mapping[str, Any] | None) -> dict[str, str]:
    """Drop empty query values and stringify booleans for both transports."""

    if not query:
        return {}
    clean: dict[str, str] = {}
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, bool):
            clean[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            clean[key] = ",".join(str(item) for item in value)
        else:
            clean[key] = str(value)
    return clean
