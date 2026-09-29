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

    # Lista das transacoes que exigem tratamento MANUAL (o que o usuario precisa
    # revisar). So os campos uteis para acao.
    manuais = [
        {
            "data": r.get("data"),
            "tipo": r.get("tipo"),
            "valor": abs(float(r["valor"])),
            "memo": r.get("memo"),
            "motivo": r.get("motivo"),
            "fitid": r.get("fitid"),
        }
        for r in registros
        if r["rota"] == "manual"
    ]

    # Resultado das escritas (modo apply): quantas foram executadas, quantas ja
    # existiam (idempotencia) e quantas falharam. Baseado nos campos que o
    # ExecutorApply grava em cada registro.
    execucao = {"executados": 0, "ja_existentes": 0, "falhas": 0}
    falhas: List[Dict[str, Any]] = []
    houve_apply = False
    for r in registros:
        if "executado" in r:
            houve_apply = True
        pp = r.get("payload_proposto") or {}
        idem = pp.get("idempotencia") if isinstance(pp, dict) else None
        if r.get("executado") is True:
            execucao["executados"] += 1
        elif isinstance(idem, dict) and idem.get("ja_existe"):
            execucao["ja_existentes"] += 1
        elif r.get("erro_execucao"):
            execucao["falhas"] += 1
            falhas.append(
                {
                    "memo": r.get("memo"),
                    "valor": abs(float(r["valor"])),
                    "erro": r.get("erro_execucao"),
                    "fitid": r.get("fitid"),
                }
            )

    resumo = {
        "total_transacoes": len(registros),
        "por_rota": dict(por_rota),
        "por_regra": dict(por_regra),
        "valor_absoluto_por_rota": {k: round(v, 2) for k, v in valor_por_rota.items()},
        "em_manual": por_rota.get("manual", 0),
        "manuais": manuais,
    }
    if houve_apply:
        resumo["execucao"] = execucao
        resumo["falhas"] = falhas
    return resumo


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


def _html_escape(valor: Any) -> str:
    import html

    return html.escape(str(valor if valor is not None else ""))


