@echo off
rem Pinganillo launcher for people running from source on Windows.
rem Finds Python 3.11-3.13 (py launcher, pyenv-win or PATH), creates a private
rem virtual environment once and reinstalls dependencies only when
rem pyproject.toml changes. Errors are kept in pinganillo-launch.log.
setlocal EnableExtensions
cd /d "%~dp0"
set "LOG=%~dp0pinganillo-launch.log"
set "PIPLOG=%~dp0pinganillo-install.log"
echo [%date% %time%] %~f0 %* > "%LOG%"

if exist ".venv\Scripts\python.exe" goto install

set "PY="
set "VERSIONS_OK=import sys; sys.exit(sys.version_info[:2] not in [(3, 11), (3, 12), (3, 13)])"

rem 1. Python launcher (python.org installers)
where py >nul 2>&1
if not errorlevel 1 (
  for %%V in (3.12 3.13 3.11) do (
    if not defined PY py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)

rem 2. pyenv-win versions (not registered with the launcher)
if not defined PY (
  for /d %%D in ("%USERPROFILE%\.pyenv\pyenv-win\versions\3.12*" "%USERPROFILE%\.pyenv\pyenv-win\versions\3.13*" "%USERPROFILE%\.pyenv\pyenv-win\versions\3.11*") do (
    if not defined PY if exist "%%~D\python.exe" set PY="%%~D\python.exe"
  )
)

rem 3. Whatever "python" is on PATH (pyenv shims are .bat files, hence "call")
if not defined PY (
  call python -c "%VERSIONS_OK%" >nul 2>&1 && set "PY=call python"
)

if not defined PY goto nopython
echo Python: %PY%>> "%LOG%"
echo Creating the private environment with %PY% ...
%PY% -m venv .venv >> "%LOG%" 2>&1
if errorlevel 1 goto error

:install
fc /b pyproject.toml .venv\.install-stamp >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies. The first time downloads a few hundred MB and takes a few minutes ...
  .venv\Scripts\python.exe -m pip install --upgrade pip --log "%PIPLOG%" >nul
  .venv\Scripts\python.exe -m pip install -e . --log "%PIPLOG%"
  if errorlevel 1 (
    echo pip install failed, see pinganillo-install.log>> "%LOG%"
    goto error
  )
  copy /y pyproject.toml .venv\.install-stamp >nul
)

echo Starting Pinganillo ...
.venv\Scripts\python.exe -m pinganillo %* 2>> "%LOG%"
if errorlevel 1 goto error
exit /b 0

:nopython
echo.
echo [EN] Pinganillo needs 64-bit Python 3.12 (3.11 and 3.13 also work).
echo      Install it from https://www.python.org/downloads/ and run this file again.
echo [ES] Pinganillo necesita Python 3.12 de 64 bits (3.11 y 3.13 tambien sirven).
echo      Instalalo desde https://www.python.org/downloads/ y vuelve a ejecutar este archivo.
echo no suitable Python found>> "%LOG%"
pause
exit /b 1

:error
echo.
echo [EN] Pinganillo could not start. Details:
echo [ES] No se pudo iniciar Pinganillo. Detalles:
echo ------------------------------------------------------------
type "%LOG%"
echo ------------------------------------------------------------
pause
exit /b 1
