$ErrorActionPreference = "Stop"

# Resolve repository paths from this script location so it can run from any CWD.
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$ScriptPath = Join-Path $RepoRoot "skills\mhq-reports\scripts\mhq_data.py"
$OutputDir = Join-Path $PSScriptRoot "scriptjson"

# Keep the live command fixture small and overrideable from the environment.
$Python = if ($env:MHQ_TEST_PYTHON) { $env:MHQ_TEST_PYTHON } else { "python" }
$Symbol = if ($env:MHQ_TEST_SYMBOL) { $env:MHQ_TEST_SYMBOL } else { "SPY" }
$FundamentalSymbol = if ($env:MHQ_TEST_FUNDAMENTAL_SYMBOL) { $env:MHQ_TEST_FUNDAMENTAL_SYMBOL } else { "AAPL" }
$Expiration = if ($env:MHQ_TEST_EXPIRATION) { $env:MHQ_TEST_EXPIRATION } else { "2026-05-08" }
$OptionTicker = if ($env:MHQ_TEST_OPTION_TICKER) { $env:MHQ_TEST_OPTION_TICKER } else { "O:SPY260508C00400000" }
$FromDate = if ($env:MHQ_TEST_FROM_DATE) { $env:MHQ_TEST_FROM_DATE } else { "2026-05-01" }
$ToDate = if ($env:MHQ_TEST_TO_DATE) { $env:MHQ_TEST_TO_DATE } else { "2026-05-03" }

New-Item -ItemType Directory -Force $OutputDir | Out-Null

# Exercise every standalone command and keep one JSON output per command.
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "symbols.json") symbols
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "fundamentals-tickers.json") fundamentals-tickers
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "expirations.json") expirations --symbol $Symbol
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "spot.json") spot --symbol $Symbol
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "option.json") option --ticker $OptionTicker
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "gex.json") gex --symbol $Symbol --expiration $Expiration
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "gex-matrix.json") gex-matrix --symbol $Symbol --expirations $Expiration
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "gex-history.json") gex-history --symbol $Symbol --date $FromDate
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "stock-bars.json") stock-bars --symbol $Symbol --from-date $FromDate --to-date $ToDate --multiplier 1 --timespan day
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "option-bars.json") option-bars --ticker $OptionTicker --from-date $FromDate --to-date $ToDate --multiplier 1 --timespan minute

# Cover every public fundamentals and economy endpoint variant.
foreach ($Endpoint in "ratios", "income", "balance-sheet", "cash-flow", "dividends", "splits", "short-interest", "float", "news") {
    & $Python $ScriptPath --pretty -o (Join-Path $OutputDir "fundamentals-$Endpoint.json") fundamentals --endpoint $Endpoint --symbol $FundamentalSymbol --limit 2
}

foreach ($Endpoint in "treasury-yields", "inflation", "labor") {
    & $Python $ScriptPath --pretty -o (Join-Path $OutputDir "economy-$Endpoint.json") economy --endpoint $Endpoint --limit 2
}

# Keep the aggregate full-surface dump at the requested canonical file path.
& $Python $ScriptPath --pretty -o (Join-Path $OutputDir "files.json") all --symbols $Symbol --fundamental-symbols $FundamentalSymbol --option-tickers $OptionTicker --expirations $Expiration --from-date $FromDate --to-date $ToDate --stock-timespan day --stock-multiplier 1 --option-timespan minute --option-multiplier 1 --limit 2 --economy-limit 2
