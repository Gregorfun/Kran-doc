@echo off
setlocal
REM PDFDoc Komfort-Start

REM In den Ordner wechseln, in dem diese .bat liegt (portabel, kein harter OneDrive-Pfad)
cd /d "%~dp0"

echo Starte PDFDoc CLI...
echo.

set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"

"%PY%" scripts\pdfdoc_cli.py

echo.
echo Vorgang beendet. Taste druecken zum Schliessen...
pause

endlocal
