#!/usr/bin/env python3
"""Conciliador OFX x Omie -- experimento em modo DRY-RUN.

Le um extrato OFX, aplica as regras de roteamento (config/roteamento.json) e
gera um relatorio (CSV + JSON) com as acoes que SERIAM executadas no Omie.
Nao chama a API -- nao requer app_key/app_secret.

Uso:
    python3 main.py \
        --ofx "../arquivos-referencia/Comprovante de Extrato.ofx" \
        --config config/roteamento.json \
        --saida saida

Sem argumentos, usa os caminhos padrao acima.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from conciliador.acoes import ExecutorApply, ExecutorDryRun
from conciliador.config_env import carregar_credenciais
from conciliador.omie_client import OmieClient
from conciliador.parser_ofx import parse_ofx
from conciliador.perfis import PerfilCliente, carregar_perfil
from conciliador.regras import MotorDeRegras
from conciliador.relatorio import (
    escrever_csv,
    escrever_json,
    gerar_resumo,
    imprimir_resumo,
)

_AQUI = os.path.dirname(os.path.abspath(__file__))
_OFX_PADRAO = os.path.join(_AQUI, "..", "arquivos-referencia", "Comprovante de Extrato.ofx")
_CONFIG_PADRAO = os.path.join(_AQUI, "config", "roteamento.json")
_SAIDA_PADRAO = os.path.join(_AQUI, "saida")
_PLANO_CONTAS_PADRAO = os.path.join(_AQUI, "..", "arquivos-referencia", "contas-haru.json")


def carregar_plano_contas(caminho: str) -> Dict[int, str]:
    """Le o contas-haru.json e devolve o mapa nCodCC -> descricao.

    Usado para exibir as contas de origem/destino como '(nCodCC) descricao'.
    Se o arquivo nao existir, devolve mapa vazio (o formato exibira o nome
    da origem ou '?').
    """
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as fh:
        dados = json.load(fh)
    contas = dados.get("ListarContasCorrentes", [])
    return {int(c["nCodCC"]): c.get("descricao", "") for c in contas if "nCodCC" in c}


def _criar_executor(modo: str, config, origem, plano_contas, env_path: str | None = None):
    """Cria o executor conforme o modo.

    - 'offline'  : dry-run sem API (nenhuma chamada; so payload proposto).
    - 'dry-run'  : dry-run com consulta read-only (idempotencia/matching).
    - 'apply'    : EXECUCAO final -- cliente read-write, escreve no Omie.

    Retorna (executor, info_modo) onde info_modo descreve o cliente usado.
    """
    cred = carregar_credenciais(env_path)

    if modo == "offline":
        return ExecutorDryRun(config, origem, plano_contas, client=None), "offline (sem API)"

    if not cred.completo:
        raise SystemExit(
            "Credenciais ausentes: preencha OMIE_APP_KEY/OMIE_APP_SECRET no .env "
            "(veja .env.example) ou use --modo offline."
        )

    if modo == "apply":
        client = OmieClient(cred, somente_leitura=False)
        return ExecutorApply(config, origem, plano_contas, client=client), "apply (EXECUCAO/escrita)"

    # dry-run (padrao): cliente read-only.
    client = OmieClient(cred, somente_leitura=True)
    return ExecutorDryRun(config, origem, plano_contas, client=client), "dry-run (leitura)"


def processar(
    ofx_path: str,
    config_path: str,
    plano_contas_path: str = _PLANO_CONTAS_PADRAO,
    modo: str = "dry-run",
    perfil: PerfilCliente | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    extrato = parse_ofx(ofx_path)
    motor = MotorDeRegras.de_arquivo(config_path)
    origem = motor.selecionar_origem(extrato)
    if perfil is not None:
        # Duplo check obrigatório: antes de carregar credenciais ou consultar a
        # API, confirma que BANKID/ACCTID pertencem ao perfil selecionado.
        perfil.validar_extrato(extrato)
        if origem is None:
            raise ValueError(
                f"BLOQUEADO: a conta do OFX é permitida para {perfil.nome}, mas "
                "não possui regra de roteamento no perfil."
            )
    plano_contas = carregar_plano_contas(plano_contas_path)

    executor, info_modo = _criar_executor(
        modo, motor.config, origem, plano_contas, perfil.env_path if perfil else None
    )

    registros: List[Dict[str, Any]] = []
    for t in extrato.transacoes:
        decisao = motor.rotear(t)
        resultado = executor.executar(decisao)
        registros.append(
            {
                "fitid": t.fitid,
                "data": t.data_posted.strftime("%d/%m/%Y %H:%M:%S") if t.data_posted else "",
                "tipo": t.tipo,
                "valor": float(t.valor),
                "memo": t.memo,
                "rota": resultado["rota"],
                "regra": resultado["regra"],
                "conta_origem": resultado["conta_origem"],
                "conta_destino": resultado["conta_destino"],
                "acao_omie": resultado["acao_omie"],
                "call": resultado["call"],
                "endpoint": resultado["endpoint"],
                "payload_proposto": resultado["payload_proposto"],
                "motivo": resultado["motivo"],
            }
        )
    resumo = gerar_resumo(registros)
    resumo["modo"] = info_modo
    if perfil is not None:
        resumo["cliente"] = {"id": perfil.id, "nome": perfil.nome}
    resumo["extrato"] = {
        "banco": extrato.bankid,
        "conta": extrato.acctid,
        "periodo": f"{extrato.dt_start} a {extrato.dt_end}",
        "saldo_final_ofx": float(extrato.saldo_final) if extrato.saldo_final is not None else None,
        "origem_identificada": origem.get("nome") if origem else None,
        "ncodcc_origem": origem.get("ncodcc_omie") if origem else None,
        "conta_origem": executor.conta_origem,
    }
    return registros, resumo


def main() -> None:
    ap = argparse.ArgumentParser(description="Conciliador OFX x Omie (dry-run)")
    ap.add_argument("--ofx", default=_OFX_PADRAO, help="Caminho do arquivo OFX")
    ap.add_argument("--cliente", required=True, help="Identificador do cliente em clientes/clientes.json")
    ap.add_argument(
        "--modo",
        choices=["dry-run", "apply", "offline"],
        default="dry-run",
        help=(
            "dry-run (padrao): consulta a API (leitura), nao escreve. "
            "apply: EXECUTA as escritas no Omie (requer --confirmar). "
            "offline: nao consulta a API."
        ),
    )
    ap.add_argument(
        "--confirmar",
        metavar="CLIENTE",
        help="Obrigatório no --modo apply: digite o código de confirmação do cliente.",
    )
    args = ap.parse_args()

    # Salvaguarda: apply e um modo de ESCRITA em ambiente real. Exige confirmacao
    # explicita para nao executar por acidente.
    perfil = carregar_perfil(args.cliente)
    if args.modo == "apply" and args.confirmar != perfil.confirmacao_apply:
        raise SystemExit(
            f"MODO APPLY exige --confirmar {perfil.confirmacao_apply}. Este modo "
            "EXECUTA inclusões e baixas reais no Omie."
        )

    registros, resumo = processar(
        args.ofx, perfil.config_path, perfil.plano_contas_path, modo=args.modo, perfil=perfil
    )

    os.makedirs(perfil.saida_path, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(perfil.saida_path, f"conciliacao_{ts}.csv")
    json_path = os.path.join(perfil.saida_path, f"conciliacao_{ts}.json")

    escrever_csv(csv_path, registros)
    escrever_json(json_path, registros, resumo)

    imprimir_resumo(resumo)
    print(f"Modo: {resumo.get('modo')}")
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
