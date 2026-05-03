2026-05-03:
- Implemented the new `mhq` Python client library for the ITMatrix public v1 API, including sync/async HTTP clients, msgspec schemas/decoding, dataframe and NumPy column return modes, key resolution, and WebSocket subscription streams.
- Added package metadata from the temp pyproject with base dependencies and platform event-loop extras (`mhq[win]` for winloop, `mhq[linux]` for uvloop).
- Added local unit coverage for the public client, conversion modes, transports, and stream subscriptions.
- Live smoke against the placeholder default host failed because `api.itmatrix.io` did not resolve in this environment; local HTTP/WebSocket fixtures cover the client behavior.
- Updated the default API URL to `https://api.itmatrixhq.com/` and added independent live-test switches for HTTP (`MHQ_TEST_LIVE_V1`) and WebSocket (`MHQ_TEST_LIVE_STREAM`); HTTP live smoke passed, WebSocket live smoke was not run while markets were closed.
