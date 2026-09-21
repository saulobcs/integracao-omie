#!/usr/bin/env python3
"""Interface local, via navegador, do conciliador OFX → Omie.

Não depende de Tkinter: inicia um servidor apenas em 127.0.0.1 e abre o
navegador padrão. A interface expõe somente os modos seguros offline e dry-run.
"""

from __future__ import annotations

import cgi
import html
import os
import tempfile
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from main import _CONFIG_PADRAO, _SAIDA_PADRAO, escrever_csv, escrever_json, processar

_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conciliador OFX → Omie</title><style>
body{margin:0;background:#f4f6f8;color:#1f2933;font:16px system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:760px;margin:40px auto;background:#fff;padding:32px;border-radius:12px;box-shadow:0 2px 14px #0002}
h1{margin-top:0;color:#0b5cad}label{display:block;font-weight:600;margin-top:18px}input,select,button{font:inherit}input,select{box-sizing:border-box;width:100%;padding:10px;margin-top:6px;border:1px solid #aab7c4;border-radius:6px}
button{margin-top:24px;padding:11px 18px;border:0;border-radius:6px;background:#0b5cad;color:#fff;font-weight:700;cursor:pointer}.note{color:#52616b}.warning{background:#fff3cd;padding:12px;border-radius:6px}.result{white-space:pre-wrap;background:#eef4f8;padding:16px;border-radius:6px}.error{background:#ffe7e7;color:#8b1f1f}.files{font-size:.9rem;word-break:break-all}
</style></head><body><main>{conteudo}</main></body></html>"""


def _pagina_inicial(mensagem: str = "") -> bytes:
    aviso = f'<p class="note">{html.escape(mensagem)}</p>' if mensagem else ""
    conteudo = f"""
<h1>Conciliador OFX → Omie</h1>
<p class="note">A interface é local: os dados não saem deste computador, exceto pelas consultas da API no modo dry-run.</p>
<p class="warning"><strong>Segurança:</strong> esta interface oferece apenas os modos offline e dry-run. Ela nunca executa o modo apply.</p>
{aviso}
<form method="post" enctype="multipart/form-data">
  <label>Arquivo OFX<input type="file" name="ofx" accept=".ofx,.OFX" required></label>
  <label>Modo<select name="modo"><option value="offline">Offline — sem acessar a API Omie</option><option value="dry-run">Dry-run — consulta, mas não grava no Omie</option></select></label>
  <button type="submit">Processar extrato</button>
</form>"""
    return _HTML.replace("{conteudo}", conteudo).encode("utf-8")


class Aplicacao(BaseHTTPRequestHandler):
    """Servidor HTTP local para uma única tela de processamento."""

    server_version = "ConciliadorOFX/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        """Evita logs de acesso no terminal do usuário."""

    def _responder(self, corpo: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:  # noqa: N802 - nome exigido pela stdlib
        if urlparse(self.path).path != "/":
            self._responder(_pagina_inicial("Página não encontrada."), 404)
            return
        self._responder(_pagina_inicial())

    def do_POST(self) -> None:  # noqa: N802 - nome exigido pela stdlib
        try:
            formulario = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
            )
            if "ofx" not in formulario or not getattr(formulario["ofx"], "file", None):
                raise ValueError("Selecione um arquivo OFX válido.")
            modo = formulario.getfirst("modo", "offline")
            if modo not in {"offline", "dry-run"}:
                raise ValueError("Modo de execução inválido.")

            arquivo = formulario["ofx"]
            conteudo = arquivo.file.read()
            if not conteudo:
                raise ValueError("O arquivo OFX está vazio.")
            with tempfile.NamedTemporaryFile(suffix=".ofx", delete=False) as temporario:
                temporario.write(conteudo)
                caminho_temporario = temporario.name
            try:
                registros, resumo = processar(caminho_temporario, _CONFIG_PADRAO, modo=modo)
            finally:
                os.unlink(caminho_temporario)

            pasta = Path(_SAIDA_PADRAO)
            pasta.mkdir(parents=True, exist_ok=True)
            instante = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv = pasta / f"conciliacao_{instante}.csv"
            json = pasta / f"conciliacao_{instante}.json"
            escrever_csv(str(csv), registros)
            escrever_json(str(json), registros, resumo)
            extrato = resumo.get("extrato", {})
            rotas = "\n".join(
                f"• {rota}: {quantidade}" for rota, quantidade in sorted(resumo.get("por_rota", {}).items())
            )
            resultado = f"""
<h1>Processamento concluído</h1><div class="result">Modo: {html.escape(resumo.get("modo", modo))}
Conta: {html.escape(str(extrato.get("conta_origem") or extrato.get("origem_identificada") or "não mapeada"))}
Transações: {resumo.get("total_transacoes", 0)}
Pendências manuais: {resumo.get("em_manual", 0)}

Por rota:
{html.escape(rotas)}</div>
<p class="files">Relatórios gravados em:<br>{html.escape(str(csv))}<br>{html.escape(str(json))}</p>
<p><a href="/">Processar outro extrato</a></p>"""
            self._responder(_HTML.replace("{conteudo}", resultado).encode("utf-8"))
        except Exception as exc:
            mensagem = html.escape(str(exc))
            conteudo = f"<h1>Não foi possível processar</h1><p class=\"result error\">{mensagem}</p><p><a href=\"/\">Voltar</a></p>"
            self._responder(_HTML.replace("{conteudo}", conteudo).encode("utf-8"), 400)


def main() -> None:
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Aplicacao)
    url = f"http://127.0.0.1:{servidor.server_port}/"
    print(f"Conciliador disponível em {url}")
    threading.Timer(0.2, webbrowser.open, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
