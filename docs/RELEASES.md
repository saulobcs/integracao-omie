# Processo de Release

Este projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/)
(`vMAJOR.MINOR.PATCH`) e gera os GitHub Releases automaticamente a partir de
tags Git.

## Como escolher o número da versão

| Parte | Quando incrementar | Exemplo |
|-------|--------------------|---------|
| **MAJOR** | Mudança incompatível (quebra a CLI, muda o formato do `roteamento.json`, remove/renomeia campos) | `1.0.0 → 2.0.0` |
| **MINOR** | Nova funcionalidade compatível (novo modo, suporte a novo banco/cliente) | `1.2.0 → 1.3.0` |
| **PATCH** | Correção de bug sem mudar comportamento esperado | `1.3.0 → 1.3.1` |

Pré-lançamentos usam sufixo: `v1.3.0-rc.1`.

## Peças da automação

| Arquivo | Função |
|---------|--------|
| `conciliador-ofx/conciliador/__init__.py` | Fonte única da verdade da versão (`__version__`). Exposta na CLI via `--version`. |
| `CHANGELOG.md` | Registro legível por humanos, formato [Keep a Changelog](https://keepachangelog.com/pt-BR/). |
| `.github/release.yml` | Agrupa as notas automáticas por categoria, a partir das labels dos PRs. |
| `.github/workflows/release.yml` | Ao receber uma tag `vX.Y.Z`, valida a versão e cria o GitHub Release com notas automáticas. |
| `scripts/release.sh` | Automatiza o bump de versão, o CHANGELOG, o commit, a tag e o push. |

## Fluxo recomendado (com o script)

Pré-requisitos: estar na `main`, atualizada e **sem mudanças pendentes**.

```bash
# 1. Ver o que mudaria (não altera nada)
scripts/release.sh minor --dry-run

# 2. Executar de fato (bump + changelog + commit + tag + push)
scripts/release.sh minor
```

O `release.sh`:
1. Calcula a nova versão (`major`/`minor`/`patch` ou um valor explícito `X.Y.Z`).
2. Atualiza `__version__`.
3. Move a seção `[Não lançado]` do CHANGELOG para a nova versão datada e recria
   o bloco `[Não lançado]` vazio.
4. Cria o commit `chore(release): vX.Y.Z` e a tag anotada.
5. Faz push da branch e da tag.

Assim que a tag chega ao GitHub, o workflow **Release** cria o GitHub Release
com as notas geradas automaticamente.

### Opções do script

| Flag | Efeito |
|------|--------|
| `--dry-run` | Mostra a versão calculada e sai, sem alterar arquivos. |
| `--no-push` | Faz commit e tag localmente, mas não faz push (você publica quando quiser). |

## Fluxo manual (sem o script)

```bash
# 1. Atualizar a versão em conciliador-ofx/conciliador/__init__.py
#    e mover a seção [Não lançado] no CHANGELOG.md

# 2. Commit
git add conciliador-ofx/conciliador/__init__.py CHANGELOG.md
git commit -m "chore(release): v0.2.0"

# 3. Tag anotada + push
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin main
git push origin v0.2.0
```

> A tag **precisa** bater com `__version__`; caso contrário o workflow falha na
> etapa de validação.

## Melhorar as notas automáticas

As notas do Release são agrupadas pelas **labels** dos Pull Requests
(ver `.github/release.yml`). Rotule cada PR com uma destas para cair na
categoria certa:

- `feature` / `enhancement` → 🚀 Funcionalidades
- `fix` / `bug` → 🐛 Correções
- `security` → 🔒 Segurança
- `docs` → 📝 Documentação
- `chore` / `refactor` / `ci` / `build` → 🧹 Manutenção e refatoração
- `ignore-for-release` → não aparece nas notas

## Primeiro release (v0.1.0)

O `CHANGELOG.md` já traz a seção `0.1.0` descrevendo o estado atual. Para
publicá-la, com a `main` limpa:

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

O workflow cuida do resto.
