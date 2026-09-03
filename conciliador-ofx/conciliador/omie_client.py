"""Cliente HTTP minimo da API Omie (stdlib, sem dependencias externas).

A API Omie e um POST JSON por endpoint, com `call`, `app_key`, `app_secret` e
`param` (array de 1 objeto). Nao ha endpoint de auth separado.

SEGURANCA (dry-run): este cliente e "read-only por padrao". Apenas metodos de
CONSULTA/PESQUISA estao na allow-list `METODOS_LEITURA`. Qualquer `call` fora
dela e recusado com `OmieMetodoBloqueado` -- garante que o dry-run nunca escreve
(nunca baixa titulo, nunca inclui lancamento). Para habilitar escrita, seria
preciso um cliente/config explicito fora do dry-run.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .config_env import Credenciais

# Endpoints (recurso) por metodo de leitura usados no fluxo de conciliacao.
# call -> recurso (path relativo ao base).
METODOS_LEITURA: Dict[str, str] = {
    "PesquisarLancamentos": "financas/pesquisartitulos/",
    "ConsultarCliente": "geral/clientes/",
    "ListarClientes": "geral/clientes/",
    "ListarContasCorrentes": "geral/contacorrente/",
    "ListarCategorias": "geral/categorias/",
    "PesquisarTipoDocumento": "geral/tiposdoc/",
    "ExtratoContaCorrente": "financas/extrato/",
}


class OmieError(Exception):
    """Erro generico de comunicacao/negocio com a API Omie."""


class OmieMetodoBloqueado(OmieError):
    """Metodo (call) fora da allow-list de leitura -- bloqueado no dry-run."""


class OmieFault(OmieError):
    """A API respondeu com faultstring/faultcode (erro de negocio)."""

    def __init__(self, faultcode: str, faultstring: str):
        self.faultcode = faultcode
        self.faultstring = faultstring
        super().__init__(f"[{faultcode}] {faultstring}")


class OmieClient:
    """Cliente read-only da API Omie.

    Parametros:
        cred: credenciais (app_key/app_secret/base).
        somente_leitura: se True (padrao), recusa qualquer `call` que nao esteja
            em METODOS_LEITURA.
        timeout: timeout de rede em segundos.
    """

    def __init__(self, cred: Credenciais, somente_leitura: bool = True, timeout: int = 30):
        self.cred = cred
        self.somente_leitura = somente_leitura
        self.timeout = timeout

    def _endpoint(self, call: str) -> str:
        recurso = METODOS_LEITURA.get(call)
        if recurso is None:
            # Fora da allow-list: so permitido se somente_leitura=False (nao e o
            # caso do dry-run). Sem recurso mapeado, nao sabemos a URL de qq forma.
            raise OmieMetodoBloqueado(
                f"Metodo '{call}' nao esta na allow-list de leitura. "
                f"No dry-run apenas consultas/pesquisas sao permitidas."
            )
        base = self.cred.base.rstrip("/")
        return f"{base}/{recurso}"

    def chamar(self, call: str, param: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma chamada `call` com um unico objeto `param`.

        Retorna o corpo JSON da resposta (dict). Lanca:
            OmieMetodoBloqueado - se o call nao for de leitura (no dry-run);
            OmieFault           - se a resposta trouxer faultstring;
            OmieError           - erros de rede/decodificacao.
        """
        if self.somente_leitura and call not in METODOS_LEITURA:
            raise OmieMetodoBloqueado(
                f"Metodo '{call}' bloqueado: cliente em modo somente-leitura."
            )
        if not self.cred.completo:
            raise OmieError(
                "Credenciais ausentes (OMIE_APP_KEY/OMIE_APP_SECRET). "
                "Preencha o .env (veja .env.example)."
            )

        url = self._endpoint(call)
        corpo = {
            "call": call,
            "app_key": self.cred.app_key,
            "app_secret": self.cred.app_secret,
            "param": [param],
        }
        dados = json.dumps(corpo).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=dados,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                texto = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # A Omie retorna erros de negocio em HTTP != 200 com corpo JSON.
            texto = exc.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            raise OmieError(f"Falha de rede ao chamar {call}: {exc}") from exc

        try:
            resultado = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise OmieError(f"Resposta nao-JSON de {call}: {texto[:200]}") from exc

        if isinstance(resultado, dict) and "faultstring" in resultado:
            raise OmieFault(
                str(resultado.get("faultcode", "")),
                str(resultado.get("faultstring", "")),
            )
        return resultado
