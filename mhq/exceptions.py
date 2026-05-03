from __future__ import annotations


class ITMatrixError(Exception):
    """Base exception for all client-side ITMatrix failures."""


class ITMatrixConfigError(ITMatrixError):
    """Raised when required local client configuration is missing."""


class ITMatrixAPIError(ITMatrixError):
    """Raised when the public API returns an error envelope."""

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        """Store the server message and request identifier when present."""

        super().__init__(message)
        self.request_id = request_id


class ITMatrixHTTPError(ITMatrixError):
    """Raised when an HTTP request fails before a valid API result is decoded."""

    def __init__(self, status: int, message: str, *, body: bytes = b"") -> None:
        """Store the status code and raw response body for diagnostics."""

        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.body = body


class ITMatrixConnectionError(ITMatrixError):
    """Raised when the client cannot connect to the configured API host."""
