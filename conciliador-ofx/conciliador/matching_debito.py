"""Matching de titulos a pagar para transacoes de DEBITO do extrato.

Regra (confirmada com o negocio), executada em modo read-only:

  1. Identificar a transacao de debito (feito no roteamento).
  2. Pesquisar titulos a pagar EM ABERTO com vencimento na janela
     [hoje - 5 dias, hoje + 5 dias] (PesquisarLancamentos).
  3. Comparar o valor do debito (absoluto) com o `nValorTitulo` de cada titulo
     retornado; manter apenas os de valor EXATAMENTE igual.
  4. Para cada candidato de valor exato, consultar o cliente pelo
     `nCodCliente` (ConsultarCliente).
  5. Verificar se o `nome_fantasia` do cliente esta contido no `memo` do
     extrato (case-insensitive). Se casar, e o titulo do debito.

Falha em qualquer etapa (0 titulos, nenhum valor exato, nenhum nome_fantasia
contido no memo, ou ambiguidade) -> resultado "manual".

Este modulo NAO baixa o titulo: apenas identifica. A baixa (escrita) fica fora
do dry-run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .omie_client import OmieClient, OmieError

# Janela de busca por vencimento, em dias, em torno da data de execucao.
JANELA_DIAS = 5


@dataclass
class ResultadoMatch:
    """Resultado do matching de um debito contra os titulos a pagar."""

    status: str  # "casado" | "manual" | "erro"
    motivo: str
    ncod_titulo: Optional[int] = None
    ncod_cliente: Optional[int] = None
    nome_fantasia: Optional[str] = None
    razao_social: Optional[str] = None
    valor_titulo: Optional[float] = None
    # Trilha das etapas para o relatorio (o que foi consultado e o que retornou).
    trilha: List[str] = field(default_factory=list)
    candidatos_valor_exato: int = 0


def _fmt(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")


def _decimais_iguais(a: Decimal, b: Decimal) -> bool:
    """Compara dois valores monetarios com 2 casas, evitando ruido de float."""
    return a.quantize(Decimal("0.01")) == b.quantize(Decimal("0.01"))


def _extrair_titulos(resposta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normaliza a lista de titulos do retorno do PesquisarLancamentos.

    A resposta tem `titulosEncontrados: [{ cabecTitulo: {...} }, ...]`.
    Devolve a lista de `cabecTitulo`.
    """
    encontrados = resposta.get("titulosEncontrados") or []
    titulos: List[Dict[str, Any]] = []
    for item in encontrados:
        cab = item.get("cabecTitulo") if isinstance(item, dict) else None
        if cab:
            titulos.append(cab)
    return titulos


def pesquisar_titulos_em_aberto(
    client: OmieClient,
    hoje: datetime,
    janela_dias: int = JANELA_DIAS,
) -> List[Dict[str, Any]]:
    """Etapa 2: pesquisa titulos a pagar EM ABERTO na janela de vencimento.

    Pagina ate esgotar (nTotPaginas). Retorna a lista de `cabecTitulo`.
    """
    d_de = _fmt(hoje - timedelta(days=janela_dias))
    d_ate = _fmt(hoje + timedelta(days=janela_dias))

    titulos: List[Dict[str, Any]] = []
    pagina = 1
    while True:
        resp = client.chamar(
            "PesquisarLancamentos",
            {
                "nPagina": pagina,
                "nRegPorPagina": 100,
                "cNatureza": "P",
                "cStatus": "EMABERTO",
                "dDtVencDe": d_de,
                "dDtVencAte": d_ate,
            },
        )
        titulos.extend(_extrair_titulos(resp))
        total_paginas = int(resp.get("nTotPaginas") or 1)
        if pagina >= total_paginas:
            break
        pagina += 1
    return titulos


def consultar_nome_fantasia(client: OmieClient, ncod_cliente: int) -> Dict[str, Optional[str]]:
    """Etapa 4: consulta o cliente pelo codigo e devolve nome_fantasia/razao_social."""
    resp = client.chamar("ConsultarCliente", {"codigo_cliente_omie": ncod_cliente})
    return {
        "nome_fantasia": resp.get("nome_fantasia"),
        "razao_social": resp.get("razao_social"),
    }


