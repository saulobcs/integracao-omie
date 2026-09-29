@echo off
REM Instalador do Conciliador OFX -> Omie (Windows).
REM
REM Automatiza todo o ambiente:
REM   1. localiza o Python 3; se NAO existir, INSTALA via winget;
REM   2. cria o ambiente virtual .venv;
REM   3. atualiza o pip e instala requirements.txt;
REM   4. prepara os .env (raiz + clientes) a partir dos .example, sem sobrescrever;
REM   5. roda os testes como verificacao.
REM
REM Fica pendente apenas o preenchimento manual das credenciais nos .env.
REM
REM Uso: clique duas vezes em install.bat ou rode no Prompt/PowerShell.

setlocal enableextensions
REM instaladores\windows -> instaladores -> conciliador-ofx
set "AQUI=%~dp0"
pushd "%AQUI%..\.." >nul
set "RAIZ=%CD%"
popd >nul
set "COMUM=%AQUI%..\comum"
set "VENV=%RAIZ%\.venv"

cd /d "%RAIZ%"
echo ==^> Conciliador OFX -^> Omie ^| instalacao (Windows)
echo     Pasta do projeto: %RAIZ%

REM 1. Localizar o Python.
set "PYTHON_LAUNCHER="
py -3 --version >nul 2>&1
if %errorlevel%==0 (
  set "PYTHON_LAUNCHER=py -3"
) else (
  python --version >nul 2>&1
  if %errorlevel%==0 set "PYTHON_LAUNCHER=python"
)

REM 1b. Se nao existir, tentar instalar via winget.
if not defined PYTHON_LAUNCHER (
  echo ==^> Python nao encontrado. Tentando instalar via winget...
  winget --version >nul 2>&1
  if errorlevel 1 (
    echo ERRO: winget nao disponivel. Instale o Python manualmente:
    echo   https://www.python.org/downloads/  ^(marque "Add Python to PATH"^)
    pause
    exit /b 1
  )
  winget install --id Python.Python.3 -e --source winget --accept-package-agreements --accept-source-agreements
  echo ==^> Reabra o terminal apos a instalacao e rode este install.bat novamente.
  echo     ^(O PATH do Python so fica disponivel em uma nova sessao.^)
  pause
  REM Tenta continuar na mesma sessao, caso o PATH ja tenha atualizado.
  py -3 --version >nul 2>&1
  if %errorlevel%==0 (
    set "PYTHON_LAUNCHER=py -3"
  ) else (
    python --version >nul 2>&1
    if %errorlevel%==0 set "PYTHON_LAUNCHER=python"
  )
)

if not defined PYTHON_LAUNCHER (
  echo ERRO: Python ainda nao disponivel nesta sessao. Reabra o terminal e rode novamente.
  pause
  exit /b 1
)
echo ==^> Python: %PYTHON_LAUNCHER%

REM 2. Criar o ambiente virtual (idempotente).
if not exist "%VENV%\Scripts\python.exe" (
  echo ==^> Criando ambiente virtual em .venv ...
  %PYTHON_LAUNCHER% -m venv "%VENV%"
  if errorlevel 1 (
    echo ERRO ao criar o ambiente virtual.
    pause
    exit /b 1
  )
) else (
  echo ==^> Ambiente virtual .venv ja existe (reutilizando^).
)
set "VENV_PY=%VENV%\Scripts\python.exe"

REM 3. Atualizar pip e instalar dependencias.
echo ==^> Atualizando pip ...
"%VENV_PY%" -m pip install --upgrade pip >nul
if exist "%RAIZ%\requirements.txt" (
  echo ==^> Instalando dependencias (requirements.txt^) ...
  "%VENV_PY%" -m pip install -r "%RAIZ%\requirements.txt"
)

REM 4. Preparar os .env.
echo ==^> Preparando arquivos .env (a partir dos .example^) ...
"%VENV_PY%" "%COMUM%\install_env.py" "%RAIZ%"

REM 5. Verificacao rapida.
echo ==^> Rodando testes de verificacao ...
"%VENV_PY%" -m unittest discover -s "%RAIZ%\tests" >nul 2>&1
if errorlevel 1 (
  echo     AVISO: testes nao passaram. Detalhe:
  echo       "%VENV_PY%" -m unittest discover -s tests -v
) else (
  echo     Testes: OK
)

echo.
echo ==^> Instalacao concluida.
echo     PENDENTE (manual^): preencha OMIE_APP_KEY / OMIE_APP_SECRET nos .env.
echo     Interface:  executar_conciliador.bat
echo     Terminal :  .venv\Scripts\python main.py --cliente ^<id^> --ofx ^<arquivo.ofx^>
pause
