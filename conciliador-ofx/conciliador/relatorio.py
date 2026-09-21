"""Geracao de relatorio do processamento (CSV + JSON) e resumo agregado."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any, Dict, List


def _serial(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    return v


def gerar_resumo(registros: List[Dict[str, Any]]) -> Dict[str, Any]:
    por_rota = Counter(r["rota"] for r in registros)
    por_regra = Counter(r["regra"] or "(sem regra)" for r in registros)
    valor_por_rota: Dict[str, float] = defaultdict(float)
    for r in registros:
        valor_por_rota[r["rota"]] += abs(float(r["valor"]))

    return {
        "total_transacoes": len(registros),
        "por_rota": dict(por_rota),
        "por_regra": dict(por_regra),
        "valor_absoluto_por_rota": {k: round(v, 2) for k, v in valor_por_rota.items()},
        "em_manual": por_rota.get("manual", 0),
    }


def escrever_csv(caminho: str, registros: List[Dict[str, Any]]) -> None:
    campos = [
        "fitid", "data", "tipo", "valor", "memo",
        "rota", "regra", "conta_origem", "conta_destino",
        "acao_omie", "call", "endpoint", "motivo",
    ]
    with open(caminho, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for r in registros:
            w.writerow({c: _serial(r.get(c)) for c in campos})


def escrever_json(caminho: str, registros: List[Dict[str, Any]], resumo: Dict[str, Any]) -> None:
    payload = {"resumo": resumo, "transacoes": registros}
    with open(caminho, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=_serial)


def imprimir_resumo(resumo: Dict[str, Any]) -> None:
    print("\n=== RESUMO DO PROCESSAMENTO (DRY-RUN) ===")
    extrato = resumo.get("extrato", {})
    if extrato:
        conta_origem = extrato.get("conta_origem") or extrato.get("origem_identificada") or "NAO MAPEADA"
        print(f"Conta de origem: {conta_origem} (OFX banco {extrato.get('banco')} / conta {extrato.get('conta')})")
    print(f"Total de transacoes: {resumo['total_transacoes']}")
    print("\nPor rota:")
    for rota, qtd in sorted(resumo["por_rota"].items(), key=lambda x: -x[1]):
        valor = resumo["valor_absoluto_por_rota"].get(rota, 0.0)
        print(f"  {rota:<22} {qtd:>4}  (R$ {valor:,.2f})")
    print("\nPor regra:")
    for regra, qtd in sorted(resumo["por_regra"].items(), key=lambda x: -x[1]):
        print(f"  {regra:<40} {qtd:>4}")
    if resumo["em_manual"]:
        print(f"\n>> {resumo['em_manual']} transacao(oes) exigem tratamento MANUAL.")
    print("=========================================\n")
