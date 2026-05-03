2026-05-03:
- Implemented the new `mhq` Python client library for the ITMatrix public v1 API, including sync/async HTTP clients, msgspec schemas/decoding, dataframe and NumPy column return modes, key resolution, and WebSocket subscription streams.
- Added package metadata from the temp pyproject with base dependencies and platform event-loop extras (`mhq[win]` for winloop, `mhq[linux]` for uvloop).
- Added local unit coverage for the public client, conversion modes, transports, and stream subscriptions.
- Live smoke against the placeholder default host failed because `api.itmatrix.io` did not resolve in this environment; local HTTP/WebSocket fixtures cover the client behavior.
