"""Motor de regras de roteamento.

Decide, para cada transacao do extrato, qual acao seria executada no Omie,
com base no sinal (credito/debito) e no texto do MEMO, conforme o mapa de
configuracao (config/roteamento.json).

O mapa suporta MULTIPLAS contas de origem: a origem e identificada pelo
BANKID/ACCTID do extrato OFX e cada origem tem suas proprias regras de
credito/debito e contas de destino.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .parser_ofx import Extrato, Transacao


@dataclass
class Decisao:
    """Resultado do roteamento de uma transacao."""

    transacao: Transacao
    rota: str  # credito_roteado | baixa_conta_pagar | pendente_p4 | manual
    regra: Optional[str]  # nome da regra que casou
    acao: Optional[str]  # acao proposta no Omie
    ncodcc_destino: Optional[int] = None
    descricao_destino: Optional[str] = None
    ccodcateg: Optional[str] = None
    motivo: str = ""


def _casa(memo: str, match: Dict[str, Any]) -> bool:
    tipo = match.get("tipo")
    valor = match.get("valor", "")
    if tipo == "igual":
        return memo == valor
    if tipo == "prefixo":
        return memo.startswith(valor)
    if tipo == "sufixo":
        return memo.endswith(valor)
    if tipo == "contem":
        return valor in memo
    if tipo == "regex":
        return re.search(valor, memo) is not None
    return False


def _norm(valor: Optional[str]) -> str:
    """Normaliza identificadores de conta para comparacao tolerante.

    O BANKID pode vir com/sem zeros a esquerda (ex.: '0197' vs '197') e o
    ACCTID pode variar em formatacao/espacos. Comparamos so pelos digitos,
    removendo zeros a esquerda do banco.
    """
    return re.sub(r"\D", "", valor or "")


class MotorDeRegras:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.origens: List[Dict[str, Any]] = config.get("origens", [])
        # Origem selecionada apos identificar o extrato (ver selecionar_origem).
        self.origem: Optional[Dict[str, Any]] = None
        self.regras_credito: List[Dict[str, Any]] = []
        self.regras_debito: List[Dict[str, Any]] = []

    @classmethod
    def de_arquivo(cls, caminho: str) -> "MotorDeRegras":
        with open(caminho, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def _casa_origem(self, match: Dict[str, Any], extrato: Extrato) -> bool:
        """Compara o BANKID/ACCTID do extrato com o match_origem da config."""
        bankid_cfg = _norm(match.get("bankid"))
        acctid_cfg = _norm(match.get("acctid"))
        bankid_ofx = _norm(extrato.bankid)
        acctid_ofx = _norm(extrato.acctid)
        # Zeros a esquerda do banco nao devem impedir o match ('0197' == '197').
        banco_ok = bankid_ofx.lstrip("0") == bankid_cfg.lstrip("0")
        conta_ok = acctid_ofx == acctid_cfg
        return banco_ok and conta_ok

    def selecionar_origem(self, extrato: Extrato) -> Optional[Dict[str, Any]]:
        """Identifica a conta de origem do extrato e carrega suas regras.

        Retorna a origem casada (ou None se nenhuma bater). Deve ser chamada
        antes de `rotear`.
        """
        for origem in self.origens:
            if self._casa_origem(origem.get("match_origem", {}), extrato):
                self.origem = origem
                self.regras_credito = origem.get("regras_credito", [])
                self.regras_debito = origem.get("regras_debito", [])
                return origem
        # Nenhuma origem casou: zera as regras para tudo cair em manual.
        self.origem = None
        self.regras_credito = []
        self.regras_debito = []
        return None

    def rotear(self, t: Transacao) -> Decisao:
        # Sem origem identificada, nao ha como mapear destinos -> manual.
        if self.origem is None:
            return Decisao(
                transacao=t,
                rota="manual",
                regra=None,
                acao=None,
                motivo="Conta de origem do extrato nao mapeada na configuracao.",
            )

        # Credito -> roteamento por MEMO para conta destino.
        if t.is_credito:
            for regra in self.regras_credito:
                if _casa(t.memo, regra["match"]):
                    return Decisao(
                        transacao=t,
                        rota="credito_roteado",
                        regra=regra.get("nome"),
                        acao=regra.get("acao"),
                        ncodcc_destino=regra.get("ncodcc_destino"),
                        descricao_destino=regra.get("descricao_destino"),
                        ccodcateg=regra.get("ccodcateg"),
                        motivo="MEMO casou com regra de credito.",
                    )
            return Decisao(
                transacao=t,
                rota="manual",
                regra=None,
                acao=None,
                motivo="Credito sem regra correspondente.",
            )

        # Debito -> baixa de conta a pagar, lancamento em CC ou tratativa configurada.
        if t.is_debito:
            for regra in self.regras_debito:
                if _casa(t.memo, regra["match"]):
                    acao = regra.get("acao")
                    if acao == "baixar_conta_pagar":
                        rota = "baixa_conta_pagar"
                    elif acao == "incluir_lanc_cc":
                        # Lancamento direto em conta corrente (mesmo tratamento
                        # do credito roteado), ex.: integralizacao de capital.
                        rota = "credito_roteado"
                    else:
                        rota = acao
                    return Decisao(
                        transacao=t,
                        rota=rota,
                        regra=regra.get("nome"),
                        acao=acao,
                        ncodcc_destino=regra.get("ncodcc_destino"),
                        descricao_destino=regra.get("descricao_destino"),
                        ccodcateg=regra.get("ccodcateg"),
                        motivo=regra.get("observacao", "MEMO casou com regra de debito."),
                    )
            return Decisao(
                transacao=t,
                rota="manual",
                regra=None,
                acao=None,
                motivo="Debito sem regra correspondente.",
            )

        # Valor zero / indefinido.
        return Decisao(
            transacao=t,
            rota="manual",
            regra=None,
            acao=None,
            motivo="Transacao com valor zero ou tipo indefinido.",
        )
