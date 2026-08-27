"""Motor de regras de roteamento.

Decide, para cada transacao do extrato, qual acao seria executada no Omie,
com base no sinal (credito/debito) e no texto do MEMO, conforme o mapa de
configuracao (config/roteamento.json).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .parser_ofx import Transacao


@dataclass
class Decisao:
    """Resultado do roteamento de uma transacao."""

    transacao: Transacao
    rota: str  # credito_roteado | baixa_conta_pagar | pendente_p4 | manual
    regra: Optional[str]  # nome da regra que casou
    acao: Optional[str]  # acao proposta no Omie
    ncodcc_destino: Optional[int] = None
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


class MotorDeRegras:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.regras_credito: List[Dict[str, Any]] = config.get("regras_credito", [])
        self.regras_debito: List[Dict[str, Any]] = config.get("regras_debito", [])

    @classmethod
    def de_arquivo(cls, caminho: str) -> "MotorDeRegras":
        with open(caminho, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def rotear(self, t: Transacao) -> Decisao:
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

        # Debito -> baixa de conta a pagar ou tratativa configurada.
        if t.is_debito:
            for regra in self.regras_debito:
                if _casa(t.memo, regra["match"]):
                    acao = regra.get("acao")
                    rota = "baixa_conta_pagar" if acao == "baixar_conta_pagar" else acao
                    return Decisao(
                        transacao=t,
                        rota=rota,
                        regra=regra.get("nome"),
                        acao=acao,
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
