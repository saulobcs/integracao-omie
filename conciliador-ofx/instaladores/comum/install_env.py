#!/usr/bin/env python3
"""Prepara os arquivos .env a partir dos .example, sem sobrescrever existentes.

Usado pelos instaladores (instaladores/<sistema>/). Copia:
  - .env da raiz (a partir de .env.example);
  - o .env de cada cliente listado em clientes/clientes.json (a partir do
    respectivo .env.example).

Nunca sobrescreve um .env que ja exista (preserva credenciais). Imprime a lista
de .env criados (relativos a raiz) para o instalador exibir o que ficou
pendente de preenchimento.

Uso: python install_env.py RAIZ   (RAIZ = pasta conciliador-ofx/)
"""

from __future__ import annotations

import json
import os
import shutil
import sys


def _preparar(env_path: str, exemplo_path: str, criados: list) -> None:
    if os.path.exists(env_path):
        return  # nunca sobrescreve credenciais existentes
    if os.path.exists(exemplo_path):
        os.makedirs(os.path.dirname(env_path) or ".", exist_ok=True)
        shutil.copyfile(exemplo_path, env_path)
        criados.append(env_path)


def preparar_envs(raiz: str) -> list:
    """Cria os .env faltantes a partir dos .example. Retorna os criados."""
    criados: list = []

    # .env da raiz (uso single).
    _preparar(os.path.join(raiz, ".env"), os.path.join(raiz, ".env.example"), criados)

    # .env de cada cliente registrado.
    registro = os.path.join(raiz, "clientes", "clientes.json")
    if os.path.isfile(registro):
        with open(registro, encoding="utf-8") as fh:
            dados = json.load(fh)
        for item in dados.get("clientes", []):
            env_rel = item.get("env")
            if not env_rel:
                continue
            env_path = os.path.normpath(os.path.join(raiz, env_rel))
            _preparar(env_path, env_path + ".example", criados)

    return criados


def main() -> None:
    raiz = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    criados = preparar_envs(raiz)
    if criados:
        print("    Criados (preencha as credenciais):")
        for caminho in criados:
            print(f"      - {os.path.relpath(caminho, raiz)}")
    else:
        print("    Nenhum .env novo criado (ja existiam ou sem .example).")


if __name__ == "__main__":
    main()
