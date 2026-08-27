"""Parser tolerante de OFX (SGML).

O OFX da Stone (e da maioria dos bancos BR) e' SGML VERSION:102 -- as tags nao
tem fechamento (ex.: `<TRNAMT>-2331.60` sem `</TRNAMT>`). Um parser XML estrito
falha, entao extraimos os campos por regex, lendo o valor ate o fim da linha.

Sem dependencias externas: usa apenas a stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

# Encodings comuns em OFX brasileiro, na ordem de tentativa.
# UTF-8 vem primeiro (estrito): se o arquivo for realmente UTF-8, decodifica
# corretamente. cp1252/latin-1 nunca falham (aceitam qualquer byte), entao so
# servem de fallback -- se viessem antes, mascarariam um arquivo UTF-8 como
# mojibake (ex.: "Antecipa\u00c3\u00a7\u00c3\u00a3o"). Muitos bancos declaram
# CHARSET:1252 no cabecalho mas gravam o conteudo em UTF-8.
_ENCODINGS = ("utf-8", "cp1252", "latin-1")

# Captura o valor de uma tag SGML: do fim de `<TAG>` ate o proximo `<` ou quebra.
_TAG_RE = r"<{tag}>([^<\r\n]*)"
_STMTTRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S)


@dataclass
class Transacao:
    """Uma movimentacao do extrato, normalizada."""

    fitid: str
    tipo: str  # CREDIT | DEBIT
    valor: Decimal  # com sinal (negativo = debito)
    data_posted: Optional[datetime]
    memo: str
    raw_dtposted: str = ""

    @property
    def is_credito(self) -> bool:
        return self.valor > 0

    @property
    def is_debito(self) -> bool:
        return self.valor < 0


@dataclass
class Extrato:
    """Extrato completo: metadados da conta + transacoes."""

    bankid: Optional[str]
    branchid: Optional[str]
    acctid: Optional[str]
    accttype: Optional[str]
    curdef: Optional[str]
    dt_start: Optional[str]
    dt_end: Optional[str]
    saldo_final: Optional[Decimal]
    transacoes: List[Transacao] = field(default_factory=list)


def _ler_arquivo(caminho: str) -> str:
    """Le o arquivo tentando os encodings tipicos de OFX BR."""
    ultimo_erro: Optional[Exception] = None
    for enc in _ENCODINGS:
        try:
            with open(caminho, encoding=enc) as fh:
                return fh.read()
        except (UnicodeDecodeError, LookupError) as exc:  # pragma: no cover
            ultimo_erro = exc
    raise ValueError(f"Nao foi possivel decodificar {caminho}: {ultimo_erro}")


def _tag(bloco: str, tag: str) -> Optional[str]:
    m = re.search(_TAG_RE.format(tag=tag), bloco)
    return m.group(1).strip() if m else None


def _parse_valor(texto: Optional[str]) -> Decimal:
    if not texto:
        return Decimal("0")
    # OFX usa ponto decimal; remove espacos.
    return Decimal(texto.strip())


def _parse_data(texto: Optional[str]) -> Optional[datetime]:
    """DTPOSTED no formato AAAAMMDDHHMMSS (com sufixo opcional de timezone).

    Remove o sufixo de timezone (ex.: "[-3:BRT]") e mantem apenas os digitos.
    Tenta primeiro data+hora (14 digitos) e depois so a data (8 digitos).
    """
    if not texto:
        return None
    digitos = re.sub(r"\D", "", re.sub(r"\[.*?\]", "", texto))
    if len(digitos) >= 14:
        try:
            return datetime.strptime(digitos[:14], "%Y%m%d%H%M%S")
        except ValueError:
            pass
    if len(digitos) >= 8:
        try:
            return datetime.strptime(digitos[:8], "%Y%m%d")
        except ValueError:
            pass
    return None


def parse_ofx(caminho: str) -> Extrato:
    """Le e normaliza um arquivo OFX, devolvendo um Extrato."""
    raw = _ler_arquivo(caminho)

    extrato = Extrato(
        bankid=_tag(raw, "BANKID"),
        branchid=_tag(raw, "BRANCHID"),
        acctid=_tag(raw, "ACCTID"),
        accttype=_tag(raw, "ACCTTYPE"),
        curdef=_tag(raw, "CURDEF"),
        dt_start=_tag(raw, "DTSTART"),
        dt_end=_tag(raw, "DTEND"),
        saldo_final=_parse_valor(_tag(raw, "BALAMT")) if _tag(raw, "BALAMT") else None,
    )

    for bloco in _STMTTRN_RE.findall(raw):
        fitid = _tag(bloco, "FITID")
        if not fitid:
            # sem FITID nao ha ancora de idempotencia -> ainda registramos, mas
            # sinalizamos com fitid sintetico para nao perder a transacao.
            fitid = f"SEM_FITID:{_tag(bloco, 'DTPOSTED')}:{_tag(bloco, 'TRNAMT')}"
        extrato.transacoes.append(
            Transacao(
                fitid=fitid,
                tipo=(_tag(bloco, "TRNTYPE") or "").upper(),
                valor=_parse_valor(_tag(bloco, "TRNAMT")),
                data_posted=_parse_data(_tag(bloco, "DTPOSTED")),
                memo=_tag(bloco, "MEMO") or "",
                raw_dtposted=_tag(bloco, "DTPOSTED") or "",
            )
        )

    return extrato
