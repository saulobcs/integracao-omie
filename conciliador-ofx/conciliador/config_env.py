"""Carregamento de credenciais/config a partir de .env (sem dependencias).

Le um arquivo .env simples (KEY=VALUE por linha, com suporte a comentarios `#`
e aspas opcionais) e o mescla com as variaveis de ambiente do processo. As
variaveis de ambiente tem precedencia sobre o .env, para permitir override em
CI/execucao pontual.

Uso:
    from conciliador.config_env import carregar_credenciais
    cred = carregar_credenciais()  # procura .env ao lado do main.py
    cred.app_key, cred.app_secret, cred.base
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

_BASE_PADRAO = "https://app.omie.com.br/api/v1"


@dataclass
class Credenciais:
    """Credenciais da API Omie + host base."""

    app_key: Optional[str]
    app_secret: Optional[str]
    base: str = _BASE_PADRAO

    @property
    def completo(self) -> bool:
        """True se app_key e app_secret estao preenchidos."""
        return bool(self.app_key) and bool(self.app_secret)


def _parse_env_file(caminho: str) -> Dict[str, str]:
    """Le um .env simples em um dicionario. Ignora linhas vazias/comentarios."""
    dados: Dict[str, str] = {}
    if not os.path.exists(caminho):
        return dados
    with open(caminho, encoding="utf-8") as fh:
        for linha in fh:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave:
                dados[chave] = valor
    return dados


def carregar_credenciais(env_path: Optional[str] = None) -> Credenciais:
    """Carrega credenciais do .env (se houver) + variaveis de ambiente.

    Precedencia: variavel de ambiente > .env > padrao. Assim da para sobrescrever
    pontualmente sem editar o arquivo (ex.: `OMIE_APP_KEY=... python main.py`).

    Se `env_path` nao for informado, procura um `.env` ao lado do pacote
    (raiz do projeto conciliador-ofx/).
    """
    if env_path is None:
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(raiz, ".env")

    arquivo = _parse_env_file(env_path)

    def _get(chave: str, padrao: Optional[str] = None) -> Optional[str]:
        # Ambiente do processo tem prioridade sobre o .env.
        return os.environ.get(chave) or arquivo.get(chave) or padrao

    return Credenciais(
        app_key=_get("OMIE_APP_KEY"),
        app_secret=_get("OMIE_APP_SECRET"),
        base=_get("OMIE_BASE", _BASE_PADRAO) or _BASE_PADRAO,
    )
