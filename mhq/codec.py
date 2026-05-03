from __future__ import annotations

from typing import Any

import msgspec

from mhq.enums import ReturnType
from mhq.exceptions import ITMatrixAPIError
from mhq.models import ErrorPayload, PublicEnvelope, WsEvent

_DECODERS: dict[Any, msgspec.json.Decoder[Any]] = {}
_ENCODER = msgspec.json.Encoder()


def decoder_for(schema: Any) -> msgspec.json.Decoder[Any]:
    """Return a cached JSON decoder for a known schema."""

    decoder = _DECODERS.get(schema)
    if decoder is None:
        decoder = msgspec.json.Decoder(type=schema)
        _DECODERS[schema] = decoder
    return decoder


def decode_json(data: bytes | bytearray | memoryview | str, schema: Any) -> Any:
    """Decode raw JSON with a cached msgspec decoder."""

    return decoder_for(schema).decode(data)


def encode_json(value: Any) -> bytes:
    """Encode a JSON frame with msgspec."""

    return _ENCODER.encode(value)


def decode_public(data: bytes, result_schema: Any) -> Any:
    """Decode a public API envelope or direct result payload."""

    envelope_schema = PublicEnvelope[result_schema]
    try:
        envelope = decode_json(data, envelope_schema)
    except msgspec.ValidationError:
        return _decode_direct_or_error(data, result_schema)
    if envelope.status != "ok":
        raise ITMatrixAPIError(envelope.error or "ITMatrix API returned an error.", request_id=envelope.request_id)
    return envelope.results


def decode_ws_message(data: bytes | bytearray | memoryview | str) -> WsEvent:
    """Decode a WebSocket message into the stream event struct."""

    return decode_json(data, WsEvent)


def convert_result(value: Any, return_type: ReturnType) -> Any:
    """Convert msgspec objects into the configured user-facing return form."""

    if return_type is ReturnType.STRUCT:
        return value
    rows = _rows_from_value(value)
    if return_type is ReturnType.DATAFRAME:
        import pandas as pd

        return pd.DataFrame.from_records(rows)
    import numpy as np

    columns = _column_names(rows)
    return {column: np.asarray([row.get(column) for row in rows]) for column in columns}


def to_builtin(value: Any) -> Any:
    """Convert msgspec structs to plain Python containers."""

    return msgspec.to_builtins(value)


def _decode_direct_or_error(data: bytes, result_schema: Any) -> Any:
    """Handle direct result payloads and non-envelope error shapes."""

    try:
        error = decode_json(data, ErrorPayload)
    except msgspec.ValidationError:
        return decode_json(data, result_schema)
    raise ITMatrixAPIError(error.error)


def _rows_from_value(value: Any) -> list[dict[str, Any]]:
    """Flatten common ITMatrix result shapes into tabular records."""

    built = to_builtin(value)
    if built is None:
        return []
    if isinstance(built, list):
        return _rows_from_list(built)
    if isinstance(built, dict):
        return _rows_from_dict(built)
    return [{"value": built}]


def _rows_from_list(items: list[Any]) -> list[dict[str, Any]]:
    """Normalize list results without rebuilding nested dict rows unnecessarily."""

    if not items:
        return []
    if all(isinstance(item, dict) for item in items):
        return items
    return [{"value": item} for item in items]


def _rows_from_dict(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten nested API result containers that naturally describe rows."""

    if "gex_by_strike" in item or "gexByStrike" in item:
        return _gex_rows(item)
    if "expirations" in item and isinstance(item["expirations"], list):
        return _expiration_rows(item)
    if "snapshots" in item and isinstance(item["snapshots"], list):
        return _child_rows(item, "snapshots")
    return [item]


def _expiration_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten matrix expirations, preserving captured snapshot metadata."""

    rows: list[dict[str, Any]] = []
    for expiration in item["expirations"]:
        if not isinstance(expiration, dict):
            rows.append({"symbol": item.get("symbol"), "expiration": expiration})
            continue
        if "gex_by_strike" in expiration or "gexByStrike" in expiration:
            rows.extend(_gex_rows(expiration, captured_at=item.get("captured_at")))
        else:
            rows.append({"symbol": item.get("symbol"), "captured_at": item.get("captured_at"), **expiration})
    return rows


def _child_rows(item: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Flatten a child row collection under a parent result."""

    rows: list[dict[str, Any]] = []
    parent = {name: value for name, value in item.items() if name != key}
    for child in item[key]:
        if isinstance(child, dict):
            rows.append({**parent, **child})
        else:
            rows.append({**parent, "value": child})
    return rows


def _gex_rows(item: dict[str, Any], *, captured_at: str | None = None) -> list[dict[str, Any]]:
    """Flatten a GEX-by-strike mapping into one row per strike."""

    rows: list[dict[str, Any]] = []
    shared = {
        "symbol": item.get("symbol"),
        "expiration": item.get("expiration"),
        "spot_price": item.get("spot_price", item.get("spotPrice")),
        "updated_at": item.get("updated_at", item.get("updatedAt")),
        "captured_at": captured_at,
        "zero_gamma_level": item.get("zero_gamma_level", item.get("zeroGammaLevel")),
    }
    by_strike = item.get("gex_by_strike", item.get("gexByStrike", {}))
    for strike, values in by_strike.items():
        row = {**shared, "strike": float(strike)}
        if isinstance(values, dict):
            row.update(values)
        rows.append(row)
    return rows


def _column_names(rows: list[dict[str, Any]]) -> list[str]:
    """Preserve first-seen column order for NumPy column conversion."""

    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names
