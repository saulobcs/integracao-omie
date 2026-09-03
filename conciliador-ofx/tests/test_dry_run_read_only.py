"""Garantias de seguranca do dry-run: NENHUM servico de escrita e chamado.

Estes testes travam o comportamento "read-only" do dry-run. Se alguem adicionar
um metodo de escrita a allow-list, remover o bloqueio, ou fizer o executor
chamar uma baixa/inclusao, algum teste aqui QUEBRA.

Servicos de escrita monitorados (inclusao/baixa/manutencao):
  LancarPagamento, LancarRecebimento, IncluirLancCC, IncluirContaPagar,
  AlterarContaPagar, ExcluirContaPagar, IncluirCliente, AlterarCliente,
  ExcluirCliente, IncluirLancamento, AlterarLancamento, ExcluirLancamento.

Rodar:
    python3 -m unittest discover -s tests -v
    (a partir de conciliador-ofx/)
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

# Permite importar o pacote `conciliador` rodando de dentro de tests/.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from conciliador.acoes import ExecutorDryRun
from conciliador.config_env import Credenciais
from conciliador.omie_client import (
    METODOS_LEITURA,
    OmieClient,
    OmieMetodoBloqueado,
)
from conciliador.parser_ofx import parse_ofx
from conciliador.regras import MotorDeRegras

# Verbos de escrita que NUNCA podem ser chamados no dry-run.
METODOS_ESCRITA = [
    "LancarPagamento",
    "LancarRecebimento",
    "IncluirLancCC",
    "IncluirContaPagar",
    "AlterarContaPagar",
    "ExcluirContaPagar",
    "IncluirCliente",
    "AlterarCliente",
    "ExcluirCliente",
    "IncluirLancamento",
    "AlterarLancamento",
    "ExcluirLancamento",
    "UpsertCliente",
]

_OFX_STONE = os.path.join(_RAIZ, "..", "arquivos-referencia", "Stone.ofx")
_CONFIG = os.path.join(_RAIZ, "config", "roteamento.json")


class RedeProibida(AssertionError):
    """Levantada se o cliente tentar tocar a rede durante os testes."""


class ClienteEspiao:
    """Substitui o OmieClient real: registra toda chamada e NUNCA usa rede.

    Falha imediatamente se receber um metodo de escrita -- assim, se o executor
    passar a chamar uma baixa/inclusao, o teste quebra em vez de bater na API.
    """

    def __init__(self):
        self.chamadas = []

    def chamar(self, call, param):
        self.chamadas.append(call)
        if call in METODOS_ESCRITA:
            raise RedeProibida(f"Dry-run tentou chamar metodo de ESCRITA: {call}")
        # Respostas simuladas minimas para os metodos de leitura usados.
        if call == "PesquisarLancamentos":
            return {"nPagina": 1, "nTotPaginas": 1, "titulosEncontrados": []}
        if call == "ConsultarCliente":
            return {"nome_fantasia": "", "razao_social": ""}
        return {}


class TestAllowListReadOnly(unittest.TestCase):
    def test_allowlist_nao_contem_metodo_de_escrita(self):
        """A allow-list de leitura nao pode conter nenhum verbo de escrita."""
        for metodo in METODOS_ESCRITA:
            self.assertNotIn(
                metodo,
                METODOS_LEITURA,
                f"{metodo} (escrita) nao pode estar na allow-list de leitura.",
            )

    def test_allowlist_so_tem_consulta_e_pesquisa(self):
        """Todo metodo da allow-list comeca com Pesquisar/Consultar/Listar/Extrato."""
        prefixos_leitura = ("Pesquisar", "Consultar", "Listar", "Extrato")
        for call in METODOS_LEITURA:
            self.assertTrue(
                call.startswith(prefixos_leitura),
                f"{call} nao parece um metodo de leitura.",
            )


class TestClienteBloqueiaEscrita(unittest.TestCase):
    def setUp(self):
        # Credenciais fake: suficientes para passar do guard; a rede nunca e
        # atingida porque o bloqueio ocorre antes.
        self.cli = OmieClient(Credenciais(app_key="k", app_secret="s"), somente_leitura=True)

    def test_escrita_bloqueada_antes_da_rede(self):
        """Qualquer metodo de escrita levanta OmieMetodoBloqueado (sem rede)."""
        for metodo in METODOS_ESCRITA:
            with self.assertRaises(OmieMetodoBloqueado, msg=f"{metodo} deveria ser bloqueado"):
                self.cli.chamar(metodo, {})

    def test_endpoint_de_escrita_tambem_bloqueia(self):
        """Mesmo com somente_leitura=False, _endpoint nao resolve URL de escrita."""
        cli = OmieClient(Credenciais(app_key="k", app_secret="s"), somente_leitura=False)
        for metodo in METODOS_ESCRITA:
            with self.assertRaises(OmieMetodoBloqueado):
                cli._endpoint(metodo)


class TestDryRunCompletoSoLeitura(unittest.TestCase):
    """Roda o dry-run inteiro sobre o Stone.ofx e confirma que so houve leitura."""

    def test_processamento_nao_emite_escrita(self):
        if not os.path.exists(_OFX_STONE):
            self.skipTest("Stone.ofx nao encontrado")

        extrato = parse_ofx(_OFX_STONE)
        motor = MotorDeRegras.de_arquivo(_CONFIG)
        motor.selecionar_origem(extrato)
        espiao = ClienteEspiao()
        executor = ExecutorDryRun(motor.config, motor.origem, {}, client=espiao)

        for t in extrato.transacoes:
            executor.executar(motor.rotear(t))

        # Toda chamada emitida tem de estar na allow-list de leitura.
        for call in espiao.chamadas:
            self.assertIn(
                call,
                METODOS_LEITURA,
                f"Dry-run emitiu call fora da allow-list: {call}",
            )
        # E nenhuma pode ser de escrita.
        escritas = [c for c in espiao.chamadas if c in METODOS_ESCRITA]
        self.assertEqual(escritas, [], f"Dry-run emitiu escrita: {escritas}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
