from __future__ import annotations

import asyncio
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

import aiohttp
import msgspec
import numpy as np
import pandas as pd
from aiohttp import web

from mhq import ITMatrixV1, ITStream, ReturnType
from mhq.auth import resolve_base_url
from mhq.codec import convert_result, decode_public, decode_ws_message, to_builtin
from mhq.enums import normalize_return_type
from mhq.exceptions import (
    ITMatrixAPIError,
    ITMatrixConfigError,
    ITMatrixConnectionError,
    ITMatrixHTTPError,
)
from mhq.models import GexMatrix, GexResult, PricePoint, Spot, WsEvent
from mhq.transport import AiohttpTransport, SyncTransport

_ENCODER = msgspec.json.Encoder()
_DECODER = msgspec.json.Decoder()


class FakeSyncTransport:
    """Small blocking transport fixture for client routing tests."""

    def __init__(self) -> None:
        """Capture calls so tests can assert lazy caching behavior."""

        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, path: str, query: dict[str, Any] | None = None) -> bytes:
        """Return API-shaped envelopes for requested paths."""

        self.calls.append((path, query))
        return _fake_response(path)


class FakeAsyncTransport(FakeSyncTransport):
    """Async transport fixture with the same payloads as the sync fixture."""

    async def get(self, path: str, query: dict[str, Any] | None = None) -> bytes:
        """Return API-shaped envelopes from an async method."""

        return super().get(path, query)

    async def close(self) -> None:
        """Satisfy the async transport close protocol."""


