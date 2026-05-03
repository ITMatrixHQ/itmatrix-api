tests/unit/test_client.py: ClientTests - Exercises the public client package through local fixtures, covering key resolution, sync and async `/api/v1` method routing, return conversion modes, transport errors, and WebSocket subscriptions without relying on the live deployment URL.
- mhq.client: General public `ITMatrixV1` behavior.
	- ITMatrixV1.__init__: Covers explicit keys, `.itmkey` files, environment keys, environment base URLs, async alias handling, and unknown option rejection.
	- ITMatrixV1.available: Covers `symbols`, `expirations`, and fundamentals ticker availability in sync and async modes, including missing-symbol and unknown-endpoint errors.
	- ITMatrixV1 spot/option/gex/gex_matrix/gex_history/stock_bars/option_bars/fundamentals/economy: Covers documented public endpoint path construction and msgspec result decoding.
	- ITMatrixV1.close/context managers: Covers sync and async close paths plus context-manager entry/exit behavior.
- mhq.codec: General response decoding and return conversion behavior.
	- decode_public: Covers standard envelopes, direct payloads, envelope errors, and middleware-style error bodies.
	- convert_result: Covers struct passthrough, pandas dataframe conversion, NumPy column conversion, scalar rows, empty rows, snapshot flattening, expiration flattening, and GEX-by-strike flattening.
	- decode_ws_message/to_builtin: Covers WebSocket frame decoding into msgspec structs and conversion back to builtins.
- mhq.transport: Concrete HTTP transport behavior.
	- SyncTransport.get: Covers successful blocking requests, query normalization, HTTP error wrapping, and connection error wrapping.
	- AiohttpTransport.get/close: Covers successful async requests, session reuse, HTTP error wrapping, timeout/connection wrapping, and no-session close.
- mhq.stream: WebSocket subscription behavior.
	- ITStream.subscribe/spot/gex/options/close: Covers shared socket subscription counting, channel-specific payloads, close-all cleanup, and URL derivation through local WebSocket fixtures.
	- ITSubscription start/stop/async iteration/matches: Covers awaitable starts, duplicate starts, stop signals, shared subscriber routing, option and GEX matching, inactive feeds, and defensive receiver branches.

Unreachable or intentionally residual coverage notes:
- mhq.codec has one partial branch in column-name de-duplication where every practical non-empty tabular conversion still enters the first-seen path; total package coverage remains 99%.
