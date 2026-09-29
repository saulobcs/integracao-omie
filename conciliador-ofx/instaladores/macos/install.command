#!/usr/bin/env bash
# Instalador do Conciliador OFX -> Omie (macOS).
# Clicavel no Finder (extensao .command) ou executavel no Terminal.
#
# Automatiza todo o ambiente:
#   1. localiza o Python 3 (>= 3.9); se NAO existir, INSTALA via Homebrew
#      (instalando o proprio Homebrew antes, caso falte);
#   2. cria o ambiente virtual .venv;
#   3. atualiza o pip e instala requirements.txt;
#   4. prepara os .env (raiz + clientes) a partir dos .example, sem sobrescrever;
#   5. roda os testes como verificacao.
#
# Fica pendente apenas o preenchimento manual das credenciais nos .env.

set -euo pipefail

AQUI="$(cd -- "$(dirname -- "$0")" && pwd)"
# instaladores/macos -> instaladores -> conciliador-ofx
RAIZ="$(cd -- "$AQUI/../.." && pwd)"
COMUM="$AQUI/../comum"
VENV="$RAIZ/.venv"
PY_MIN_MINOR=9

cd "$RAIZ"
echo "==> Conciliador OFX -> Omie | instalacao (macOS)"
echo "    Pasta do projeto: $RAIZ"

encontrar_python() {
  for candidato in python3 python; do
    if command -v "$candidato" >/dev/null 2>&1; then
      if "$candidato" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, '"$PY_MIN_MINOR"') else 1)' 2>/dev/null; then
        echo "$candidato"
        return 0
      fi
    fi
  done
  return 1
}

instalar_homebrew() {
  if command -v brew >/dev/null 2>&1; then return 0; fi
  echo "==> Homebrew nao encontrado. Instalando (pode pedir sua senha)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Ajusta o PATH para a sessao atual (Apple Silicon usa /opt/homebrew).
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
  if [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
}

instalar_python() {
  echo "==> Python 3.$PY_MIN_MINOR+ nao encontrado. Instalando via Homebrew..."
  instalar_homebrew
  brew install python
}

if ! PYTHON_BIN="$(encontrar_python)"; then
  instalar_python
  if ! PYTHON_BIN="$(encontrar_python)"; then
    echo "ERRO: Python ainda nao encontrado apos a instalacao." >&2
    echo "  Instale manualmente: https://www.python.org/downloads/macos/" >&2
    exit 1
  fi
fi
echo "==> Python: $($PYTHON_BIN --version) ($PYTHON_BIN)"

if [ ! -x "$VENV/bin/python" ]; then
  echo "==> Criando ambiente virtual em .venv ..."
  "$PYTHON_BIN" -m venv "$VENV"
else
  echo "==> Ambiente virtual .venv ja existe (reutilizando)."
fi
VENV_PY="$VENV/bin/python"

echo "==> Atualizando pip ..."
"$VENV_PY" -m pip install --upgrade pip >/dev/null

if [ -f "$RAIZ/requirements.txt" ]; then
  echo "==> Instalando dependencias (requirements.txt) ..."
  "$VENV_PY" -m pip install -r "$RAIZ/requirements.txt"
fi

echo "==> Preparando arquivos .env (a partir dos .example) ..."
"$VENV_PY" "$COMUM/install_env.py" "$RAIZ"

echo "==> Rodando testes de verificacao ..."
if "$VENV_PY" -m unittest discover -s "$RAIZ/tests" >/dev/null 2>&1; then
  echo "    Testes: OK"
else
  echo "    AVISO: testes nao passaram. Detalhe: $VENV_PY -m unittest discover -s tests -v" >&2
fi

echo ""
echo "==> Instalacao concluida."
echo "    PENDENTE (manual): preencha OMIE_APP_KEY / OMIE_APP_SECRET nos .env."
echo "    Interface:  ./executar_conciliador.command"
echo "    Terminal :  .venv/bin/python main.py --cliente <id> --ofx <arquivo.ofx>"
