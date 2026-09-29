#!/usr/bin/env bash
#
# release.sh - automatiza o bump de versão e a publicação de um release.
#
# O que faz:
#   1. Calcula a nova versão a partir da atual (major/minor/patch) ou usa a que
#      você informar explicitamente.
#   2. Atualiza __version__ em conciliador-ofx/conciliador/__init__.py.
#   3. Renomeia a seção [Não lançado] do CHANGELOG.md para a nova versão + data,
#      e recria um bloco [Não lançado] vazio.
#   4. Commita, cria a tag anotada vX.Y.Z e faz push (opcional).
#
# O GitHub Actions (.github/workflows/release.yml) detecta a tag e cria o
# GitHub Release com notas automáticas.
#
# Uso:
#   scripts/release.sh patch          # 0.1.0 -> 0.1.1
#   scripts/release.sh minor          # 0.1.1 -> 0.2.0
#   scripts/release.sh major          # 0.2.0 -> 1.0.0
#   scripts/release.sh 1.4.2          # define a versão explicitamente
#   scripts/release.sh minor --dry-run  # mostra o que faria, sem alterar nada
#   scripts/release.sh patch --no-push  # commita e cria a tag, mas não faz push
#
set -euo pipefail

# --- Localiza a raiz do repositório ---
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION_FILE="conciliador-ofx/conciliador/__init__.py"
CHANGELOG="CHANGELOG.md"

DRY_RUN=false
DO_PUSH=true
BUMP=""

# --- Parse dos argumentos ---
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-push) DO_PUSH=false ;;
    major|minor|patch) BUMP="$arg" ;;
    [0-9]*.[0-9]*.[0-9]*) BUMP="$arg" ;;
    *) echo "Argumento desconhecido: $arg" >&2; exit 1 ;;
  esac
done

if [ -z "$BUMP" ]; then
  echo "Uso: scripts/release.sh {major|minor|patch|X.Y.Z} [--dry-run] [--no-push]" >&2
  exit 1
fi

# --- Verificações de segurança ---
if [ -n "$(git status --porcelain)" ]; then
  echo "ERRO: há mudanças não commitadas. Faça commit ou stash antes de lançar." >&2
  git status --short >&2
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "AVISO: você está na branch '$BRANCH', não em 'main'." >&2
  read -r -p "Continuar mesmo assim? [s/N] " resp
  [ "$resp" = "s" ] || [ "$resp" = "S" ] || { echo "Cancelado."; exit 1; }
fi

# --- Lê a versão atual ---
CUR="$(grep -oE '__version__ *= *"[^"]+"' "$VERSION_FILE" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
if [ -z "$CUR" ]; then
  echo "ERRO: não consegui ler __version__ em $VERSION_FILE" >&2
  exit 1
fi

# --- Calcula a nova versão ---
IFS='.' read -r MA MI PA <<< "$CUR"
case "$BUMP" in
  major) NEW="$((MA + 1)).0.0" ;;
  minor) NEW="${MA}.$((MI + 1)).0" ;;
  patch) NEW="${MA}.${MI}.$((PA + 1))" ;;
  *)     NEW="$BUMP" ;;
esac

TAG="v${NEW}"
TODAY="$(date +%Y-%m-%d)"

echo "Versão atual : $CUR"
echo "Nova versão  : $NEW  (tag $TAG, data $TODAY)"

# --- Aborta se a tag já existir ---
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "ERRO: a tag $TAG já existe." >&2
  exit 1
fi

if [ "$DRY_RUN" = true ]; then
  echo "[dry-run] Nenhuma alteração feita."
  exit 0
fi

# --- Atualiza __version__ ---
python3 - "$VERSION_FILE" "$NEW" <<'PY'
import re, sys
path, new = sys.argv[1], sys.argv[2]
src = open(path, encoding="utf-8").read()
src = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new}"', src)
open(path, "w", encoding="utf-8").write(src)
PY

# --- Atualiza o CHANGELOG: renomeia [Não lançado] e recria bloco vazio ---
python3 - "$CHANGELOG" "$NEW" "$TODAY" <<'PY'
import sys
path, new, today = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path, encoding="utf-8").read()
marker = "## [Não lançado]"
if marker not in src:
    print("AVISO: seção '## [Não lançado]' não encontrada no CHANGELOG.", file=sys.stderr)
else:
    novo_bloco = (
        "## [Não lançado]\n\n"
        "<!-- Adicione aqui as mudanças que ainda não entraram em uma release. -->\n\n"
        f"## [{new}] - {today}"
    )
    src = src.replace(marker, novo_bloco, 1)
    # Adiciona os links de comparação no rodapé, se houver o padrão.
    link_unreleased = f"[Não lançado]: https://github.com/saulobcs/integracao-omie/compare/v{new}...HEAD"
    link_versao = f"[{new}]: https://github.com/saulobcs/integracao-omie/releases/tag/v{new}"
    import re
    src = re.sub(r"\[Não lançado\]: https://github\.com/\S+", link_unreleased, src, count=1)
    if link_versao not in src:
        src = src.rstrip() + "\n" + link_versao + "\n"
open(path, "w", encoding="utf-8").write(src)
PY

echo "Arquivos atualizados. Revise o diff:"
git --no-pager diff --stat

# --- Commit + tag ---
git add "$VERSION_FILE" "$CHANGELOG"
git commit -m "chore(release): ${TAG}"
git tag -a "$TAG" -m "Release ${TAG}"

echo "Commit e tag $TAG criados."

# --- Push ---
if [ "$DO_PUSH" = true ]; then
  git push origin "$BRANCH"
  git push origin "$TAG"
  echo "Push concluído. O workflow de Release vai criar o GitHub Release para $TAG."
else
  echo "--no-push: quando quiser publicar, rode:"
  echo "  git push origin $BRANCH && git push origin $TAG"
fi
