@echo off
setlocal
set "DIRETORIO=%~dp0"
set "PYTHON=%DIRETORIO%.venv\Scripts\pythonw.exe"

if not exist "%PYTHON%" (
  echo Ambiente virtual nao encontrado.
  echo Execute uma vez no PowerShell, dentro desta pasta:
  echo py -3 -m venv .venv
  pause
  exit /b 1
)

start "Conciliador OFX" /b "%PYTHON%" "%DIRETORIO%conciliador_web.py"
