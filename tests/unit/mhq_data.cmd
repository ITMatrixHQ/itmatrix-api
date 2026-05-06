@echo off
setlocal enabledelayedexpansion

rem Resolve repository paths from this script location so it can run from any CWD.
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "SCRIPT_PATH=%REPO_ROOT%\skills\mhq-reports\scripts\mhq_data.py"
set "OUTPUT_DIR=%SCRIPT_DIR%scriptjson"

rem Keep the live command fixture small and overrideable from the environment.
if not defined MHQ_TEST_PYTHON set "MHQ_TEST_PYTHON=python"
if not defined MHQ_TEST_SYMBOL set "MHQ_TEST_SYMBOL=SPY"
if not defined MHQ_TEST_FUNDAMENTAL_SYMBOL set "MHQ_TEST_FUNDAMENTAL_SYMBOL=AAPL"
if not defined MHQ_TEST_EXPIRATION set "MHQ_TEST_EXPIRATION=2026-05-08"
if not defined MHQ_TEST_OPTION_TICKER set "MHQ_TEST_OPTION_TICKER=O:SPY260508C00400000"
if not defined MHQ_TEST_FROM_DATE set "MHQ_TEST_FROM_DATE=2026-05-01"
if not defined MHQ_TEST_TO_DATE set "MHQ_TEST_TO_DATE=2026-05-03"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

rem Exercise every standalone command and keep one JSON output per command.
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\symbols.json" symbols
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\fundamentals-tickers.json" fundamentals-tickers
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\expirations.json" expirations --symbol "%MHQ_TEST_SYMBOL%"
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\spot.json" spot --symbol "%MHQ_TEST_SYMBOL%"
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\option.json" option --ticker "%MHQ_TEST_OPTION_TICKER%"
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\gex.json" gex --symbol "%MHQ_TEST_SYMBOL%" --expiration "%MHQ_TEST_EXPIRATION%"
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\gex-matrix.json" gex-matrix --symbol "%MHQ_TEST_SYMBOL%" --expirations "%MHQ_TEST_EXPIRATION%"
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\gex-history.json" gex-history --symbol "%MHQ_TEST_SYMBOL%" --date "%MHQ_TEST_FROM_DATE%"
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\stock-bars.json" stock-bars --symbol "%MHQ_TEST_SYMBOL%" --from-date "%MHQ_TEST_FROM_DATE%" --to-date "%MHQ_TEST_TO_DATE%" --multiplier 1 --timespan day
if errorlevel 1 exit /b %errorlevel%
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\option-bars.json" option-bars --ticker "%MHQ_TEST_OPTION_TICKER%" --from-date "%MHQ_TEST_FROM_DATE%" --to-date "%MHQ_TEST_TO_DATE%" --multiplier 1 --timespan minute
if errorlevel 1 exit /b %errorlevel%

rem Cover every public fundamentals and economy endpoint variant.
for %%E in (ratios income balance-sheet cash-flow dividends splits short-interest float news) do (
    "%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\fundamentals-%%E.json" fundamentals --endpoint "%%E" --symbol "%MHQ_TEST_FUNDAMENTAL_SYMBOL%" --limit 2
    if errorlevel 1 exit /b !errorlevel!
)

for %%E in (treasury-yields inflation labor) do (
    "%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\economy-%%E.json" economy --endpoint "%%E" --limit 2
    if errorlevel 1 exit /b !errorlevel!
)

rem Keep the aggregate full-surface dump at the requested canonical file path.
"%MHQ_TEST_PYTHON%" "%SCRIPT_PATH%" --pretty -o "%OUTPUT_DIR%\files.json" all --symbols "%MHQ_TEST_SYMBOL%" --fundamental-symbols "%MHQ_TEST_FUNDAMENTAL_SYMBOL%" --option-tickers "%MHQ_TEST_OPTION_TICKER%" --expirations "%MHQ_TEST_EXPIRATION%" --from-date "%MHQ_TEST_FROM_DATE%" --to-date "%MHQ_TEST_TO_DATE%" --stock-timespan day --stock-multiplier 1 --option-timespan minute --option-multiplier 1 --limit 2 --economy-limit 2
if errorlevel 1 exit /b %errorlevel%
exit /b 0
