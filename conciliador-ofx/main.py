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

from conciliador.acoes import ExecutorDryRun
from conciliador.parser_ofx import parse_ofx
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


def processar(
    ofx_path: str,
    config_path: str,
    plano_contas_path: str = _PLANO_CONTAS_PADRAO,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    extrato = parse_ofx(ofx_path)
    motor = MotorDeRegras.de_arquivo(config_path)
    origem = motor.selecionar_origem(extrato)
    plano_contas = carregar_plano_contas(plano_contas_path)
    executor = ExecutorDryRun(motor.config, origem, plano_contas)

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
    ap.add_argument("--config", default=_CONFIG_PADRAO, help="Caminho do JSON de roteamento")
    ap.add_argument("--saida", default=_SAIDA_PADRAO, help="Pasta de saida dos relatorios")
    args = ap.parse_args()

    registros, resumo = processar(args.ofx, args.config)

    os.makedirs(args.saida, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.saida, f"conciliacao_{ts}.csv")
    json_path = os.path.join(args.saida, f"conciliacao_{ts}.json")

    escrever_csv(csv_path, registros)
    escrever_json(json_path, registros, resumo)

    imprimir_resumo(resumo)
    print(f"CSV : {csv_path}")
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