def escrever_html(caminho: str, registros: List[Dict[str, Any]], resumo: Dict[str, Any]) -> None:
    """Gera um relatorio HTML legivel (resumo + pendencias + transacoes).

    Pensado para o usuario abrir no navegador e entender o que foi feito sem
    precisar de planilha. Sem dependencias: HTML/CSS inline.
    """
    e = _html_escape
    extrato = resumo.get("extrato", {})
    partes: List[str] = []

    partes.append(
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Relatorio de Conciliacao</title><style>"
        "body{font:15px system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#f4f6f8;color:#1f2933}"
        "main{max-width:1000px;margin:32px auto;background:#fff;padding:28px;border-radius:12px;box-shadow:0 2px 14px #0001}"
        "h1{color:#0b5cad;margin-top:0}h2{margin-top:28px;border-bottom:2px solid #eef2f5;padding-bottom:6px}"
        "table{border-collapse:collapse;width:100%;margin-top:10px;font-size:14px}"
        "th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #eef2f5}th{background:#f7fafc}"
        ".kpi{display:inline-block;margin:6px 18px 6px 0}.kpi b{font-size:22px;color:#0b5cad;display:block}"
        ".manual{background:#fff3cd}.falha{background:#ffe7e7}.ok{color:#0a7d33}"
        ".tag{font-size:12px;padding:2px 8px;border-radius:10px;background:#eef4f8}"
        "td.num{text-align:right;font-variant-numeric:tabular-nums}"
        "</style></head><body><main>"
    )

    partes.append("<h1>Relatorio de Conciliacao OFX &rarr; Omie</h1>")
    cliente = resumo.get("cliente", {})
    partes.append(
        "<p>"
        f"<span class='tag'>Modo: {e(resumo.get('modo', '-'))}</span> "
        + (f"<span class='tag'>Cliente: {e(cliente.get('nome'))}</span> " if cliente else "")
        + f"<span class='tag'>Conta: {e(extrato.get('conta_origem') or extrato.get('origem_identificada') or 'nao mapeada')}</span> "
        f"<span class='tag'>Periodo: {e(extrato.get('periodo'))}</span>"
        "</p>"
    )

    # KPIs.
    partes.append("<h2>Resumo</h2><div>")
    partes.append(f"<div class='kpi'><b>{resumo.get('total_transacoes', 0)}</b>transacoes</div>")
    partes.append(f"<div class='kpi'><b>{resumo.get('em_manual', 0)}</b>pendencias manuais</div>")
    execucao = resumo.get("execucao")
    if execucao:
        partes.append(f"<div class='kpi'><b>{execucao['executados']}</b>executados</div>")
        partes.append(f"<div class='kpi'><b>{execucao['ja_existentes']}</b>ja existentes</div>")
        partes.append(f"<div class='kpi'><b>{execucao['falhas']}</b>falhas</div>")
    partes.append("</div>")

    # Por rota.
    partes.append("<h2>Por rota</h2><table><tr><th>Rota</th><th>Qtd</th><th>Valor (R$)</th></tr>")
    for rota, qtd in sorted(resumo.get("por_rota", {}).items(), key=lambda x: -x[1]):
        valor = resumo.get("valor_absoluto_por_rota", {}).get(rota, 0.0)
        partes.append(f"<tr><td>{e(rota)}</td><td class='num'>{qtd}</td><td class='num'>{valor:,.2f}</td></tr>")
    partes.append("</table>")

    # Falhas de execucao (modo apply).
    falhas = resumo.get("falhas", [])
    if falhas:
        partes.append("<h2>Falhas na execucao</h2><table><tr><th>Valor</th><th>Memo</th><th>Erro</th></tr>")
        for f in falhas:
            partes.append(
                f"<tr class='falha'><td class='num'>{f['valor']:,.2f}</td>"
                f"<td>{e(f['memo'])}</td><td>{e(f['erro'])}</td></tr>"
            )
        partes.append("</table>")

    # Pendencias manuais (o que o usuario precisa revisar).
    manuais = resumo.get("manuais", [])
    if manuais:
        partes.append("<h2>Pendencias manuais</h2>")
        partes.append("<table><tr><th>Data</th><th>Tipo</th><th>Valor</th><th>Memo</th><th>Motivo</th></tr>")
        for m in manuais:
            partes.append(
                f"<tr class='manual'><td>{e(m['data'])}</td><td>{e(m['tipo'])}</td>"
                f"<td class='num'>{m['valor']:,.2f}</td><td>{e(m['memo'])}</td><td>{e(m['motivo'])}</td></tr>"
            )
        partes.append("</table>")

    # Detalhe de todas as transacoes.
    partes.append("<h2>Transacoes</h2>")
    partes.append(
        "<table><tr><th>Data</th><th>Tipo</th><th>Valor</th><th>Memo</th>"
        "<th>Rota</th><th>Regra</th><th>Destino</th><th>Acao</th></tr>"
    )
    for r in registros:
        classe = " class='manual'" if r.get("rota") == "manual" else ""
        partes.append(
            f"<tr{classe}><td>{e(r.get('data'))}</td><td>{e(r.get('tipo'))}</td>"
            f"<td class='num'>{abs(float(r.get('valor', 0))):,.2f}</td><td>{e(r.get('memo'))}</td>"
            f"<td>{e(r.get('rota'))}</td><td>{e(r.get('regra'))}</td>"
            f"<td>{e(r.get('conta_destino'))}</td><td>{e(r.get('call'))}</td></tr>"
        )
    partes.append("</table>")

    partes.append("</main></body></html>")
    with open(caminho, "w", encoding="utf-8") as fh:
        fh.write("".join(partes))


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

    # Resultado das escritas (modo apply).
    execucao = resumo.get("execucao")
    if execucao:
        print("\nExecucao (modo apply):")
        print(f"  executados     {execucao['executados']:>4}")
        print(f"  ja existentes  {execucao['ja_existentes']:>4}")
        print(f"  falhas         {execucao['falhas']:>4}")
        for f in resumo.get("falhas", []):
            print(f"    ! FALHA R$ {f['valor']:,.2f} | {f['memo']} | {f['erro']}")

    # Lista acionavel das pendencias manuais.
    manuais = resumo.get("manuais", [])
    if manuais:
        print(f"\n>> {len(manuais)} transacao(oes) exigem tratamento MANUAL:")
        for m in manuais:
            print(f"   - {m['data']} | {m['tipo']} R$ {m['valor']:,.2f} | {m['memo']}")
            print(f"     motivo: {m['motivo']}")
    print("=========================================\n")
