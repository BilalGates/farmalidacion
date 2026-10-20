@echo off
setlocal
set /p FARMALIDACION_URL=Pegue la direccion completa de Farmalidacion y pulse Intro: 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-nomenclator-connector.ps1" -FarmalidacionUrl "%FARMALIDACION_URL%"
pause
