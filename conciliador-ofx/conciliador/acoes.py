"""Camada de acao plugavel.

Isola o ponto onde a integracao com o Omie aconteceria. Hoje existe apenas a
implementacao DRY-RUN, que monta o payload que SERIA enviado e o registra, sem
chamar a API (ainda nao ha app_key/app_secret).

Quando as credenciais existirem, basta criar uma implementacao `OmieReal` que
herde de `ExecutorAcao` e faca o POST usando o mesmo payload -- o restante do
fluxo (parser, regras, relatorio) nao muda.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .parser_ofx import Transacao
from .regras import Decisao


def _fmt_data(t: Transacao) -> Optional[str]:
    return t.data_posted.strftime("%d/%m/%Y") if t.data_posted else None


class ExecutorAcao(ABC):
    """Contrato de execucao de uma decisao de roteamento."""

    @abstractmethod
    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        """Retorna um registro descrevendo o que foi (ou seria) feito."""


class ExecutorDryRun(ExecutorAcao):
    """Nao chama a API: monta o payload proposto e marca como simulado."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ncodcc_origem = (
            config.get("conta_corrente_origem", {}).get("ncodcc_omie")
        )

    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        t = decisao.transacao
        base = {
            "fitid": t.fitid,
            "rota": decisao.rota,
            "regra": decisao.regra,
            "acao_omie": decisao.acao,
            "simulado": True,
            "payload_proposto": None,
            "endpoint": None,
            "call": None,
            "motivo": decisao.motivo,
        }

        if decisao.rota == "credito_roteado" and decisao.acao == "incluir_lanc_cc":
            base["endpoint"] = "/api/v1/financas/contacorrentelancamentos/"
            base["call"] = "IncluirLancCC"
            base["payload_proposto"] = {
                "cabecalho": {
                    "nCodCC": decisao.ncodcc_destino,  # placeholder (pendencia P1)
                    "dDtLanc": _fmt_data(t),
                    "nValorLanc": float(t.valor),
                },
                "detalhes": {
                    "cCodCateg": decisao.ccodcateg,  # placeholder (pendencia P1)
                    "cTipo": "PIX",
                },
                "cCodIntLanc": t.fitid,  # ancora de idempotencia (pendencia P3)
            }

        elif decisao.rota == "baixa_conta_pagar":
            base["endpoint"] = "/api/v1/financas/contapagar/"
            base["call"] = "PesquisarTitulos -> baixa"
            base["payload_proposto"] = {
                "busca_titulo": {
                    "cNatureza": "P",
                    "nValorTitulo": abs(float(t.valor)),
                    "dDtPrevisao": _fmt_data(t),
                    "cMemoOFX": t.memo,
                },
                "observacao": "Se encontrar 1 titulo -> baixar; senao -> manual.",
            }

        elif decisao.rota == "pendente_p4":
            base["endpoint"] = None
            base["call"] = None
            base["payload_proposto"] = {
                "contexto": "Debito Pix (freelancer/motoboy) - tratativa a definir (P4).",
            }

        # rota 'manual' fica sem payload: requer intervencao humana.
        return base
