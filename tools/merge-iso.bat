@echo off
rem Double-click me: joins the Migood OS ISO parts in this folder (see merge-iso.ps1).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0merge-iso.ps1" "%~dp0."
pause
