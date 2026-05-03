from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from mhq.auth import resolve_base_url, resolve_key
from mhq.codec import decode_ws_message, encode_json
from mhq.models import WsEvent

_STOP = object()


@dataclass(frozen=True, slots=True)
class SubscriptionKey:
    """Unique key for counting socket subscriptions."""

    channel: str
    symbol: str
    expiration: str | None = None
    strikes: tuple[float, ...] = ()


class ITSubscription:
    """Awaitable async iterator for one logical WebSocket subscription."""

    __slots__ = ("_active", "_key", "_queue", "_stream")

    def __init__(self, stream: ITStream, key: SubscriptionKey) -> None:
        """Bind the subscription object to its owning stream factory."""

        self._stream = stream
        self._key = key
        self._queue: asyncio.Queue[WsEvent | object] = asyncio.Queue()
        self._active = False

    def __await__(self) -> Any:
        """Allow `await stream.subscribe(...)` to start and return this object."""

        return self.start().__await__()

    async def __aenter__(self) -> ITSubscription:
        """Start the subscription when entering an async context."""

        return await self.start()

    async def __aexit__(self, *_exc: object) -> None:
        """Stop the subscription when leaving an async context."""

        await self.stop()

    def __aiter__(self) -> ITSubscription:
        """Return this object as its own async iterator."""

        return self

    async def __anext__(self) -> WsEvent:
        """Read the next routed WebSocket event struct."""

        item = await self._queue.get()
        if item is _STOP:
            raise StopAsyncIteration
        return item

    async def start(self) -> ITSubscription:
        """Start this logical subscription on the shared socket."""

        if not self._active:
            await self._stream._start(self)
            self._active = True
        return self

    async def stop(self) -> None:
        """Stop this logical subscription immediately."""

        if self._active:
            self._active = False
            await self._stream._stop(self)
        self._queue.put_nowait(_STOP)

    def feed(self, message: WsEvent) -> None:
        """Route one decoded message into this subscription."""

        if self._active:
            self._queue.put_nowait(message)

    def matches(self, message: WsEvent) -> bool:
        """Return true when a decoded socket message belongs to this subscription."""

        if message.symbol != self._key.symbol:
            return False
        channel = message.channel
        if self._key.channel == "gex":
            return channel in {"gex", "gex:update"}
        if channel != self._key.channel:
            return False
        if self._key.channel != "options":
            return True
        if message.expiration != self._key.expiration:
            return False
        return message.strike is not None and (not self._key.strikes or message.strike in self._key.strikes)


class ITStream:
    """Factory and shared socket manager for WebSocket subscriptions."""

    __slots__ = ("_base_url", "_counts", "_headers", "_lock", "_receiver", "_session", "_subs", "_timeout", "_ws")

    def __init__(
        self,
        key: str | None = None,
        *,
        base_url: str | None = None,
        key_file: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Create a lazy WebSocket stream factory."""

        self._base_url = _ws_url(resolve_base_url(base_url))
        self._headers = {"X-API-Key": resolve_key(key, key_file)}
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._receiver: asyncio.Task[None] | None = None
        self._counts: Counter[SubscriptionKey] = Counter()
        self._subs: dict[SubscriptionKey, set[ITSubscription]] = {}
        self._lock = asyncio.Lock()

    def subscribe(
        self,
        channel: str,
        symbol: str,
        *,
        expiration: str | None = None,
        strikes: Iterable[float] = (),
    ) -> ITSubscription:
        """Build an awaitable subscription for a supported channel."""

        key = SubscriptionKey(channel.lower(), symbol.upper(), expiration, tuple(strikes))
        return ITSubscription(self, key)

    def gex(self, symbol: str) -> ITSubscription:
        """Build a GEX subscription."""

        return self.subscribe("gex", symbol)

    def spot(self, symbol: str) -> ITSubscription:
        """Build a spot-price subscription."""

        return self.subscribe("spot", symbol)

    def options(self, symbol: str, *, expiration: str, strikes: Iterable[float]) -> ITSubscription:
        """Build an option-tick subscription."""

        return self.subscribe("options", symbol, expiration=expiration, strikes=strikes)

    async def close(self) -> None:
        """Stop every logical subscription and close the shared socket."""

        async with self._lock:
            keys = list(self._subs)
            for key in keys:
                await self._send("unsubscribe", key)
            self._counts.clear()
            self._subs.clear()
            if self._receiver is not None:
                self._receiver.cancel()
                self._receiver = None
            if self._ws is not None:
                await self._ws.close()
                self._ws = None
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def __aenter__(self) -> ITStream:
        """Return the stream factory for async context usage."""

        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close all socket resources on async context exit."""

        await self.close()

    async def _start(self, subscription: ITSubscription) -> None:
        """Register a logical subscription and send only the needed socket frame."""

        async with self._lock:
            await self._ensure_socket()
            key = subscription._key
            self._subs.setdefault(key, set()).add(subscription)
            if self._counts[key] == 0:
                await self._send("subscribe", key)
            self._counts[key] += 1

    async def _stop(self, subscription: ITSubscription) -> None:
        """Unregister a logical subscription and release the socket frame count."""

        async with self._lock:
            key = subscription._key
            subscribers = self._subs.get(key)
            if subscribers is not None:
                subscribers.discard(subscription)
                if not subscribers:
                    self._subs.pop(key, None)
            if self._counts[key] <= 1:
                self._counts.pop(key, None)
                await self._send("unsubscribe", key)
            else:
                self._counts[key] -= 1

    async def _ensure_socket(self) -> None:
        """Open the singleton socket and receiver task on first subscription."""

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers, timeout=self._timeout)
        if self._ws is None or self._ws.closed:
            self._ws = await self._session.ws_connect(self._base_url)
            self._receiver = asyncio.create_task(self._receive())

    async def _send(self, action: str, key: SubscriptionKey) -> None:
        """Send a subscribe or unsubscribe frame for one counted key."""

        if self._ws is None or self._ws.closed:
            return
        payload: dict[str, Any] = {"action": action, "channel": key.channel, "symbol": key.symbol}
        if key.channel == "options":
            payload["expiration"] = key.expiration
            payload["strikes"] = key.strikes
        await self._ws.send_bytes(encode_json(payload))

    async def _receive(self) -> None:
        """Continuously decode and route messages from the shared socket."""

        if self._ws is None:
            return
        async for message in self._ws:
            if message.type == aiohttp.WSMsgType.ERROR:
                break
            if message.type not in {aiohttp.WSMsgType.BINARY, aiohttp.WSMsgType.TEXT}:
                continue
            data = message.data if isinstance(message.data, str) else bytes(message.data)
            self._route(decode_ws_message(data))

    def _route(self, message: WsEvent) -> None:
        """Fan one decoded message out to matching logical subscriptions."""

        for subscribers in self._subs.values():
            for subscription in subscribers:
                if subscription.matches(message):
                    subscription.feed(message)


def _ws_url(base_url: str) -> str:
    """Derive the `/ws` endpoint URL from an HTTP base URL."""

    base_url = base_url.removesuffix("/api/v1")
    parts = urlsplit(base_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, "/ws", "", ""))
