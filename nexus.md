mhq/auth.py resolves API keys and base URLs for HTTP and WebSocket clients.
- os : Reads `ITM_KEY` and `ITM_BASE_URL` from the process environment.
- pathlib.Path : Checks and reads the fallback `.itmkey` file from the working root.
- mhq.exceptions.ITMatrixConfigError : Raises a package-specific error when no key source is available.

mhq/client.py provides the public `ITMatrixV1` sync/async API surface for `/api/v1` endpoints.
- collections.abc.Awaitable : Annotates methods that return awaitables when async mode is enabled.
- typing.Any : Holds dynamic msgspec schema types and flexible public query values.
- urllib.parse.quote : Safely encodes symbols and option tickers into path components.
- mhq.auth : Resolves keys and base URLs at instance construction.
- mhq.codec : Decodes API envelopes, converts msgspec results to dataframe or NumPy-column modes, and returns plain availability data.
- mhq.enums : Stores the instance-wide return type setting and normalizes user aliases.
- mhq.models : Supplies pre-known msgspec schemas for all public endpoint result shapes.
- mhq.transport : Provides the blocking and aiohttp GET transports used by the client.

mhq/codec.py centralizes msgspec JSON encoding, decoding, public envelope handling, WebSocket decoding, and result conversion.
- typing.Any : Allows decoder caching by arbitrary schema and dynamic conversion inputs.
- msgspec : Performs fast JSON decode/encode, struct conversion, and validation-driven casting.
- mhq.enums.ReturnType : Selects struct, pandas dataframe, or NumPy column-dict conversion.
- mhq.exceptions.ITMatrixAPIError : Raises API-envelope failures with the request id when provided.
- mhq.models : Supplies the public envelope, middleware error, and WebSocket event schemas.

mhq/models.py defines msgspec structs for public API results and WebSocket events.
- typing.Generic : Parameterizes the public response envelope by endpoint result schema.
- typing.TypeVar : Carries the generic result type for envelope decoding.
- msgspec : Provides fast typed structs and default factories for mutable result fields.

mhq/stream.py implements the `ITStream` WebSocket factory and logical subscription iterators.
- asyncio : Owns subscription queues, locks, receiver tasks, and async iterator behavior.
- collections.Counter : Tracks how many logical subscriptions share each channel/symbol key.
- collections.abc.Iterable : Accepts strike collections without forcing a specific container type.
- dataclasses.dataclass : Defines the immutable counted subscription key with slots.
- typing.Any : Types outbound subscribe/unsubscribe JSON payloads.
- urllib.parse : Derives a `/ws` URL from the configured HTTP base URL.
- aiohttp : Opens the singleton WebSocket connection and reads frames asynchronously.
- mhq.auth : Resolves stream key and base URL configuration.
- mhq.codec : Encodes subscription frames and decodes inbound frames into msgspec event structs.
- mhq.models.WsEvent : Provides the object yielded by subscription streams.

mhq/transport.py contains the HTTP transport layer for async and blocking requests.
- collections.abc.Mapping : Accepts read-only header and query mappings.
- typing.Any : Supports arbitrary query values before string normalization.
- urllib.error : Converts blocking HTTP and connection failures into package exceptions.
- urllib.parse.urlencode : Encodes blocking transport query strings.
- urllib.request : Performs actual synchronous blocking GET requests without thread wrapping.
- aiohttp : Performs async GET requests and owns lazy async sessions.
- mhq.exceptions : Raises package-specific connection and HTTP status errors.
