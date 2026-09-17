"""Testes do modo de execucao final (ExecutorApply).

Garante que:
  - ExecutorApply exige um cliente read-write (recusa read-only / None);
  - no modo apply, a escrita (IncluirLancCC / LancarPagamento) e EXECUTADA;
  - a idempotencia e respeitada: credito que ja existe NAO e reincluido;
  - o ExecutorDryRun continua NAO executando escrita (so consulta).

Nenhum teste toca a rede: usa clientes fake.
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from conciliador.acoes import ExecutorApply, ExecutorDryRun
from conciliador.omie_client import OmieFault
from conciliador.parser_ofx import parse_ofx
from conciliador.regras import MotorDeRegras

_OFX = os.path.join(_RAIZ, "..", "arquivos-referencia", "Comprovante de Extrato (8).ofx")
_CONFIG = os.path.join(_RAIZ, "config", "roteamento.json")


class _FakeBase:
    """Base dos fakes: registra os calls emitidos."""

    def __init__(self, somente_leitura):
        self.somente_leitura = somente_leitura
        self.chamadas = []


class FakeRWNaoExiste(_FakeBase):
    """Read-write; credito nao existe -> deve incluir."""

    def __init__(self):
        super().__init__(somente_leitura=False)

    def chamar(self, call, param):
        self.chamadas.append(call)
        if call == "ConsultaLancCC":
            raise OmieFault("x", "nao existe")
        if call == "IncluirLancCC":
            return {"nCodLanc": 999, "cCodIntLanc": param.get("cCodIntLanc"), "cCodStatus": "0"}
        raise AssertionError(f"call inesperado: {call}")


class FakeRWExiste(_FakeBase):
    """Read-write; credito ja existe -> NAO deve incluir."""

    def __init__(self):
        super().__init__(somente_leitura=False)

    def chamar(self, call, param):
        self.chamadas.append(call)
        if call == "ConsultaLancCC":
            return {"nCodLanc": 555}
        raise AssertionError(f"nao deveria chamar {call}")


class FakeRO(_FakeBase):
    """Read-only: idempotencia diz 'nao existe'."""

    def __init__(self):
        super().__init__(somente_leitura=True)

    def chamar(self, call, param):
        self.chamadas.append(call)
        if call == "ConsultaLancCC":
            raise OmieFault("x", "nao existe")
        if call == "PesquisarLancamentos":
            return {"nPagina": 1, "nTotPaginas": 1, "titulosEncontrados": []}
        return {}


def _primeiro_credito(motor, extrato):
    for t in extrato.transacoes:
        if motor.rotear(t).acao == "incluir_lanc_cc":
            return t
    raise AssertionError("nenhum credito no extrato")


class TestApplyExigeReadWrite(unittest.TestCase):
    def _motor(self):
        extrato = parse_ofx(_OFX)
        motor = MotorDeRegras.de_arquivo(_CONFIG)
        motor.selecionar_origem(extrato)
        return motor, extrato

    def test_recusa_cliente_none(self):
        motor, _ = self._motor()
        with self.assertRaises(ValueError):
            ExecutorApply(motor.config, motor.origem, {}, client=None)

    def test_recusa_cliente_read_only(self):
        motor, _ = self._motor()
        with self.assertRaises(ValueError):
            ExecutorApply(motor.config, motor.origem, {}, client=FakeRO())


class TestApplyExecutaEscrita(unittest.TestCase):
    def setUp(self):
        self.extrato = parse_ofx(_OFX)
        self.motor = MotorDeRegras.de_arquivo(_CONFIG)
        self.motor.selecionar_origem(self.extrato)
        self.credito = _primeiro_credito(self.motor, self.extrato)

    def test_apply_inclui_quando_nao_existe(self):
        cli = FakeRWNaoExiste()
        ex = ExecutorApply(self.motor.config, self.motor.origem, {}, client=cli)
        r = ex.executar(self.motor.rotear(self.credito))
        self.assertTrue(r["executado"])
        self.assertEqual(r["resultado_execucao"]["nCodLanc"], 999)
        self.assertIn("IncluirLancCC", cli.chamadas)
        self.assertFalse(r["simulado"])

    def test_apply_nao_inclui_quando_ja_existe(self):
        cli = FakeRWExiste()
        ex = ExecutorApply(self.motor.config, self.motor.origem, {}, client=cli)
        r = ex.executar(self.motor.rotear(self.credito))
        self.assertFalse(r["executado"])
        self.assertNotIn("IncluirLancCC", cli.chamadas)

    def test_dry_run_nao_executa_escrita(self):
        cli = FakeRO()
        ex = ExecutorDryRun(self.motor.config, self.motor.origem, {}, client=cli)
        ex.executar(self.motor.rotear(self.credito))
        # DryRun so consulta (ConsultaLancCC); nunca IncluirLancCC.
        self.assertNotIn("IncluirLancCC", cli.chamadas)


if __name__ == "__main__":
    unittest.main(verbosity=2)
