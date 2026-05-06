from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://api.itmatrixhq.com"
ENV_KEY_NAMES = ("MHQ_KEY", "MHQ_API_KEY")
FUNDAMENTAL_ENDPOINTS = (
    "ratios",
    "income",
    "balance-sheet",
    "cash-flow",
    "dividends",
    "splits",
    "short-interest",
    "float",
    "news",
)
ECONOMY_ENDPOINTS = ("treasury-yields", "inflation", "labor")
LIMITED_FUNDAMENTALS = {"dividends": 20, "short-interest": 50, "news": 10}
PERIOD_FUNDAMENTALS = {"income", "balance-sheet", "cash-flow"}


@dataclass(slots=True)
class ApiClient:
    """Small stdlib-only blocking `/api/v1` client."""

    base_url: str
    key: str
    timeout: float
    calls: list[dict[str, Any]] = field(default_factory=list)

    def get(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        """Fetch a public v1 path and return the unwrapped result payload."""

        clean_query = clean_query_values(query)
        url = build_url(self.base_url, path, clean_query)
        request = Request(url, headers={"X-API-Key": self.key}, method="GET")
        self.calls.append({"path": path, "query": clean_query})
        try:
            # The public API uses simple GET requests, so urllib is sufficient here.
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(http_error_message(error)) from error
        except URLError as error:
            raise RuntimeError(f"Connection failed for {url}: {error.reason}") from error
        return unwrap_payload(payload)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process status code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    client = ApiClient(resolve_base_url(args.base_url), resolve_key(args.key, args.key_file), args.timeout)
    data = args.handler(client, args)
    document = build_document(args.command, client.base_url, data, client.calls)
    output_path = write_json(document, resolve_output(args.output, args.command), pretty=args.pretty)
    print(output_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the command parser with one subcommand per v1 route family."""

    parser = argparse.ArgumentParser(description="Dump MHQ `/api/v1` data to static-site friendly JSON.")
    parser.add_argument("--key", help="API key. Defaults to MHQ_KEY, MHQ_API_KEY, then .mhqkey.")
    parser.add_argument("--key-file", default=".mhqkey", help="Key file fallback path. Defaults to .mhqkey in CWD.")
    parser.add_argument("--base-url", default=None, help="API base URL. Defaults to MHQ_BASE_URL or live MHQ.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout in seconds.")
    parser.add_argument("-o", "--output", help="Output JSON path. Defaults to CWD.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON instead of compact JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_simple_command(subparsers, "symbols", fetch_symbols)
    add_simple_command(subparsers, "fundamentals-tickers", fetch_fundamentals_tickers)
    add_symbol_command(subparsers, "expirations", fetch_expirations)
    add_symbol_command(subparsers, "spot", fetch_spot)
    add_option_command(subparsers, "option", fetch_option)
    add_gex_command(subparsers)
    add_gex_matrix_command(subparsers)
    add_gex_history_command(subparsers)
    add_stock_bars_command(subparsers)
    add_option_bars_command(subparsers)
    add_fundamentals_command(subparsers)
    add_economy_command(subparsers)
    add_all_command(subparsers)
    return parser


def add_simple_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Callable[[ApiClient, argparse.Namespace], Any],
) -> None:
    """Register a command that has no endpoint-specific arguments."""

    command = subparsers.add_parser(name)
    command.set_defaults(handler=handler)


def add_symbol_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Callable[[ApiClient, argparse.Namespace], Any],
) -> None:
    """Register a command that needs a stock or index symbol."""

    command = subparsers.add_parser(name)
    command.add_argument("--symbol", required=True)
    command.set_defaults(handler=handler)


def add_option_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Callable[[ApiClient, argparse.Namespace], Any],
) -> None:
    """Register a command that needs an OCC option ticker."""

    command = subparsers.add_parser(name)
    command.add_argument("--ticker", required=True)
    command.set_defaults(handler=handler)


def add_gex_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the current GEX-by-strike command."""

    command = subparsers.add_parser("gex")
    command.add_argument("--symbol", required=True)
    command.add_argument("--expiration", required=True)
    add_strike_filters(command)
    command.set_defaults(handler=fetch_gex)


def add_gex_matrix_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the GEX matrix command."""

    command = subparsers.add_parser("gex-matrix")
    command.add_argument("--symbol", required=True)
    command.add_argument("--expirations", action="append", help="Comma-separated expiration list; repeatable.")
    command.add_argument("--at", help="Historical ISO-8601 timestamp.")
    command.set_defaults(handler=fetch_gex_matrix)


def add_gex_history_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the intraday GEX history command."""

    command = subparsers.add_parser("gex-history")
    command.add_argument("--symbol", required=True)
    command.add_argument("--date", help="History date in YYYY-MM-DD.")
    command.set_defaults(handler=fetch_gex_history)


def add_stock_bars_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the stock bars command."""

    command = subparsers.add_parser("stock-bars")
    command.add_argument("--symbol", required=True)
    add_bar_window(command, default_timespan="minute")
    command.add_argument("--adjusted", choices=("true", "false"), default="true")
    command.add_argument("--sort", choices=("asc", "desc"), default="asc")
    command.set_defaults(handler=fetch_stock_bars)


def add_option_bars_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the option bars command."""

    command = subparsers.add_parser("option-bars")
    command.add_argument("--ticker", required=True)
    add_bar_window(command, default_timespan="minute")
    command.set_defaults(handler=fetch_option_bars)


def add_fundamentals_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the symbol fundamentals command."""

    command = subparsers.add_parser("fundamentals")
    command.add_argument("--endpoint", required=True, choices=FUNDAMENTAL_ENDPOINTS)
    command.add_argument("--symbol", required=True)
    command.add_argument("--timeframe", default="quarterly")
    command.add_argument("--limit", type=int)
    command.set_defaults(handler=fetch_fundamentals)


def add_economy_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the economy fundamentals command."""

    command = subparsers.add_parser("economy")
    command.add_argument("--endpoint", required=True, choices=ECONOMY_ENDPOINTS)
    command.add_argument("--limit", type=int)
    command.set_defaults(handler=fetch_economy)


def add_all_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the aggregate full-v1 dump command."""

    command = subparsers.add_parser("all")
    command.add_argument(
        "--symbols",
        action="append",
        help="Comma-separated symbols; repeatable. Defaults to /symbols.",
    )
    command.add_argument("--fundamental-symbols", action="append", help="Defaults to /fundamentals/tickers.")
    command.add_argument("--option-tickers", action="append", help="Comma-separated OCC tickers; repeatable.")
    command.add_argument("--expirations", action="append", help="Comma-separated expirations reused for every symbol.")
    command.add_argument("--from-date", required=True, help="Bars start date in YYYY-MM-DD.")
    command.add_argument("--to-date", required=True, help="Bars end date in YYYY-MM-DD.")
    command.add_argument("--stock-multiplier", type=int, default=1)
    command.add_argument("--stock-timespan", default="day")
    command.add_argument("--option-multiplier", type=int, default=1)
    command.add_argument("--option-timespan", default="minute")
    command.add_argument("--timeframe", default="quarterly")
    command.add_argument("--limit", type=int)
    command.add_argument("--economy-limit", type=int)
    command.add_argument("--keep-going", action="store_true", help="Record endpoint errors and continue.")
    command.set_defaults(handler=fetch_all)


def add_bar_window(command: argparse.ArgumentParser, *, default_timespan: str) -> None:
    """Add shared bar query arguments."""

    command.add_argument("--from-date", required=True, help="Start date in YYYY-MM-DD.")
    command.add_argument("--to-date", required=True, help="End date in YYYY-MM-DD.")
    command.add_argument("--multiplier", type=int, default=1)
    command.add_argument("--timespan", default=default_timespan)


def add_strike_filters(command: argparse.ArgumentParser) -> None:
    """Add supported GEX strike filter arguments."""

    command.add_argument("--strike-gt", type=float)
    command.add_argument("--strike-gte", type=float)
    command.add_argument("--strike-lt", type=float)
    command.add_argument("--strike-lte", type=float)
    command.add_argument("--strike-eq", type=float)


def fetch_symbols(client: ApiClient, _args: argparse.Namespace) -> Any:
    """Fetch `/symbols`."""

    return client.get("/symbols")


def fetch_fundamentals_tickers(client: ApiClient, _args: argparse.Namespace) -> Any:
    """Fetch `/fundamentals/tickers`."""

    return client.get("/fundamentals/tickers")


def fetch_expirations(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/expirations/:symbol`."""

    return client.get(f"/expirations/{path_symbol(args.symbol)}")


def fetch_spot(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/spot/:symbol`."""

    return client.get(f"/spot/{path_symbol(args.symbol)}")


def fetch_option(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/options/:ticker`."""

    return client.get(f"/options/{path_part(args.ticker)}")


def fetch_gex(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/gex/:symbol`."""

    return client.get(f"/gex/{path_symbol(args.symbol)}", gex_query(args))


def fetch_gex_matrix(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/gex/:symbol/matrix`."""

    return client.get(
        f"/gex/{path_symbol(args.symbol)}/matrix",
        {"expirations": csv_values(args.expirations), "at": args.at},
    )


def fetch_gex_history(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/gex/:symbol/history`."""

    return client.get(f"/gex/{path_symbol(args.symbol)}/history", {"date": args.date})


def fetch_stock_bars(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/stock/:symbol/bars`."""

    query = {
        "multiplier": args.multiplier,
        "timespan": args.timespan,
        "from": args.from_date,
        "to": args.to_date,
        "adjusted": args.adjusted,
        "sort": args.sort,
    }
    return client.get(f"/stock/{path_symbol(args.symbol)}/bars", query)


def fetch_option_bars(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch `/options/:ticker/bars`."""

    query = {"multiplier": args.multiplier, "timespan": args.timespan, "from": args.from_date, "to": args.to_date}
    return client.get(f"/options/{path_part(args.ticker)}/bars", query)


def fetch_fundamentals(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch one public symbol fundamentals endpoint."""

    return client.get(f"/fundamentals/{args.endpoint}/{path_symbol(args.symbol)}", fundamentals_query(args))


def fetch_economy(client: ApiClient, args: argparse.Namespace) -> Any:
    """Fetch one public economy endpoint."""

    return client.get(f"/fundamentals/economy/{args.endpoint}", {"limit": args.limit})


def fetch_all(client: ApiClient, args: argparse.Namespace) -> dict[str, Any]:
    """Fetch every `/api/v1` endpoint family into one document."""

    data: dict[str, Any] = {"errors": []}
    data["symbols"] = client.get("/symbols")
    data["fundamentalsTickers"] = client.get("/fundamentals/tickers")
    symbols = csv_values(args.symbols) or data["symbols"]
    fundamental_symbols = csv_values(args.fundamental_symbols) or data["fundamentalsTickers"]
    option_tickers = csv_values(args.option_tickers)
    data["expirations"] = fetch_all_expirations(client, args, symbols)
    data["spot"] = fetch_each(args, symbols, lambda symbol: client.get(f"/spot/{path_symbol(symbol)}"))
    data["gex"] = fetch_all_gex(client, args, symbols, data["expirations"])
    data["gexMatrix"] = fetch_each(
        args,
        symbols,
        lambda symbol: client.get(
            f"/gex/{path_symbol(symbol)}/matrix",
            {"expirations": expiration_list_for_symbol(args, data["expirations"], symbol)},
        ),
    )
    data["gexHistory"] = fetch_each(
        args,
        symbols,
        lambda symbol: client.get(f"/gex/{path_symbol(symbol)}/history"),
    )
    data["stockBars"] = fetch_each(args, symbols, lambda symbol: fetch_stock_bar_symbol(client, args, symbol))
    data["options"] = fetch_each(args, option_tickers, lambda ticker: client.get(f"/options/{path_part(ticker)}"))
    data["optionBars"] = fetch_each(args, option_tickers, lambda ticker: fetch_option_bar_ticker(client, args, ticker))
    data["fundamentals"] = fetch_all_fundamentals(client, args, fundamental_symbols)
    data["economy"] = {
        endpoint: catch(
            args,
            lambda endpoint=endpoint: client.get(f"/fundamentals/economy/{endpoint}", economy_query(args)),
        )
        for endpoint in ECONOMY_ENDPOINTS
    }
    return data


def fetch_all_expirations(client: ApiClient, args: argparse.Namespace, symbols: Iterable[str]) -> dict[str, Any]:
    """Fetch expirations for every selected symbol unless a shared list was provided."""

    shared = csv_values(args.expirations)
    if shared:
        return {symbol: {"symbol": symbol, "expirations": shared} for symbol in symbols}
    return fetch_each(args, symbols, lambda symbol: client.get(f"/expirations/{path_symbol(symbol)}"))


def fetch_all_gex(
    client: ApiClient,
    args: argparse.Namespace,
    symbols: Iterable[str],
    expirations_by_symbol: Mapping[str, Any],
) -> dict[str, Any]:
    """Fetch current GEX for every selected symbol expiration."""

    data: dict[str, Any] = {}
    for symbol in symbols:
        expirations = expiration_list_for_symbol(args, expirations_by_symbol, symbol)
        data[symbol] = fetch_each(
            args,
            expirations,
            lambda expiration, symbol=symbol: client.get(f"/gex/{path_symbol(symbol)}", {"expiration": expiration}),
        )
    return data


def fetch_all_fundamentals(client: ApiClient, args: argparse.Namespace, symbols: Iterable[str]) -> dict[str, Any]:
    """Fetch all public fundamentals endpoint families for every selected symbol."""

    data: dict[str, Any] = {}
    for endpoint in FUNDAMENTAL_ENDPOINTS:
        data[endpoint] = fetch_each(
            args,
            symbols,
            lambda symbol, endpoint=endpoint: client.get(
                f"/fundamentals/{endpoint}/{path_symbol(symbol)}",
                aggregate_fundamentals_query(args, endpoint),
            ),
        )
    return data


def fetch_stock_bar_symbol(client: ApiClient, args: argparse.Namespace, symbol: str) -> Any:
    """Fetch one symbol's aggregate stock bars for the aggregate command."""

    query = {
        "multiplier": args.stock_multiplier,
        "timespan": args.stock_timespan,
        "from": args.from_date,
        "to": args.to_date,
        "adjusted": "true",
        "sort": "asc",
    }
    return client.get(f"/stock/{path_symbol(symbol)}/bars", query)


def fetch_option_bar_ticker(client: ApiClient, args: argparse.Namespace, ticker: str) -> Any:
    """Fetch one option ticker's bars for the aggregate command."""

    query = {
        "multiplier": args.option_multiplier,
        "timespan": args.option_timespan,
        "from": args.from_date,
        "to": args.to_date,
    }
    return client.get(f"/options/{path_part(ticker)}/bars", query)


def fetch_each(args: argparse.Namespace, values: Iterable[str], getter: Callable[[str], Any]) -> dict[str, Any]:
    """Fetch keyed values, optionally recording per-item errors."""

    data: dict[str, Any] = {}
    for value in values:
        data[value] = catch(args, lambda value=value: getter(value))
    return data


def catch(args: argparse.Namespace, getter: Callable[[], Any]) -> Any:
    """Return endpoint data or an error record when `--keep-going` is enabled."""

    try:
        return getter()
    except RuntimeError as error:
        if getattr(args, "keep_going", False):
            return {"error": str(error)}
        raise


def gex_query(args: argparse.Namespace) -> dict[str, Any]:
    """Build the current GEX query from CLI arguments."""

    return {
        "expiration": args.expiration,
        "strike_gt": args.strike_gt,
        "strike_gte": args.strike_gte,
        "strike_lt": args.strike_lt,
        "strike_lte": args.strike_lte,
        "strike_eq": args.strike_eq,
    }


def fundamentals_query(args: argparse.Namespace) -> dict[str, Any]:
    """Build a symbol fundamentals query using documented defaults."""

    return aggregate_fundamentals_query(args, args.endpoint)


def aggregate_fundamentals_query(args: argparse.Namespace, endpoint: str) -> dict[str, Any]:
    """Build fundamentals query values for aggregate and single commands."""

    if endpoint in PERIOD_FUNDAMENTALS:
        return {"timeframe": args.timeframe, "limit": args.limit}
    if endpoint in LIMITED_FUNDAMENTALS:
        return {"limit": args.limit}
    return {}


def economy_query(args: argparse.Namespace) -> dict[str, Any]:
    """Build the aggregate economy query."""

    return {"limit": args.economy_limit}


def expiration_list_for_symbol(
    args: argparse.Namespace,
    expirations_by_symbol: Mapping[str, Any],
    symbol: str,
) -> list[str]:
    """Extract expiration strings from either shared args or endpoint results."""

    shared = csv_values(args.expirations)
    if shared:
        return shared
    value = expirations_by_symbol.get(symbol, {})
    if isinstance(value, dict) and isinstance(value.get("expirations"), list):
        return value["expirations"]
    return []


def clean_query_values(query: Mapping[str, Any] | None) -> dict[str, str]:
    """Drop empty query values and stringify values for URL encoding."""

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


def build_url(base_url: str, path: str, query: Mapping[str, str]) -> str:
    """Join the normalized base URL, v1 path, and query string."""

    url = f"{base_url}{path}"
    if query:
        return f"{url}?{urlencode(query)}"
    return url


def unwrap_payload(payload: Any) -> Any:
    """Return envelope results while accepting direct JSON payloads."""

    if not isinstance(payload, dict):
        return payload
    if payload.get("status") == "ok":
        return payload.get("results")
    if payload.get("status") == "error":
        raise RuntimeError(str(payload.get("error", "MHQ API returned an error.")))
    if "error" in payload:
        raise RuntimeError(str(payload["error"]))
    return payload


def http_error_message(error: HTTPError) -> str:
    """Build a readable HTTP error with public API error payloads when available."""

    body = error.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"HTTP {error.code} {error.reason}: {body}"
    if isinstance(payload, dict) and "error" in payload:
        return f"HTTP {error.code} {error.reason}: {payload['error']}"
    return f"HTTP {error.code} {error.reason}: {payload}"


def build_document(command: str, base_url: str, data: Any, calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap dumped data with enough metadata for static importers."""

    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "baseUrl": base_url,
        "command": command,
        "requests": calls,
        "data": data,
    }


def write_json(document: Mapping[str, Any], output: Path, *, pretty: bool) -> Path:
    """Write the final JSON document and return the resolved path."""

    output.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    else:
        text = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    output.write_text(f"{text}\n", encoding="utf-8")
    return output.resolve()


def resolve_output(output: str | None, command: str) -> Path:
    """Resolve an explicit output path or choose a CWD default."""

    if output:
        return Path(output)
    suffix = "mhq-v1.json" if command == "all" else f"mhq-v1-{command}.json"
    return Path.cwd() / suffix


def resolve_key(key: str | None, key_file: str) -> str:
    """Resolve an API key from args, env, or `.mhqkey`."""

    if key:
        return key.strip()
    for name in ENV_KEY_NAMES:
        value = os.getenv(name)
        if value:
            return value.strip()
    path = Path(key_file)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    raise RuntimeError("Provide --key, set MHQ_KEY or MHQ_API_KEY, or create .mhqkey in the current directory.")


def resolve_base_url(base_url: str | None) -> str:
    """Resolve a base URL and ensure it points at `/api/v1`."""

    raw_url = (base_url or os.getenv("MHQ_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    if raw_url.endswith("/api/v1"):
        return raw_url
    return f"{raw_url}/api/v1"


def csv_values(values: Iterable[str] | None) -> list[str]:
    """Split repeated comma-separated arguments into a compact list."""

    if values is None:
        return []
    items: list[str] = []
    for value in values:
        items.extend(item.strip() for item in value.split(",") if item.strip())
    return items


def path_symbol(symbol: str) -> str:
    """Normalize and encode a stock or index symbol."""

    return quote(symbol.upper(), safe="")


def path_part(value: str) -> str:
    """Encode an arbitrary API path component."""

    return quote(value, safe="")


if __name__ == "__main__":
    sys.exit(main())
