"""Testes da camada multicliente (perfis, isolamento e credenciais).

Travam o comportamento sensivel de seguranca:
  - so processa OFX de contas que pertencem ao cliente selecionado;
  - caminhos de perfil ficam confinados ao repositorio (sem path traversal);
  - identificadores de cliente sao validados;
  - no modo multicliente, o .env do cliente tem prioridade sobre o ambiente.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from conciliador import perfis
from conciliador.config_env import carregar_credenciais
from conciliador.parser_ofx import Extrato
from conciliador.perfis import PerfilInvalido, carregar_perfil, listar_perfis


def _extrato(bankid, acctid) -> Extrato:
    return Extrato(
        bankid=bankid,
        branchid=None,
        acctid=acctid,
        accttype=None,
        curdef=None,
        dt_start="",
        dt_end="",
        saldo_final=None,
        transacoes=[],
    )


class TestValidacaoDeConta(unittest.TestCase):
    def setUp(self):
        self.haru = carregar_perfil("haru")

    def test_conta_permitida_passa(self):
        # Stone e Sicredi estao no clientes.json do Haru.
        self.haru.validar_extrato(_extrato("0197", "6684788-0"))
        self.haru.validar_extrato(_extrato("748", "2580000000157815"))

    def test_normaliza_zero_a_esquerda_do_banco(self):
        # bankid "197" deve casar com "0197" (lstrip de zeros).
        self.haru.validar_extrato(_extrato("197", "6684788-0"))

    def test_conta_alheia_e_bloqueada(self):
        with self.assertRaises(PerfilInvalido):
            self.haru.validar_extrato(_extrato("0001", "99999-9"))

    def test_conta_certa_banco_errado_e_bloqueada(self):
        # Mesmo numero de conta, banco diferente -> bloqueia.
        with self.assertRaises(PerfilInvalido):
            self.haru.validar_extrato(_extrato("9999", "6684788-0"))


class TestRegistroDeClientes(unittest.TestCase):
    def test_lista_contem_haru(self):
        ids = {p.id for p in listar_perfis()}
        self.assertIn("haru", ids)

    def test_cliente_inexistente(self):
        with self.assertRaises(PerfilInvalido):
            carregar_perfil("naoexiste")

    def _com_registro(self, dados):
        """Aponta o _REGISTRO para um clientes.json temporario."""
        tmp = tempfile.mkdtemp()
        reg = os.path.join(tmp, "clientes.json")
        with open(reg, "w", encoding="utf-8") as fh:
            json.dump(dados, fh)
        return reg

    def test_path_traversal_bloqueado(self):
        # env fora do repositorio deve ser recusado.
        reg = self._com_registro(
            {
                "clientes": [
                    {
                        "id": "x",
                        "nome": "X",
                        "config": "config/roteamento.json",
                        "plano_contas": "../arquivos-referencia/contas-haru.json",
                        "env": "../../../../etc/passwd",
                        "saida": "saida/x",
                    }
                ]
            }
        )
        original = perfis._REGISTRO
        perfis._REGISTRO = reg
        try:
            with self.assertRaises(PerfilInvalido):
                listar_perfis()
        finally:
            perfis._REGISTRO = original

    def test_id_invalido_bloqueado(self):
        # Identificador com caracteres fora de [a-z0-9_-] e recusado.
        reg = self._com_registro(
            {
                "clientes": [
                    {
                        "id": "../evil",
                        "nome": "X",
                        "config": "config/roteamento.json",
                        "plano_contas": "../arquivos-referencia/contas-haru.json",
                        "env": "clientes/x/.env",
                        "saida": "saida/x",
                    }
                ]
            }
        )
        original = perfis._REGISTRO
        perfis._REGISTRO = reg
        try:
            with self.assertRaises(PerfilInvalido):
                listar_perfis()
        finally:
            perfis._REGISTRO = original


class TestPrecedenciaCredenciais(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._env = os.path.join(self._tmp, ".env")
        with open(self._env, "w", encoding="utf-8") as fh:
            fh.write("OMIE_APP_KEY=CHAVE_CLIENTE\nOMIE_APP_SECRET=SEGREDO_CLIENTE\n")
        self._salvo = os.environ.get("OMIE_APP_KEY")

    def tearDown(self):
        if self._salvo is None:
            os.environ.pop("OMIE_APP_KEY", None)
        else:
            os.environ["OMIE_APP_KEY"] = self._salvo

    def test_multicliente_env_do_cliente_vence_ambiente(self):
        # env_path explicito -> a chave do cliente prevalece sobre a global.
        os.environ["OMIE_APP_KEY"] = "CHAVE_GLOBAL"
        cred = carregar_credenciais(self._env)
        self.assertEqual(cred.app_key, "CHAVE_CLIENTE")

    def test_single_ambiente_vence(self):
        # Sem env_path explicito -> ambiente prevalece (override pontual).
        os.environ["OMIE_APP_KEY"] = "CHAVE_GLOBAL"
        cred = carregar_credenciais()
        self.assertEqual(cred.app_key, "CHAVE_GLOBAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
