#!/usr/bin/env sh
set -eu

# Resolve repository paths from this script location so it can run from any CWD.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
SCRIPT_PATH="$REPO_ROOT/skills/mhq-reports/scripts/mhq_data.py"
OUTPUT_DIR="$SCRIPT_DIR/scriptjson"

# Keep the live command fixture small and overrideable from the environment.
PYTHON_BIN="${MHQ_TEST_PYTHON:-python}"
SYMBOL="${MHQ_TEST_SYMBOL:-SPY}"
FUNDAMENTAL_SYMBOL="${MHQ_TEST_FUNDAMENTAL_SYMBOL:-AAPL}"
EXPIRATION="${MHQ_TEST_EXPIRATION:-2026-05-08}"
OPTION_TICKER="${MHQ_TEST_OPTION_TICKER:-O:SPY260508C00400000}"
FROM_DATE="${MHQ_TEST_FROM_DATE:-2026-05-01}"
TO_DATE="${MHQ_TEST_TO_DATE:-2026-05-03}"

mkdir -p "$OUTPUT_DIR"

# Exercise every standalone command and keep one JSON output per command.
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/symbols.json" symbols
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/fundamentals-tickers.json" fundamentals-tickers
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/expirations.json" expirations --symbol "$SYMBOL"
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/spot.json" spot --symbol "$SYMBOL"
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/option.json" option --ticker "$OPTION_TICKER"
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/gex.json" gex --symbol "$SYMBOL" --expiration "$EXPIRATION"
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/gex-matrix.json" gex-matrix --symbol "$SYMBOL" --expirations "$EXPIRATION"
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/gex-history.json" gex-history --symbol "$SYMBOL" --date "$FROM_DATE"
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/stock-bars.json" stock-bars --symbol "$SYMBOL" --from-date "$FROM_DATE" --to-date "$TO_DATE" --multiplier 1 --timespan day
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/option-bars.json" option-bars --ticker "$OPTION_TICKER" --from-date "$FROM_DATE" --to-date "$TO_DATE" --multiplier 1 --timespan minute

# Cover every public fundamentals and economy endpoint variant.
for endpoint in ratios income balance-sheet cash-flow dividends splits short-interest float news; do
    "$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/fundamentals-$endpoint.json" fundamentals --endpoint "$endpoint" --symbol "$FUNDAMENTAL_SYMBOL" --limit 2
done

for endpoint in treasury-yields inflation labor; do
    "$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/economy-$endpoint.json" economy --endpoint "$endpoint" --limit 2
done

# Keep the aggregate full-surface dump at the requested canonical file path.
"$PYTHON_BIN" "$SCRIPT_PATH" --pretty -o "$OUTPUT_DIR/files.json" all --symbols "$SYMBOL" --fundamental-symbols "$FUNDAMENTAL_SYMBOL" --option-tickers "$OPTION_TICKER" --expirations "$EXPIRATION" --from-date "$FROM_DATE" --to-date "$TO_DATE" --stock-timespan day --stock-multiplier 1 --option-timespan minute --option-multiplier 1 --limit 2 --economy-limit 2
