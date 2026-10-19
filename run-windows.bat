@echo off
rem Escuchator launcher for people running from source on Windows.
rem Creates a private virtual environment once and reinstalls dependencies
rem only when pyproject.toml changes, so normal starts are fast and offline.
setlocal
cd /d "%~dp0"

set "PY="
for %%V in (3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  echo [EN] Escuchator needs 64-bit Python 3.12 or 3.11: https://www.python.org/downloads/
  echo [ES] Escuchator necesita Python 3.12 o 3.11 de 64 bits: https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Creating the virtual environment with %PY% ...
  %PY% -m venv .venv || goto error
)

fc /b pyproject.toml .venv\.install-stamp >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies, this only happens after an update ...
  .venv\Scripts\python.exe -m pip install --upgrade pip >nul
  .venv\Scripts\python.exe -m pip install -e . || goto error
  copy /y pyproject.toml .venv\.install-stamp >nul
)

.venv\Scripts\python.exe -m escuchator %*
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo [EN] Escuchator could not start. Check your Internet connection for the first install.
echo [ES] No se pudo iniciar Escuchator. La primera instalacion necesita Internet.
pause
exit /b 1
