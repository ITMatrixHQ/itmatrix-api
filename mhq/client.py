from __future__ import annotations

from collections.abc import Awaitable
from typing import Any
from urllib.parse import quote

from mhq.auth import resolve_base_url, resolve_key
from mhq.codec import convert_result, decode_public, to_builtin
from mhq.enums import ReturnType, normalize_return_type
from mhq.models import (
    BalanceSheetRow,
    CashFlowRow,
    DividendRow,
    Expirations,
    FloatRow,
    GexHistory,
    GexMatrix,
    GexResult,
    IncomeRow,
    InflationRow,
    LaborRow,
    NewsRow,
    OptionQuote,
    PricePoint,
    RatioRow,
    ShortInterestRow,
    SplitRow,
    Spot,
    TreasuryYieldRow,
)
from mhq.transport import AiohttpTransport, SyncTransport

_FUNDAMENTAL_SCHEMAS: dict[str, Any] = {
    "ratios": list[RatioRow],
    "income": list[IncomeRow],
    "balance-sheet": list[BalanceSheetRow],
    "cash-flow": list[CashFlowRow],
    "dividends": list[DividendRow],
    "splits": list[SplitRow],
    "short-interest": list[ShortInterestRow],
    "float": FloatRow | None,
    "news": list[NewsRow],
}
_ECONOMY_SCHEMAS: dict[str, Any] = {
    "treasury-yields": list[TreasuryYieldRow],
    "inflation": list[InflationRow],
    "labor": list[LaborRow],
}


