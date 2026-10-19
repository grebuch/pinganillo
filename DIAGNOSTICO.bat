@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Ejecuta primero INICIAR.bat para instalar los componentes.
  pause
  exit /b 1
)
.venv\Scripts\python.exe diagnostico.py
pause
