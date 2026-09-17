"""Camada de acao plugavel -- dois executores.

A DECISAO (o que fazer: qual conta destino, cCodIntLanc, matching de debito,
idempotencia) fica na classe base `ExecutorAcao._decidir`, compartilhada. Sobre
essa decisao, dois executores concretos:

- `ExecutorDryRun`: NAO escreve. Consulta a API (leitura) para idempotencia e
  matching de debito, mas as acoes de escrita ficam apenas como "proposta" no
  relatorio. E o modo de validacao das regras de roteamento.

- `ExecutorApply`: modo de EXECUCAO final. Reusa a mesma decisao e, ao final,
  EXECUTA as escritas (IncluirLancCC / LancarPagamento) via um OmieClient com
  somente_leitura=False. Respeita idempotencia (nao inclui credito que ja
  existe) e so age em decisoes conclusivas.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, Optional

from .matching_debito import casar_debito
from .omie_client import OmieClient
from .parser_ofx import Transacao
from .regras import Decisao

# Limite do campo cCodIntLanc na API Omie (string 20). O FITID da Stone e um
# UUID de 36 caracteres e NAO cabe direto -- por isso derivamos um codigo curto.
_CCODINTLANC_MAX = 20


def _derivar_ccodintlanc(fitid: Optional[str]) -> Optional[str]:
    """Deriva o cCodIntLanc (<=20 chars) a partir do FITID do extrato.

    O FITID (UUID de 36 chars) nao cabe no campo cCodIntLanc (string 20) da
    Omie. Se couber (<=20), usa o proprio FITID. Caso contrario, gera um hash
    DETERMINISTICO: os 20 primeiros hex do SHA-256 do FITID. Deterministico =>
    o mesmo FITID sempre gera o mesmo codigo, preservando a idempotencia
    server-side (reenvio do mesmo lancamento e reconhecido).
    """
    if not fitid:
        return None
    fitid = fitid.strip()
    if len(fitid) <= _CCODINTLANC_MAX:
        return fitid
    digest = hashlib.sha256(fitid.encode("utf-8")).hexdigest()
    return digest[:_CCODINTLANC_MAX]


def _fmt_data(t: Transacao) -> Optional[str]:
    return t.data_posted.strftime("%d/%m/%Y") if t.data_posted else None


def _consultar_lancamento_existente(
    client: OmieClient, ccodintlanc: str
) -> Optional[int]:
    """Consulta idempotencia via ConsultaLancCC pelo cCodIntLanc.

    Retorna o nCodLanc se ja existir um lancamento com esse codigo de
    integracao; None se nao existir. Erros de "nao encontrado" da Omie
    (faultstring) sao tratados como "nao existe".
    """
    from .omie_client import OmieFault

    try:
        resp = client.chamar("ConsultaLancCC", {"cCodIntLanc": ccodintlanc})
    except OmieFault:
        # A Omie sinaliza inexistencia via faultstring -> tratamos como "nao existe".
        return None
    ncod = resp.get("nCodLanc") if isinstance(resp, dict) else None
    return int(ncod) if ncod else None


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
    """Contrato + decisao compartilhada entre os executores.

    `_decidir` produz o registro (base dict) com todos os dados da acao, inc
    luindo -- quando ha escrita a fazer -- um `_plano_escrita` (call, endpoint,
    param) que o executor concreto decide se descreve (dry-run) ou executa
    (apply). A decisao usa o cliente APENAS para leitura (idempotencia e
    matching de debito), valida em ambos os modos.
    """

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
        # Cliente Omie. No dry-run e read-only; no apply e read-write. A DECISAO
        # so usa metodos de leitura (idempotencia/matching), validos em ambos.
        self.client = client
        self.ncodcc_origem = self.origem.get("ncodcc_omie")
        self.conta_origem = _fmt_conta(
            self.ncodcc_origem,
            self.plano_contas,
            descricao_config=self.origem.get("descricao_origem"),
            nome_fallback=self.origem.get("nome"),
        )

    @abstractmethod
    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        """Retorna um registro descrevendo o que foi (ou seria) feito."""

    def _decidir(self, decisao: Decisao) -> Dict[str, Any]:
        """Monta o registro da decisao (comum a dry-run e apply).

        Quando ha uma escrita a realizar, anexa `base['_plano_escrita']` com
        `{call, endpoint, param}`. Rotas sem escrita (manual, pendentes, credito
        ja existente) nao anexam plano.
        """
        t = decisao.transacao
        base: Dict[str, Any] = {
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
            "_plano_escrita": None,
        }

        if decisao.rota == "credito_roteado" and decisao.acao == "incluir_lanc_cc":
            self._decidir_credito(decisao, base)
        elif decisao.rota == "baixa_conta_pagar":
            self._decidir_debito(decisao, base)
        elif decisao.rota == "pendente_debito":
            base["conta_destino"] = _fmt_conta(
                decisao.ncodcc_destino,
                self.plano_contas,
                descricao_config=decisao.descricao_destino,
            )
            base["payload_proposto"] = {
                "contexto": "Debito Stone - tratativa a validar (baixa de conta a pagar vs. lancamento em Stone - Cartão de Débito).",
                "conta_debito_sugerida": base["conta_destino"],
                "valor": abs(float(t.valor)),
                "memo": t.memo,
            }
        elif decisao.rota == "pendente_p4":
            base["payload_proposto"] = {
                "contexto": "Debito Pix (freelancer/motoboy) - tratativa a definir (P4).",
            }
        # rota 'manual' fica sem payload: requer intervencao humana.
        return base

    def _decidir_credito(self, decisao: Decisao, base: Dict[str, Any]) -> None:
        t = decisao.transacao
        base["conta_destino"] = _fmt_conta(
            decisao.ncodcc_destino,
            self.plano_contas,
            descricao_config=decisao.descricao_destino,
        )
        base["endpoint"] = "/api/v1/financas/contacorrentelancamentos/"
        base["call"] = "IncluirLancCC"
        # cCodIntLanc: <=20 chars derivado do FITID (hash deterministico se >20).
        ccodintlanc = _derivar_ccodintlanc(t.fitid)
        payload = {
            "cCodIntLanc": ccodintlanc,
            "cabecalho": {
                "nCodCC": decisao.ncodcc_destino,  # placeholder (pendencia P1)
                "dDtLanc": _fmt_data(t),
                "nValorLanc": float(t.valor),
            },
            "detalhes": {
                "cCodCateg": decisao.ccodcateg,  # placeholder (pendencia P1)
                "cTipo": "PIX",
            },
        }
        base["payload_proposto"] = {**payload, "fitid_origem": t.fitid}

        # Idempotencia: consulta se ja existe lancamento com esse cCodIntLanc.
        if self.client is not None and ccodintlanc:
            ncod_existente = _consultar_lancamento_existente(self.client, ccodintlanc)
            if ncod_existente is not None:
                base["call"] = "ConsultaLancCC (ja existe)"
                base["motivo"] = (
                    f"Lancamento ja existe (nCodLanc {ncod_existente}) para "
                    f"cCodIntLanc {ccodintlanc}. Nao incluido."
                )
                base["payload_proposto"]["idempotencia"] = {
                    "ja_existe": True,
                    "nCodLanc": ncod_existente,
                    "cCodIntLanc": ccodintlanc,
                    "consulta": "ConsultaLancCC",
                }
                return  # ja existe -> sem plano de escrita
            base["payload_proposto"]["idempotencia"] = {
                "ja_existe": False,
                "cCodIntLanc": ccodintlanc,
                "consulta": "ConsultaLancCC",
            }

        # Ha inclusao a fazer -> registra o plano de escrita.
        base["_plano_escrita"] = {
            "call": "IncluirLancCC",
            "endpoint": "/api/v1/financas/contacorrentelancamentos/",
            "param": payload,
        }

    def _decidir_debito(self, decisao: Decisao, base: Dict[str, Any]) -> None:
        t = decisao.transacao
        base["endpoint"] = "/api/v1/financas/pesquisartitulos/"
        base["call"] = "PesquisarLancamentos -> ConsultarCliente"
        if self.client is None:
            # Sem cliente: apenas descreve o que seria feito.
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
            return

        # Matching real (leitura): pesquisa, casa por valor exato + nome_fantasia.
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
            base["conta_destino"] = f"titulo {match.ncod_titulo} ({match.razao_social})"
            baixa = {
                "codigo_lancamento": match.ncod_titulo,
                "valor": abs(float(t.valor)),
                "data": _fmt_data(t),
                "observacao": f"Conciliacao OFX - FITID {t.fitid}",
            }
            base["payload_proposto"]["baixa_proposta"] = {
                "endpoint": "/api/v1/financas/contapagar/",
                "call": "LancarPagamento",
                **baixa,
            }
            base["_plano_escrita"] = {
                "call": "LancarPagamento",
                "endpoint": "/api/v1/financas/contapagar/",
                "param": baixa,
            }
        else:
            # manual/erro: nao ha titulo unico casado -> revisao humana.
            base["rota"] = "manual" if match.status == "manual" else base["rota"]


class ExecutorDryRun(ExecutorAcao):
    """Nao escreve: monta a decisao e marca a escrita como apenas proposta."""

    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        base = self._decidir(decisao)
        plano = base.pop("_plano_escrita", None)
        base["simulado"] = True
        if plano is not None:
            # Marca a proposta como nao executada (o payload ja esta em payload_proposto).
            pp = base.get("payload_proposto")
            if isinstance(pp, dict):
                if "baixa_proposta" in pp and isinstance(pp["baixa_proposta"], dict):
                    pp["baixa_proposta"]["nota"] = "NAO executado no dry-run (metodo de escrita)."
                elif "idempotencia" in pp and isinstance(pp["idempotencia"], dict):
                    pp["idempotencia"]["nota"] = (
                        "Nao existe -> apto a incluir (IncluirLancCC nao executado no dry-run)."
                    )
        return base


class ExecutorApply(ExecutorAcao):
    """Modo de EXECUCAO final: reusa a decisao e EXECUTA as escritas.

    Requer um OmieClient com somente_leitura=False. Para cada decisao com
    `_plano_escrita`, dispara o `call` (IncluirLancCC / LancarPagamento) e
    registra o resultado (nCodLanc / codigo_baixa) ou o erro. Decisoes sem
    plano (manual, pendentes, credito ja existente) nao geram escrita.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.client is None:
            raise ValueError("ExecutorApply requer um OmieClient (com credenciais).")
        if getattr(self.client, "somente_leitura", True):
            raise ValueError(
                "ExecutorApply requer OmieClient com somente_leitura=False."
            )

    def executar(self, decisao: Decisao) -> Dict[str, Any]:
        from .omie_client import OmieError

        base = self._decidir(decisao)
        plano = base.pop("_plano_escrita", None)
        base["simulado"] = False
        if plano is None:
            base["executado"] = False
            return base

        try:
            resp = self.client.chamar(plano["call"], plano["param"])
            base["executado"] = True
            base["resultado_execucao"] = {
                "call": plano["call"],
                "nCodLanc": resp.get("nCodLanc"),
                "cCodIntLanc": resp.get("cCodIntLanc"),
                "codigo_lancamento": resp.get("codigo_lancamento"),
                "codigo_baixa": resp.get("codigo_baixa"),
                "cCodStatus": resp.get("cCodStatus"),
                "cDesStatus": resp.get("cDesStatus"),
            }
            base["motivo"] = f"Executado {plano['call']} com sucesso."
        except OmieError as exc:
            base["executado"] = False
            base["erro_execucao"] = str(exc)
            base["motivo"] = f"Falha ao executar {plano['call']}: {exc}"
        return base