class ITMatrixV1:
    """Sync or async client for ITMatrix `/api/v1` endpoints."""

    __slots__ = (
        "_api_prefix",
        "_async_mode",
        "_async_transport",
        "_base_url",
        "_headers",
        "_key",
        "_return_type",
        "_symbols",
        "_sync_transport",
        "_timeout",
    )

    def __init__(
        self,
        key: str | None = None,
        *,
        base_url: str | None = None,
        key_file: str | None = None,
        return_type: ReturnType | str | int = ReturnType.STRUCT,
        async_mode: bool = False,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        """Create a lazy client; pass `async_mode=True` for awaitable methods."""

        if "async" in kwargs:
            async_mode = bool(kwargs.pop("async"))
        if kwargs:
            unknown = ", ".join(kwargs)
            raise TypeError(f"Unknown ITMatrixV1 option(s): {unknown}")
        self._key = resolve_key(key, key_file)
        self._base_url = resolve_base_url(base_url)
        self._api_prefix = "" if self._base_url.endswith("/api/v1") else "/api/v1"
        self._headers: dict[str, str] | None = None
        self._timeout = timeout
        self._return_type = normalize_return_type(return_type)
        self._async_mode = async_mode
        self._async_transport: AiohttpTransport | None = None
        self._sync_transport: SyncTransport | None = None
        self._symbols: list[str] | None = None

    def available(self, endpoint: str, *, symbol: str | None = None) -> Any | Awaitable[Any]:
        """Return availability or universe data as plain Python containers."""

        endpoint_name = _endpoint_name(endpoint)
        if self._async_mode:
            return self._available_async(endpoint_name, symbol=symbol)
        return self._available_sync(endpoint_name, symbol=symbol)

    def spot(self, symbol: str) -> Any | Awaitable[Any]:
        """Return the latest spot price for a symbol."""

        return self._data(Spot, f"/spot/{_path_symbol(symbol)}")

    def option(self, ticker: str) -> Any | Awaitable[Any]:
        """Return the current data for one OCC option ticker."""

        return self._data(OptionQuote, f"/options/{_path_part(ticker)}")

    def gex(
        self,
        symbol: str,
        *,
        expiration: str,
        strike_gt: float | None = None,
        strike_gte: float | None = None,
        strike_lt: float | None = None,
        strike_lte: float | None = None,
        strike_eq: float | None = None,
    ) -> Any | Awaitable[Any]:
        """Return current GEX by strike for one symbol expiration."""

        query = {
            "expiration": expiration,
            "strike_gt": strike_gt,
            "strike_gte": strike_gte,
            "strike_lt": strike_lt,
            "strike_lte": strike_lte,
            "strike_eq": strike_eq,
        }
        return self._data(GexResult, f"/gex/{_path_symbol(symbol)}", query)

    def gex_matrix(
        self,
        symbol: str,
        *,
        expirations: str | list[str] | tuple[str, ...] | None = None,
        at: str | None = None,
    ) -> Any | Awaitable[Any]:
        """Return GEX grids across expirations, optionally at a historical timestamp."""

        return self._data(GexMatrix, f"/gex/{_path_symbol(symbol)}/matrix", {"expirations": expirations, "at": at})

    def gex_history(self, symbol: str, *, date: str | None = None) -> Any | Awaitable[Any]:
        """Return intraday net GEX snapshot history."""

        return self._data(GexHistory, f"/gex/{_path_symbol(symbol)}/history", {"date": date})

    def stock_bars(
        self,
        symbol: str,
        *,
        multiplier: int,
        timespan: str,
        from_: str,
        to: str,
        adjusted: bool = True,
        sort: str = "asc",
    ) -> Any | Awaitable[Any]:
        """Return smoothed stock/index price points."""

        query = {
            "multiplier": multiplier,
            "timespan": timespan,
            "from": from_,
            "to": to,
            "adjusted": adjusted,
            "sort": sort,
        }
        return self._data(list[PricePoint], f"/stock/{_path_symbol(symbol)}/bars", query)

    def option_bars(
        self,
        ticker: str,
        *,
        from_: str,
        to: str,
        multiplier: int = 1,
        timespan: str = "minute",
    ) -> Any | Awaitable[Any]:
        """Return smoothed option price points."""

        query = {"from": from_, "to": to, "multiplier": multiplier, "timespan": timespan}
        return self._data(list[PricePoint], f"/options/{_path_part(ticker)}/bars", query)

    def fundamentals(
        self,
        endpoint: str,
        symbol: str,
        *,
        timeframe: str = "quarterly",
        limit: int | None = None,
    ) -> Any | Awaitable[Any]:
        """Return a public fundamentals endpoint for a symbol."""

        endpoint_name = _fundamental_endpoint(endpoint)
        query: dict[str, Any] = {}
        if endpoint_name in {"income", "balance-sheet", "cash-flow"}:
            query["timeframe"] = timeframe
            query["limit"] = 12 if limit is None else limit
        elif endpoint_name in {"dividends", "short-interest", "news"}:
            query["limit"] = _default_limit(endpoint_name) if limit is None else limit
        schema = _FUNDAMENTAL_SCHEMAS[endpoint_name]
        return self._data(schema, f"/fundamentals/{endpoint_name}/{_path_symbol(symbol)}", query)

    def economy(self, endpoint: str, *, limit: int | None = None) -> Any | Awaitable[Any]:
        """Return a public economy fundamentals endpoint."""

        endpoint_name = _economy_endpoint(endpoint)
        default_limit = 500 if endpoint_name == "treasury-yields" else 100
        return self._data(
            _ECONOMY_SCHEMAS[endpoint_name],
            f"/fundamentals/economy/{endpoint_name}",
            {"limit": default_limit if limit is None else limit},
        )

    def close(self) -> Awaitable[None] | None:
        """Close any async resources owned by the client."""

        if self._async_mode:
            return self._close_async()
        self._sync_transport = None
        return None

    def __enter__(self) -> ITMatrixV1:
        """Return the sync client for context-manager usage."""

        return self

    def __exit__(self, *_exc: object) -> None:
        """Close sync client resources on context exit."""

        self.close()

    async def __aenter__(self) -> ITMatrixV1:
        """Return the async client for context-manager usage."""

        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close async client resources on context exit."""

        await self._close_async()

    def _data(self, schema: Any, path: str, query: dict[str, Any] | None = None) -> Any | Awaitable[Any]:
        """Dispatch a data request through the selected sync mode."""

        if self._async_mode:
            return self._data_async(schema, path, query)
        return self._data_sync(schema, path, query)

    def _available_sync(self, endpoint: str, *, symbol: str | None) -> Any:
        """Run an availability request through the blocking transport."""

        self._ensure_ready_sync()
        if endpoint == "symbols":
            return self._symbols
        if endpoint == "expirations":
            if symbol is None:
                raise TypeError("available('expirations') requires symbol='SPY'.")
            return to_builtin(self._get_sync(Expirations, f"/expirations/{_path_symbol(symbol)}"))
        return to_builtin(self._get_sync(list[str], "/fundamentals/tickers"))

    async def _available_async(self, endpoint: str, *, symbol: str | None) -> Any:
        """Run an availability request through the aiohttp transport."""

        await self._ensure_ready_async()
        if endpoint == "symbols":
            return self._symbols
        if endpoint == "expirations":
            if symbol is None:
                raise TypeError("available('expirations') requires symbol='SPY'.")
            return to_builtin(await self._get_async(Expirations, f"/expirations/{_path_symbol(symbol)}"))
        return to_builtin(await self._get_async(list[str], "/fundamentals/tickers"))

    def _data_sync(self, schema: Any, path: str, query: dict[str, Any] | None) -> Any:
        """Fetch, decode, and convert a blocking data request."""

        self._ensure_ready_sync()
        return convert_result(self._get_sync(schema, path, query), self._return_type)

    async def _data_async(self, schema: Any, path: str, query: dict[str, Any] | None) -> Any:
        """Fetch, decode, and convert an async data request."""

        await self._ensure_ready_async()
        return convert_result(await self._get_async(schema, path, query), self._return_type)

    def _ensure_ready_sync(self) -> None:
        """Build shared headers and lazily validate the key through `/symbols`."""

        self._ensure_payload()
        if self._sync_transport is None:
            self._sync_transport = SyncTransport(self._base_url, self._headers or {}, timeout=self._timeout)
        if self._symbols is None:
            self._symbols = self._get_sync(list[str], "/symbols")

    async def _ensure_ready_async(self) -> None:
        """Build shared headers and lazily validate the key through `/symbols`."""

        self._ensure_payload()
        if self._async_transport is None:
            self._async_transport = AiohttpTransport(self._base_url, self._headers or {}, timeout=self._timeout)
        if self._symbols is None:
            self._symbols = await self._get_async(list[str], "/symbols")

    def _ensure_payload(self) -> None:
        """Construct the shared request headers once per instance."""

        if self._headers is None:
            self._headers = {"X-API-Key": self._key}

    def _get_sync(self, schema: Any, path: str, query: dict[str, Any] | None = None) -> Any:
        """Decode a blocking GET response with the requested result schema."""

        if self._sync_transport is None:
            raise RuntimeError("Sync transport was not initialized.")
        return decode_public(self._sync_transport.get(f"{self._api_prefix}{path}", query), schema)

    async def _get_async(self, schema: Any, path: str, query: dict[str, Any] | None = None) -> Any:
        """Decode an aiohttp GET response with the requested result schema."""

        if self._async_transport is None:
            raise RuntimeError("Async transport was not initialized.")
        return decode_public(await self._async_transport.get(f"{self._api_prefix}{path}", query), schema)

    async def _close_async(self) -> None:
        """Close aiohttp resources when async mode was used."""

        if self._async_transport is not None:
            await self._async_transport.close()
            self._async_transport = None


def _endpoint_name(endpoint: str) -> str:
    """Normalize supported availability endpoint names."""

    name = endpoint.replace("_", "-").lower()
    if name in {"symbols", "expirations"}:
        return name
    if name in {"tickers", "fundamentals-tickers", "fundamental-tickers"}:
        return "fundamentals-tickers"
    raise ValueError("endpoint must be 'symbols', 'expirations', or 'fundamentals-tickers'.")


def _fundamental_endpoint(endpoint: str) -> str:
    """Normalize public fundamentals endpoint names."""

    name = endpoint.replace("_", "-").lower()
    if name not in _FUNDAMENTAL_SCHEMAS:
        raise ValueError(f"Unknown fundamentals endpoint: {endpoint}")
    return name


def _economy_endpoint(endpoint: str) -> str:
    """Normalize public economy endpoint names."""

    name = endpoint.replace("_", "-").lower()
    if name not in _ECONOMY_SCHEMAS:
        raise ValueError(f"Unknown economy endpoint: {endpoint}")
    return name


def _default_limit(endpoint: str) -> int:
    """Return documented public defaults for limited fundamentals endpoints."""

    if endpoint == "short-interest":
        return 50
    if endpoint == "news":
        return 10
    return 20


def _path_symbol(symbol: str) -> str:
    """Normalize and encode a stock/index symbol for path usage."""

    return quote(symbol.upper(), safe="")


def _path_part(value: str) -> str:
    """Encode an arbitrary path component."""

    return quote(value, safe="")
