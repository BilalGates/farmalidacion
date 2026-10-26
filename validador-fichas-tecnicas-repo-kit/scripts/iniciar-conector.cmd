@echo off
setlocal
set "CONFIG=%LOCALAPPDATA%\Farmalidacion\NomenclatorConnector\origen.txt"
set "FARMALIDACION_URL="
if exist "%CONFIG%" set /p FARMALIDACION_URL=<"%CONFIG%"
if defined FARMALIDACION_URL (
    echo Origen autorizado: %FARMALIDACION_URL%
    echo Para cambiarlo, borre "%CONFIG%" y vuelva a abrir este archivo.
) else (
    set /p FARMALIDACION_URL=Pegue la direccion completa de Farmalidacion y pulse Intro: 
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-nomenclator-connector.ps1" -FarmalidacionUrl "%FARMALIDACION_URL%"
pause
