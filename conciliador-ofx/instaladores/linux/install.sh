#!/usr/bin/env bash
# Instalador do Conciliador OFX -> Omie (Linux).
#
# Automatiza todo o ambiente:
#   1. localiza o Python 3 (>= 3.9); se NAO existir, INSTALA automaticamente
#      pelo gerenciador de pacotes da distro (apt/dnf/yum/pacman/zypper);
#   2. cria o ambiente virtual .venv;
#   3. atualiza o pip e instala requirements.txt;
#   4. prepara os .env (raiz + clientes) a partir dos .example, sem sobrescrever;
#   5. roda os testes como verificacao.
#
# Fica pendente apenas o preenchimento manual das credenciais nos .env.
#
# Uso:
#   ./instaladores/linux/install.sh
# (a partir de qualquer diretorio; o script resolve os caminhos.)

set -euo pipefail

AQUI="$(cd -- "$(dirname -- "$0")" && pwd)"
# instaladores/linux -> instaladores -> conciliador-ofx
RAIZ="$(cd -- "$AQUI/../.." && pwd)"
COMUM="$AQUI/../comum"
VENV="$RAIZ/.venv"
PY_MIN_MINOR=9

cd "$RAIZ"
echo "==> Conciliador OFX -> Omie | instalacao (Linux)"
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

instalar_python() {
  echo "==> Python 3.$PY_MIN_MINOR+ nao encontrado. Tentando instalar..."
  local sudo=""
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then sudo="sudo"; else
      echo "ERRO: sem privilegios de root e sem 'sudo' para instalar o Python." >&2
      exit 1
    fi
  fi
  if command -v apt-get >/dev/null 2>&1; then
    echo "    Gerenciador: apt"
    $sudo apt-get update
    $sudo apt-get install -y python3 python3-venv python3-pip
  elif command -v dnf >/dev/null 2>&1; then
    echo "    Gerenciador: dnf"
    $sudo dnf install -y python3 python3-pip
  elif command -v yum >/dev/null 2>&1; then
    echo "    Gerenciador: yum"
    $sudo yum install -y python3 python3-pip
  elif command -v pacman >/dev/null 2>&1; then
    echo "    Gerenciador: pacman"
    $sudo pacman -Sy --noconfirm python python-pip
  elif command -v zypper >/dev/null 2>&1; then
    echo "    Gerenciador: zypper"
    $sudo zypper install -y python3 python3-pip
  else
    echo "ERRO: nenhum gerenciador de pacotes conhecido (apt/dnf/yum/pacman/zypper)." >&2
    echo "  Instale o Python 3.$PY_MIN_MINOR+ manualmente: https://www.python.org/downloads/" >&2
    exit 1
  fi
}

if ! PYTHON_BIN="$(encontrar_python)"; then
  instalar_python
  if ! PYTHON_BIN="$(encontrar_python)"; then
    echo "ERRO: Python ainda nao encontrado apos a instalacao." >&2
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
echo "    Interface:  ./executar_conciliador.sh"
echo "    Terminal :  .venv/bin/python main.py --cliente <id> --ofx <arquivo.ofx>"
