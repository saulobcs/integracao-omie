#!/usr/bin/env sh
# Lançador para Linux e macOS. Execute pelo terminal ou dê permissão de execução.
set -eu

DIRETORIO=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$DIRETORIO/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  printf '%s\n' "Ambiente virtual não encontrado."
  printf '%s\n' "Crie-o uma vez com: cd \"$DIRETORIO\" && python3 -m venv .venv"
  exit 1
fi

exec "$PYTHON" "$DIRETORIO/conciliador_web.py"
