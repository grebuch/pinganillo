@echo off
rem Audio + Whisper self-test. Run it while a video with speech is playing.
cd /d "%~dp0"
call run-windows.bat --diagnose
pause