def casar_debito(
    client: OmieClient,
    valor_debito: Decimal,
    memo: str,
    hoje: Optional[datetime] = None,
    janela_dias: int = JANELA_DIAS,
) -> ResultadoMatch:
    """Executa as 5 etapas para um unico debito. Nao escreve nada.

    valor_debito: valor da transacao (pode vir negativo; usa-se o absoluto).
    memo: MEMO do extrato (usado no teste do nome_fantasia).
    hoje: data de execucao (default: agora). Parametrizavel para testes.
    """
    hoje = hoje or datetime.now()
    alvo = abs(valor_debito)
    trilha: List[str] = []

    # Etapa 2: pesquisar titulos em aberto na janela.
    try:
        titulos = pesquisar_titulos_em_aberto(client, hoje, janela_dias)
    except OmieError as exc:
        return ResultadoMatch(
            status="erro",
            motivo=f"Falha ao pesquisar titulos: {exc}",
            trilha=[f"PesquisarLancamentos falhou: {exc}"],
        )
    d_de = _fmt(hoje - timedelta(days=janela_dias))
    d_ate = _fmt(hoje + timedelta(days=janela_dias))
    trilha.append(
        f"PesquisarLancamentos (P/EMABERTO, venc {d_de}..{d_ate}): "
        f"{len(titulos)} titulo(s)."
    )
    if not titulos:
        return ResultadoMatch(status="manual", motivo="Nenhum titulo em aberto na janela.", trilha=trilha)

    # Etapa 3: filtrar por valor exato (absoluto) via nValorTitulo.
    exatos: List[Dict[str, Any]] = []
    for t in titulos:
        bruto = t.get("nValorTitulo")
        if bruto is None:
            continue
        try:
            v = Decimal(str(bruto))
        except (ArithmeticError, ValueError):
            continue
        if _decimais_iguais(v, alvo):
            exatos.append(t)
    trilha.append(f"Valor exato R$ {alvo:.2f}: {len(exatos)} candidato(s).")
    if not exatos:
        return ResultadoMatch(
            status="manual",
            motivo=f"Nenhum titulo com valor exato R$ {alvo:.2f}.",
            trilha=trilha,
        )

    # Etapas 4 e 5: consultar cliente e testar nome_fantasia no memo.
    memo_lower = (memo or "").lower()
    casados: List[Dict[str, Any]] = []
    for t in exatos:
        ncod_cli = t.get("nCodCliente")
        if not ncod_cli:
            trilha.append("Candidato sem nCodCliente -> ignorado.")
            continue
        try:
            cli = consultar_nome_fantasia(client, int(ncod_cli))
        except OmieError as exc:
            trilha.append(f"ConsultarCliente({ncod_cli}) falhou: {exc}")
            continue
        nome_fant = (cli.get("nome_fantasia") or "").strip()
        if nome_fant and nome_fant.lower() in memo_lower:
            casados.append(
                {
                    "titulo": t,
                    "ncod_cliente": int(ncod_cli),
                    "nome_fantasia": nome_fant,
                    "razao_social": cli.get("razao_social"),
                }
            )
            trilha.append(f"nome_fantasia '{nome_fant}' contido no memo -> CASOU.")
        else:
            trilha.append(
                f"nome_fantasia '{nome_fant or '(vazio)'}' NAO contido no memo."
            )

    if len(casados) == 1:
        c = casados[0]
        t = c["titulo"]
        return ResultadoMatch(
            status="casado",
            motivo="Valor exato + nome_fantasia contido no memo.",
            ncod_titulo=t.get("nCodTitulo"),
            ncod_cliente=c["ncod_cliente"],
            nome_fantasia=c["nome_fantasia"],
            razao_social=c["razao_social"],
            valor_titulo=float(Decimal(str(t.get("nValorTitulo")))),
            trilha=trilha,
            candidatos_valor_exato=len(exatos),
        )
    if len(casados) > 1:
        return ResultadoMatch(
            status="manual",
            motivo=f"Ambiguidade: {len(casados)} titulos casaram (valor + nome).",
            trilha=trilha,
            candidatos_valor_exato=len(exatos),
        )
    return ResultadoMatch(
        status="manual",
        motivo="Nenhum candidato teve nome_fantasia contido no memo.",
        trilha=trilha,
        candidatos_valor_exato=len(exatos),
    )
