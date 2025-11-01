@echo off
title BestBuy Watcher Manager
color 3F
setlocal enabledelayedexpansion

:: ============================================================
::  SKU-Scout (BestBuy Stock Watcher)
::  Manager Script for Windows
::  Updated for: bestbuy_restock_watcher_telegram_60s.py
:: ============================================================

set "SCRIPT_DIR=C:\bestbuy-watcher"
set "MAIN_SCRIPT=%SCRIPT_DIR%\bestbuy_restock_watcher_telegram_60s.py"
set "LOG_PATH=%SCRIPT_DIR%\restock.log"
set "STATE_PATH=%SCRIPT_DIR%\availability_state.json"
set "PID_FILE=%SCRIPT_DIR%\watcher.pid"
set "VENV_PY=%SCRIPT_DIR%\venv\Scripts\python.exe"
set "TITLE=BestBuy Watcher Manager"

if not exist "%VENV_PY%" (
    echo [⚙️] Python venv not found — creating one now...
    cd /d "%SCRIPT_DIR%"
    python -m venv venv
    "%VENV_PY%" -m pip install -U pip
    "%VENV_PY%" -m pip install -r requirements.txt
)

:menu
cls
echo ===========================================================
echo                 BestBuy Watcher Manager
echo ===========================================================
echo   1. Start watcher (background)
echo   2. Stop watcher
echo   3. Status (show PID/log)
echo   4. View live log (Ctrl+C to stop)
echo   5. Run once (debug)
echo   6. Edit .env
echo   7. Reset saved state
echo   8. Diagnostics
echo   9. Exit
echo -----------------------------------------------------------
echo   State file: "%STATE_PATH%"
echo   Log file:   "%LOG_PATH%"
echo -----------------------------------------------------------
set /p choice="Select an option [1-9] then press ENTER: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto status
if "%choice%"=="4" goto log
if "%choice%"=="5" goto runonce
if "%choice%"=="6" goto edit
if "%choice%"=="7" goto reset
if "%choice%"=="8" goto diag
if "%choice%"=="9" exit /b
goto menu

:start
cls
echo === START WATCHER ===
echo Launching...
powershell -command "Start-Process '%VENV_PY%' -ArgumentList '%MAIN_SCRIPT%' -WindowStyle Hidden"
timeout /t 2 >nul
echo [✅] Watcher started in background.
pause
goto menu

:stop
cls
echo === STOP WATCHER ===
for /f "tokens=*" %%i in ('tasklist /fi "imagename eq python.exe" /fo csv ^| findstr /i "%MAIN_SCRIPT%"') do (
    for /f "tokens=2 delims=," %%a in ("%%i") do taskkill /PID %%~a /F >nul 2>&1
)
del "%PID_FILE%" >nul 2>&1
echo [🛑] Watcher stopped (if running).
pause
goto menu

:status
cls
echo === WATCHER STATUS ===
if exist "%PID_FILE%" (
    echo PID file found at "%PID_FILE%"
    type "%PID_FILE%"
) else (
    echo No PID file found. Watcher may not be running.
)
if exist "%LOG_PATH%" (
    echo --- Recent Log Entries ---
    powershell -command "Get-Content '%LOG_PATH%' -Tail 10"
) else (
    echo Log file not found.
)
pause
goto menu

:log
cls
echo === LIVE LOG VIEW ===
if not exist "%LOG_PATH%" echo Log file not found. & pause & goto menu
powershell -command "Get-Content '%LOG_PATH%' -Wait"
goto menu

:runonce
cls
echo === RUN ONCE - DEBUG (Press Ctrl+C to stop) ===
"%VENV_PY%" "%MAIN_SCRIPT%"
pause
goto menu

:edit
cls
echo === EDIT .ENV FILE ===
if exist "%SCRIPT_DIR%\.env" (
    notepad "%SCRIPT_DIR%\.env"
) else (
    echo .env file not found!
)
pause
goto menu

:reset
cls
echo === RESET STATE ===
del "%STATE_PATH%" >nul 2>&1
del "%LOG_PATH%" >nul 2>&1
echo [♻️] Saved state and log cleared.
pause
goto menu

:diag
cls
echo === DIAGNOSTICS ===
where python
where pip
if exist "%VENV_PY%" (
    echo VENV Python found at "%VENV_PY%"
) else (
    echo VENV Python not found!
)
if exist "%MAIN_SCRIPT%" (
    echo Script found: "%MAIN_SCRIPT%"
) else (
    echo ❌ Script not found! Check file path.
)
echo.
if exist "%LOG_PATH%" (
    for %%I in ("%LOG_PATH%") do echo Log size: %%~zI bytes
) else (
    echo No log file yet.
)
pause
goto menu
