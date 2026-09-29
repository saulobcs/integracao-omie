"""Perfis isolados de clientes (configuração, credenciais e contas OFX)."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from .parser_ofx import Extrato


class PerfilInvalido(ValueError):
    """Perfil inexistente ou OFX não autorizado para o perfil selecionado."""


@dataclass(frozen=True)
class PerfilCliente:
    id: str
    nome: str
    config_path: str
    plano_contas_path: str
    env_path: str
    saida_path: str
    confirmacao_apply: str
    contas_ofx_permitidas: List[Dict[str, str]]

    @staticmethod
    def _normalizar(valor: object) -> str:
        return re.sub(r"\D", "", str(valor or ""))

    def validar_extrato(self, extrato: Extrato) -> None:
        banco = self._normalizar(extrato.bankid).lstrip("0")
        conta = self._normalizar(extrato.acctid)
        for permitida in self.contas_ofx_permitidas:
            if (
                banco == self._normalizar(permitida.get("bankid")).lstrip("0")
                and conta == self._normalizar(permitida.get("acctid"))
            ):
                return
        raise PerfilInvalido(
            f"BLOQUEADO: o OFX identifica banco {extrato.bankid!r} e conta "
            f"{extrato.acctid!r}, que não pertencem ao cliente selecionado "
            f"{self.nome!r}. Nenhuma consulta ou escrita no Omie foi realizada."
        )


_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RAIZ_REPOSITORIO = os.path.dirname(_RAIZ)
_REGISTRO = os.path.join(_RAIZ, "clientes", "clientes.json")


def _caminho_relativo(valor: str) -> str:
    caminho = os.path.abspath(os.path.join(_RAIZ, valor))
    if os.path.commonpath([_RAIZ_REPOSITORIO, caminho]) != _RAIZ_REPOSITORIO:
        raise PerfilInvalido("Caminho de perfil fora do repositório.")
    return caminho


def listar_perfis() -> List[PerfilCliente]:
    if not os.path.isfile(_REGISTRO):
        raise PerfilInvalido(f"Registro de clientes não encontrado: {_REGISTRO}")
    with open(_REGISTRO, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    perfis: List[PerfilCliente] = []
    for item in dados.get("clientes", []):
        cliente_id = str(item.get("id", ""))
        if not re.fullmatch(r"[a-z0-9_-]+", cliente_id):
            raise PerfilInvalido(f"Identificador de cliente inválido: {cliente_id!r}")
        perfis.append(
            PerfilCliente(
                id=cliente_id,
                nome=str(item["nome"]),
                config_path=_caminho_relativo(str(item["config"])),
                plano_contas_path=_caminho_relativo(str(item["plano_contas"])),
                env_path=_caminho_relativo(str(item["env"])),
                saida_path=_caminho_relativo(str(item["saida"])),
                confirmacao_apply=str(item.get("confirmacao_apply") or cliente_id.upper()),
                contas_ofx_permitidas=list(item.get("contas_ofx_permitidas") or []),
            )
        )
    return perfis


def carregar_perfil(cliente_id: str) -> PerfilCliente:
    for perfil in listar_perfis():
        if perfil.id == cliente_id:
            return perfil
    raise PerfilInvalido(f"Cliente não encontrado: {cliente_id!r}")