class ClientTests(unittest.TestCase):
    """Client behavior tests that do not require the live API host."""

    def test_key_resolution_and_constructor_guards(self) -> None:
        """The public constructor resolves keys and rejects unknown options."""

        with tempfile.TemporaryDirectory() as tmp:
            key_file = Path(tmp) / ".itmkey"
            key_file.write_text("itm_file\n", encoding="utf-8")

            self.assertEqual(ITMatrixV1(key_file=str(key_file))._key, "itm_file")
            with patch.dict("os.environ", {"ITM_KEY": "itm_env", "ITM_BASE_URL": "http://env.test"}):
                self.assertEqual(ITMatrixV1()._key, "itm_env")
                self.assertEqual(resolve_base_url(None), "http://env.test")
            with (
                patch.dict("os.environ", {}, clear=True),
                patch("pathlib.Path.cwd", return_value=Path(tmp) / "none"),
                self.assertRaises(ITMatrixConfigError),
            ):
                ITMatrixV1()
        with self.assertRaises(TypeError):
            ITMatrixV1("itm_test", unknown=True)

    def test_sync_client_routes_every_public_data_method(self) -> None:
        """The sync public methods build documented paths and decode structs."""

        client = ITMatrixV1("itm_test", base_url="http://example.test")
        transport = FakeSyncTransport()
        client._sync_transport = transport

        self.assertEqual(client.available("symbols"), ["SPY", "QQQ"])
        self.assertEqual(client.available("expirations", symbol="spy")["expirations"], ["2026-05-15"])
        self.assertEqual(client.available("tickers"), ["AAPL", "MSFT"])
        self.assertIsInstance(client.spot("spy"), Spot)
        self.assertEqual(client.option("O:SPY260417C00600000").underlying, "SPY")
        self.assertEqual(client.gex("spy", expiration="2026-05-15").expiration, "2026-05-15")
        self.assertIsInstance(client.gex_matrix("spy", expirations=["2026-05-15"]), GexMatrix)
        self.assertEqual(client.gex_history("spy", date="2026-05-03").snapshots[0].captured_at[:10], "2026-05-03")
        stock_bars = client.stock_bars("spy", multiplier=1, timespan="minute", from_="2026-05-01", to="2026-05-02")
        option_bars = client.option_bars("O:SPY260417C00600000", from_="2026-05-01", to="2026-05-02")
        self.assertEqual(stock_bars[0].t, 1)
        self.assertEqual(option_bars[0].price, 18.42)
        self.assertEqual(client.fundamentals("ratios", "aapl")[0].ticker, "AAPL")
        self.assertEqual(client.fundamentals("income", "aapl")[0].revenue, 1.0)
        self.assertEqual(client.fundamentals("balance_sheet", "aapl")[0].total_assets, 1.0)
        self.assertEqual(client.fundamentals("cash-flow", "aapl")[0].capex, -1.0)
        self.assertEqual(client.fundamentals("dividends", "aapl")[0].cash_amount, 0.25)
        self.assertEqual(client.fundamentals("splits", "aapl")[0].split_to, 4.0)
        self.assertEqual(client.fundamentals("short-interest", "aapl")[0].days_to_cover, 2.0)
        self.assertEqual(client.fundamentals("float", "aapl").free_float, 1.0)
        self.assertEqual(client.fundamentals("news", "aapl")[0].id, "n1")
        self.assertEqual(client.economy("treasury_yields")[0].y10y, 4.0)
        self.assertEqual(client.economy("inflation")[0].cpi, 1.0)
        self.assertEqual(client.economy("labor")[0].unemployment_rate, 4.0)
        client.close()

        self.assertEqual([call[0] for call in transport.calls].count("/api/v1/symbols"), 1)
        with self.assertRaises(TypeError):
            client.available("expirations")
        with self.assertRaises(ValueError):
            client.available("missing")
        with self.assertRaises(ValueError):
            client.fundamentals("missing", "AAPL")
        with self.assertRaises(ValueError):
            client.economy("missing")

        with ITMatrixV1("itm_test", base_url="http://example.test") as managed:
            managed._sync_transport = FakeSyncTransport()
            self.assertEqual(managed.available("symbols")[0], "SPY")
        with self.assertRaises(RuntimeError):
            ITMatrixV1("itm_test", base_url="http://example.test")._get_sync(list[str], "/symbols")

    def test_return_type_conversions_and_aliases(self) -> None:
        """Data methods can return structs, pandas frames, or NumPy columns."""

        frame_client = ITMatrixV1("itm_test", base_url="http://example.test", return_type=ReturnType.DATAFRAME)
        frame_client._sync_transport = FakeSyncTransport()
        frame = frame_client.stock_bars("spy", multiplier=1, timespan="minute", from_="2026-05-01", to="2026-05-02")

        dict_client = ITMatrixV1("itm_test", base_url="http://example.test", return_type="dict")
        dict_client._sync_transport = FakeSyncTransport()
        columns = dict_client.stock_bars("spy", multiplier=1, timespan="minute", from_="2026-05-01", to="2026-05-02")

        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(frame.loc[0, "price"], 612.34)
        self.assertIsInstance(columns["price"], np.ndarray)
        self.assertEqual(columns["price"][0], 612.34)
        self.assertIs(normalize_return_type(1), ReturnType.STRUCT)

    def test_codec_error_and_flattening_paths(self) -> None:
        """Envelope errors, direct payloads, and nested result flattening are handled."""

        self.assertEqual(decode_public(b'[{"t":1,"price":2.0}]', list[PricePoint])[0].price, 2.0)
        self.assertEqual(to_builtin(decode_ws_message(b'{"channel":"spot","symbol":"SPY","price":1.0}'))["price"], 1.0)
        self.assertTrue(convert_result(None, ReturnType.DATAFRAME).empty)
        self.assertTrue(convert_result([], ReturnType.DATAFRAME).empty)
        self.assertEqual(convert_result("ok", ReturnType.ARRAY_DICT)["value"][0], "ok")
        self.assertEqual(convert_result(["SPY"], ReturnType.ARRAY_DICT)["value"][0], "SPY")
        snapshots = {"symbol": "SPY", "snapshots": [{"x": 1}, 2]}
        expirations = {"symbol": "SPY", "expirations": ["2026-05-15", {"expiration": "2026-05-22"}]}
        gex_frame = convert_result(decode_public(_envelope(_gex_payload()), GexResult), ReturnType.DATAFRAME)

        self.assertEqual(convert_result(snapshots, ReturnType.DATAFRAME).shape[0], 2)
        self.assertEqual(
            convert_result(expirations, ReturnType.DATAFRAME).shape[0],
            2,
        )
        self.assertEqual(gex_frame.loc[0, "strike"], 600)
        self.assertEqual(convert_result({"x": 1}, ReturnType.DATAFRAME).loc[0, "x"], 1)
        self.assertEqual(
            convert_result(
                {"symbol": "SPY", "expirations": [{"expiration": "x", "gex_by_strike": {"1": {}}}]},
                ReturnType.DATAFRAME,
            ).loc[0, "strike"],
            1,
        )
        self.assertEqual(convert_result({"gex_by_strike": {"1": 5}}, ReturnType.DATAFRAME).loc[0, "strike"], 1)
        with self.assertRaises(ITMatrixAPIError):
            decode_public(_ENCODER.encode({"status": "error", "requestId": "r1", "error": "no"}), list[str])
        with self.assertRaises(ITMatrixAPIError):
            decode_public(_ENCODER.encode({"error": "limited"}), list[str])

    def test_async_client_uses_async_transport_and_context(self) -> None:
        """Async mode exposes awaitable data methods without thread wrapping."""

        async def run_case() -> None:
            async with ITMatrixV1("itm_test", base_url="http://example.test", async_mode=True) as client:
                client._async_transport = FakeAsyncTransport()
                result = await client.spot("spy")
                self.assertIsInstance(result, Spot)
                self.assertEqual(result.symbol, "SPY")

            alias = ITMatrixV1("itm_test", base_url="http://example.test", **{"async": True})
            alias._async_transport = FakeAsyncTransport()
            self.assertEqual((await alias.available("symbols"))[0], "SPY")
            self.assertEqual((await alias.available("expirations", symbol="spy"))["symbol"], "SPY")
            self.assertEqual((await alias.available("tickers"))[0], "AAPL")
            with self.assertRaises(TypeError):
                await alias.available("expirations")
            await alias.close()
            await ITMatrixV1("itm_test", base_url="http://example.test", async_mode=True).close()
            with self.assertRaises(RuntimeError):
                broken = ITMatrixV1("itm_test", base_url="http://example.test", async_mode=True)
                await broken._get_async(list[str], "/symbols")

        asyncio.run(run_case())

    def test_transports_against_local_http_server(self) -> None:
        """The concrete sync and aiohttp transports handle status and connection errors."""

        server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        async def run_case() -> None:
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                sync_body = SyncTransport(base_url, {"X-API-Key": "itm"}, timeout=5).get(
                    "/api/v1/symbols",
                    {"items": ["a", "b"], "adjusted": True, "plain": "x", "empty": None},
                )
                async_transport = AiohttpTransport(base_url, {"X-API-Key": "itm"}, timeout=5)
                async_body = await async_transport.get("/api/v1/symbols")
                repeat_body = await async_transport.get("/api/v1/symbols")
                with self.assertRaises(ITMatrixHTTPError):
                    await async_transport.get("/fail")
                await async_transport.close()
                await AiohttpTransport(base_url, {}, timeout=5).close()
                live_client = ITMatrixV1("itm", base_url=base_url, async_mode=True)
                self.assertEqual((await live_client.available("symbols"))[0], "SPY")
                await live_client.close()
                with self.assertRaises(ITMatrixHTTPError):
                    SyncTransport(base_url, {}, timeout=5).get("/fail")
                with self.assertRaises(ITMatrixConnectionError):
                    SyncTransport("http://127.0.0.1:1", {}, timeout=0.01).get("/")
                with self.assertRaises(ITMatrixConnectionError):
                    await AiohttpTransport("http://127.0.0.1:1", {}, timeout=0.01).get("/")
            finally:
                server.shutdown()
                thread.join(timeout=1)

            self.assertEqual(decode_public(sync_body, list[str]), ["SPY"])
            self.assertEqual(decode_public(async_body, list[str]), ["SPY"])
            self.assertEqual(decode_public(repeat_body, list[str]), ["SPY"])

        asyncio.run(run_case())

    def test_stream_subscriptions_yield_msgspec_structs(self) -> None:
        """The stream factory shares one socket and yields typed events."""

        async def run_case() -> None:
            app = web.Application()
            frames: list[dict[str, Any]] = []

            async def ws_handler(_request: web.Request) -> web.WebSocketResponse:
                """Echo subscription actions and push one typed spot tick."""

                ws = web.WebSocketResponse()
                await ws.prepare(_request)
                async for message in ws:
                    data = message.data if isinstance(message.data, bytes) else message.data.encode()
                    payload = _DECODER.decode(data)
                    frames.append(payload)
                    if payload["action"] == "subscribe":
                        await asyncio.sleep(0.05)
                        event = {"channel": "spot", "symbol": "SPY", "price": 612.34, "t": 1}
                        await ws.send_bytes(_ENCODER.encode(event))
                return ws

            app.router.add_get("/ws", ws_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            try:
                async with ITStream("itm_test", base_url=f"http://127.0.0.1:{port}") as stream:
                    first = await stream.spot("spy")
                    second = await stream.spot("SPY")
                    self.assertIs(first.__aiter__(), first)
                    self.assertIs(await first.start(), first)
                    event = await asyncio.wait_for(first.__anext__(), timeout=1)
                    second_event = await asyncio.wait_for(second.__anext__(), timeout=1)
                    await first.stop()
                    with self.assertRaises(StopAsyncIteration):
                        await first.__anext__()
                    await second.stop()
                    async with stream.options("SPY", expiration="2026-05-15", strikes=[600]):
                        pass
                    gex_sub = await stream.gex("SPY")
                    self.assertFalse(gex_sub.matches(WsEvent(channel="spot", symbol="QQQ")))
                    self.assertTrue(gex_sub.matches(WsEvent(channel="gex:update", symbol="SPY")))
                    option_sub = stream.options("SPY", expiration="2026-05-15", strikes=[600])
                    self.assertFalse(option_sub.matches(WsEvent(channel="spot", symbol="SPY")))
                    wrong_expiration = WsEvent(channel="options", symbol="SPY", expiration="x", strike=600)
                    self.assertFalse(option_sub.matches(wrong_expiration))
                    self.assertTrue(
                        option_sub.matches(
                            WsEvent(channel="options", symbol="SPY", expiration="2026-05-15", strike=600),
                        ),
                    )
                    first.feed(WsEvent(channel="spot", symbol="SPY"))
                    await first.stop()
                    await stream.close()
                    await stream._receive()
                    await stream._send("subscribe", stream.gex("SPY")._key)
                self.assertIsInstance(event, WsEvent)
                self.assertEqual(second_event.price, 612.34)
                options_frame = {
                    "action": "subscribe",
                    "channel": "options",
                    "symbol": "SPY",
                    "expiration": "2026-05-15",
                    "strikes": [600],
                }
                self.assertIn(options_frame, frames)
            finally:
                await runner.cleanup()

        asyncio.run(run_case())

    @staticmethod
    def test_stream_defensive_socket_branches() -> None:
        """The stream receiver tolerates non-data and error frames."""

        async def run_case() -> None:
            stream = ITStream("itm_test", base_url="http://example.test")
            sub = stream.spot("SPY")
            stream._subs[sub._key] = {sub}
            stream._ws = FakeWebSocket(
                [
                    FakeWsMessage(aiohttp.WSMsgType.CLOSED, b""),
                    FakeWsMessage(aiohttp.WSMsgType.TEXT, b'{"channel":"spot","symbol":"QQQ"}'),
                    FakeWsMessage(aiohttp.WSMsgType.ERROR, b""),
                ],
            )

            await stream._receive()
            await stream._stop(stream.spot("MSFT"))

        asyncio.run(run_case())


class FakeWsMessage:
    """Minimal aiohttp WebSocket message fixture."""

    def __init__(self, kind: aiohttp.WSMsgType, data: bytes) -> None:
        """Store the frame type and payload used by the receiver."""

        self.type = kind
        self.data = data


class FakeWebSocket:
    """Async iterable fake WebSocket used for receiver branch tests."""

    closed = False

    def __init__(self, messages: list[FakeWsMessage]) -> None:
        """Store the finite frame stream."""

        self._messages = messages

    def __aiter__(self) -> FakeWebSocket:
        """Return this object as its own async iterator."""

        return self

    async def __anext__(self) -> FakeWsMessage:
        """Return the next fake frame."""

        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send_bytes(self, _data: bytes) -> None:
        """Satisfy the send protocol for defensive stop calls."""


class LocalHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler for concrete transport tests."""

    def do_GET(self) -> None:
        """Return an envelope or an HTTP error for the requested path."""

        if self.path.startswith("/fail"):
            self.send_error(500, "boom")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_envelope(["SPY"]))

    def log_message(self, _format: str, *_args: Any) -> None:
        """Silence server logs during tests."""


def _fake_response(path: str) -> bytes:
    """Return documented endpoint payloads for the client fixture."""

    routes: dict[str, Any] = {
        "/api/v1/symbols": ["SPY", "QQQ"],
        "/api/v1/expirations/SPY": {"symbol": "SPY", "expirations": ["2026-05-15"]},
        "/api/v1/fundamentals/tickers": ["AAPL", "MSFT"],
        "/api/v1/spot/SPY": {"symbol": "SPY", "price": 612.34, "updatedAt": "2026-05-03T14:35:00.000Z"},
        "/api/v1/options/O%3ASPY260417C00600000": _option_payload(),
        "/api/v1/gex/SPY": _gex_payload(),
        "/api/v1/gex/SPY/matrix": {"symbol": "SPY", "expirations": [_gex_payload()]},
        "/api/v1/gex/SPY/history": {
            "symbol": "SPY",
            "date": "2026-05-03",
            "snapshots": [{"capturedAt": "2026-05-03T14:35:00.000Z", "spotPrice": 612.34, "netGex": {}}],
        },
        "/api/v1/stock/SPY/bars": [{"t": 1, "price": 612.34}],
        "/api/v1/options/O%3ASPY260417C00600000/bars": [{"t": 1, "price": 18.42}],
        "/api/v1/fundamentals/ratios/AAPL": [{"ticker": "AAPL", "date": "2026-05-03", "price": 1.0}],
        "/api/v1/fundamentals/income/AAPL": [{"ticker": "AAPL", "revenue": 1.0}],
        "/api/v1/fundamentals/balance-sheet/AAPL": [{"ticker": "AAPL", "total_assets": 1.0}],
        "/api/v1/fundamentals/cash-flow/AAPL": [{"ticker": "AAPL", "capex": -1.0}],
        "/api/v1/fundamentals/dividends/AAPL": [{"ticker": "AAPL", "cash_amount": 0.25}],
        "/api/v1/fundamentals/splits/AAPL": [{"ticker": "AAPL", "split_to": 4.0}],
        "/api/v1/fundamentals/short-interest/AAPL": [{"ticker": "AAPL", "days_to_cover": 2.0}],
        "/api/v1/fundamentals/float/AAPL": {"ticker": "AAPL", "free_float": 1.0},
        "/api/v1/fundamentals/news/AAPL": [{"id": "n1"}],
        "/api/v1/fundamentals/economy/treasury-yields": [{"date": "2026-05-03", "y10y": 4.0}],
        "/api/v1/fundamentals/economy/inflation": [{"date": "2026-05-03", "cpi": 1.0}],
        "/api/v1/fundamentals/economy/labor": [{"date": "2026-05-03", "unemployment_rate": 4.0}],
    }
    try:
        return _envelope(routes[path])
    except KeyError as error:
        raise AssertionError(path) from error


def _option_payload() -> dict[str, Any]:
    """Return a current option quote payload."""

    return {
        "ticker": "O:SPY260417C00600000",
        "underlying": "SPY",
        "expiration": "2026-04-17",
        "strike": 600,
        "contractType": "call",
    }


def _gex_payload() -> dict[str, Any]:
    """Return a current GEX payload with one strike row."""

    return {
        "symbol": "SPY",
        "expiration": "2026-05-15",
        "spotPrice": 612.34,
        "updatedAt": "2026-05-03T14:35:00.000Z",
        "netGex": {},
        "maxAbsGex": {},
        "zeroGammaLevel": 600,
        "strikes": [600],
        "gexByStrike": {"600": {"totalGexShares": 1, "callTicker": "C", "putTicker": "P"}},
    }


def _envelope(results: Any) -> bytes:
    """Encode a standard public API envelope."""

    return _ENCODER.encode({"status": "ok", "requestId": "req-test", "results": results})
