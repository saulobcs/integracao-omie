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
from decimal import Decimal
from typing import Any, Dict, Optional

from .matching_debito import casar_debito
from .omie_client import OmieClient
from .parser_ofx import Transacao
from .regras import Decisao


def _fmt_data(t: Transacao) -> Optional[str]:
    return t.data_posted.strftime("%d/%m/%Y") if t.data_posted else None


def _fmt_conta(
    ncodcc: Optional[int],
    plano_contas: Dict[int, str],
    descricao_config: Optional[str] = None,
    nome_fallback: Optional[str] = None,
) -> Optional[str]:
    """Formata uma conta como '(nCodCC) descricao'.

    Prioridade da descricao: a do proprio roteamento (descricao_config, para o
    arquivo ficar autossuficiente) -> plano de contas (contas-haru.json) ->
    nome da origem/regra. Se o nCodCC ainda nao estiver definido (pendencia
    P1), usa '(pendente) <descricao>'.
    """
    descricao = descricao_config or plano_contas.get(int(ncodcc)) if ncodcc is not None else descricao_config
    if ncodcc is None:
        rotulo = descricao or nome_fallback
        return f"(pendente) {rotulo}" if rotulo else None
    rotulo = descricao or nome_fallback or "?"
    return f"({ncodcc}) {rotulo}"


class ExecutorAcao(ABC):
    """Contrato de execucao de uma decisao de roteamento."""

    @abstractmethod
    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        """Retorna um registro descrevendo o que foi (ou seria) feito."""


class ExecutorDryRun(ExecutorAcao):
    """Nao chama a API: monta o payload proposto e marca como simulado."""

    def __init__(
        self,
        config: Dict[str, Any],
        origem: Optional[Dict[str, Any]] = None,
        plano_contas: Optional[Dict[int, str]] = None,
        client: Optional[OmieClient] = None,
    ):
        self.config = config
        self.origem = origem or {}
        # Mapa nCodCC -> descricao (do contas-haru.json), para exibir '(nCodCC) descricao'.
        self.plano_contas = plano_contas or {}
        # Cliente Omie read-only (opcional). Se presente, o debito e casado
        # consultando a API (PesquisarLancamentos + ConsultarCliente). Sem
        # cliente, apenas o payload proposto e registrado.
        self.client = client
        # nCodCC da conta de origem selecionada (pode ser None enquanto pendente P1).
        self.ncodcc_origem = self.origem.get("ncodcc_omie")
        # Conta de origem ja formatada como '(nCodCC) descricao'.
        self.conta_origem = _fmt_conta(
            self.ncodcc_origem,
            self.plano_contas,
            descricao_config=self.origem.get("descricao_origem"),
            nome_fallback=self.origem.get("nome"),
        )

    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        t = decisao.transacao
        base = {
            "fitid": t.fitid,
            "rota": decisao.rota,
            "regra": decisao.regra,
            "acao_omie": decisao.acao,
            "conta_origem": self.conta_origem,
            "conta_destino": None,
            "simulado": True,
            "payload_proposto": None,
            "endpoint": None,
            "call": None,
            "motivo": decisao.motivo,
        }

        if decisao.rota == "credito_roteado" and decisao.acao == "incluir_lanc_cc":
            base["conta_destino"] = _fmt_conta(
                decisao.ncodcc_destino,
                self.plano_contas,
                descricao_config=decisao.descricao_destino,
            )
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
            base["endpoint"] = "/api/v1/financas/pesquisartitulos/"
            base["call"] = "PesquisarLancamentos -> ConsultarCliente"
            if self.client is not None:
                # Executa o matching real (read-only): pesquisa titulos em aberto,
                # casa por valor exato e testa nome_fantasia no memo.
                match = casar_debito(self.client, Decimal(str(t.valor)), t.memo)
                base["payload_proposto"] = {
                    "match_status": match.status,
                    "ncod_titulo": match.ncod_titulo,
                    "ncod_cliente": match.ncod_cliente,
                    "nome_fantasia": match.nome_fantasia,
                    "razao_social": match.razao_social,
                    "valor_titulo": match.valor_titulo,
                    "candidatos_valor_exato": match.candidatos_valor_exato,
                    "trilha": match.trilha,
                }
                base["motivo"] = match.motivo
                if match.status == "casado":
                    # Titulo identificado: a baixa (escrita) fica fora do dry-run.
                    base["conta_destino"] = f"titulo {match.ncod_titulo} ({match.razao_social})"
                    base["payload_proposto"]["baixa_proposta"] = {
                        "endpoint": "/api/v1/financas/contapagar/",
                        "call": "LancarPagamento",
                        "codigo_lancamento": match.ncod_titulo,
                        "valor": abs(float(t.valor)),
                        "data": _fmt_data(t),
                        "observacao": f"Conciliacao OFX - FITID {t.fitid}",
                        "nota": "NAO executado no dry-run (metodo de escrita).",
                    }
                else:
                    # manual/erro: nao ha titulo unico casado -> revisao humana.
                    base["rota"] = "manual" if match.status == "manual" else base["rota"]
            else:
                # Sem cliente/credenciais: apenas descreve o que seria feito.
                data = _fmt_data(t)
                base["payload_proposto"] = {
                    "busca_titulo": {
                        "call": "PesquisarLancamentos",
                        "param": [
                            {
                                "nPagina": 1,
                                "nRegPorPagina": 100,
                                "cNatureza": "P",
                                "cStatus": "EMABERTO",
                                "dDtVencDe": "<hoje-5d>",
                                "dDtVencAte": "<hoje+5d>",
                            }
                        ],
                    },
                    "match_valor_client_side": abs(float(t.valor)),
                    "memo_ofx": t.memo,
                    "observacao": (
                        "Sem credenciais (.env): matching nao executado. Com .env, "
                        "casa por valor exato (nValorTitulo) + nome_fantasia "
                        "(ConsultarCliente) contido no memo."
                    ),
                }

        elif decisao.rota == "pendente_debito":
            base["conta_destino"] = _fmt_conta(
                decisao.ncodcc_destino,
                self.plano_contas,
                descricao_config=decisao.descricao_destino,
            )
            base["endpoint"] = None
            base["call"] = None
            base["payload_proposto"] = {
                "contexto": "Debito Stone - tratativa a validar (baixa de conta a pagar vs. lancamento em Stone - Cartão de Débito).",
                "conta_debito_sugerida": base["conta_destino"],
                "valor": abs(float(t.valor)),
                "memo": t.memo,
            }

        elif decisao.rota == "pendente_p4":
            base["endpoint"] = None
            base["call"] = None
            base["payload_proposto"] = {
                "contexto": "Debito Pix (freelancer/motoboy) - tratativa a definir (P4).",
            }

        # rota 'manual' fica sem payload: requer intervencao humana.
        return base
