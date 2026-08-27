# Análise do OFX de Referência

Análise do arquivo real
[`../arquivos-referencia/Comprovante de Extrato.ofx`](../arquivos-referencia/Comprovante%20de%20Extrato.ofx),
usada para dimensionar o parser e as regras de matching da conciliação.

---

## 1. Origem e cabeçalho

| Item | Valor |
|------|-------|
| Formato | OFX **SGML** (não XML), `VERSION:102` |
| Encoding | `USASCII` / `CHARSET:1252` |
| Instituição | Stone Instituição de Pagamento S.A. (`ORG`), `FID` 197 |
| `BANKID` | 0197 |
| `BRANCHID` | 1 |
| `ACCTID` | 6684788-0 |
| `ACCTTYPE` | CHECKING |
| Moeda | BRL |
| Período (`DTSTART`–`DTEND`) | 24/08/2026 a 27/08/2026 |
| Saldo final (`LEDGERBAL/BALAMT`) | 4258.04 (em `DTASOF` 27/08/2026) |

> **Atenção ao formato SGML:** as tags não têm fechamento (`<TRNAMT>-2331.60`
> sem `</TRNAMT>`), o valor vai até o fim da linha. Um parser de XML estrito
> falha aqui — usar um parser tolerante de OFX (ex.: `ofxparse` em Python) ou
> tratamento linha a linha. Há também tabs e espaços à direita em algumas linhas.

---

## 2. Volume e composição

| Métrica | Quantidade |
|---------|-----------|
| Total de transações (`STMTTRN`) | **129** |
| Créditos (`CREDIT`) | 92 |
| Débitos (`DEBIT`) | 37 |

Composição por tipo de histórico (`MEMO`):

| Padrão de MEMO | Qtde | Natureza provável | Classificação |
|----------------|------|-------------------|---------------|
| `Recebimento vendas - Antecipação` | 64 | Crédito | Recebimento (antecipação de recebíveis de cartão) |
| `... - Transferência \| Pix` | 37 | Crédito **e** débito | Pix recebido (CR) ou pago (DB) |
| `... - Pix \| Maquininha` | 12 | Crédito | Recebimento via Pix na maquininha |
| `... - Pagamento` | 15 | Débito | Pagamento a fornecedor |
| Origem `IFOODCOM ...` | 15 | Crédito | Repasse de marketplace (iFood) via Pix |

> As categorias acima se sobrepõem (ex.: os 15 do iFood estão dentro dos 37
> "Transferência | Pix"). Servem para entender os perfis de linha, não como soma
> exata.

---

## 3. Campos disponíveis por transação

Cada `STMTTRN` traz **apenas**:

- `TRNTYPE` — CREDIT ou DEBIT (só esses dois no arquivo; sem FEE/INT/XFER).
- `DTPOSTED` — data/hora da movimentação (formato `AAAAMMDDHHMMSS`, sem timezone
  nas transações; o cabeçalho usa `[-3:BRT]`).
- `TRNAMT` — valor com sinal (negativo = débito).
- `FITID` — **UUID único por transação** (ex.: `285f55d8-2818-4f5c-ae45-b61536a2770a`).
- `MEMO` — texto livre com nome da contraparte + tipo de operação.

**Não há** `CHECKNUM`, `REFNUM`, `PAYEEID` nem documento fiscal. O único dado
estruturado para casar com o Omie é **valor + data + o texto do MEMO**.

---

## 4. Implicações para idempotência

- O `FITID` é um **UUID único por transação** — é a âncora natural de
  idempotência e rastreio. Ele diferencia com segurança cada linha do extrato,
  **inclusive** transações de mesmo valor ou processadas no mesmo instante (ver
  seção 5). Persistir `FITID` já processado impede baixa duplicada.
- **Único risco a validar:** confirmar se a Stone mantém o mesmo `FITID` ao
  reexportar o mesmo período. Se o UUID for estável entre exportações (esperado),
  o `FITID` sozinho basta. Se for regenerado, adicionar uma chave composta de
  reforço (`DTPOSTED` + `TRNAMT` + hash do `MEMO`).

---

## 5. Implicações para o matching (casos reais observados)

> **Distinção fundamental — dois lados do casamento:**
> O `FITID` identifica unicamente cada **linha do extrato**. Logo, valores
> repetidos e débitos em lote **não** causam ambiguidade na *identificação da
> transação do OFX* nem na idempotência/rastreio — cada linha é inequívoca.
> A ambiguidade, quando ocorre, é do **lado do Omie**: decidir *qual título*
> corresponde a uma linha, já que o `FITID` não existe no lançamento do Omie.

### 5.1 Valores idênticos repetidos
Há valores que se repetem (ex.: `62.09` duas vezes seguidas; `33.44`, `109.90`,
`34.73`, `150.00`, `120.00` várias vezes). Cada uma tem `FITID` próprio, então
**são transações distintas e sem ambiguidade no extrato**. O risco aparece só se
existirem **múltiplos títulos abertos de mesmo valor no Omie** — aí valor + data +
`MEMO` podem não desempatar qual título quitar. Nesse caso: fila de exceção.

### 5.2 Débitos em lote no mesmo instante
Vários débitos compartilham o mesmo `DTPOSTED` (ex.: 21 transferências Pix às
`20260825200432`; pagamentos a fornecedor às `20260827093212`) — processamento em
lote. Novamente, o `FITID` distingue cada débito no extrato sem problema. A
atenção é só na hora de mapear cada débito ao título de contas a pagar correto
quando houver vários candidatos de mesmo valor.

### 5.3 "Recebimento vendas - Antecipação" (64 linhas)
Não têm contraparte identificável (sem CPF/CNPJ, sem nome). São repasses da
adquirente. Provavelmente **não** correspondem 1:1 a um título de contas a
receber no Omie — tendem a ser tratados como recebimento consolidado de cartão ou
lançamento em conta corrente. **Decisão de negócio pendente:** como esses
recebimentos de antecipação estão (ou deveriam estar) representados no Omie?

### 5.4 Repasses de marketplace (iFood, 15 linhas)
Mesma questão da antecipação: são créditos de agregador, sem título individual
por venda. Precisam de uma regra de categorização própria.

### 5.5 Pix com nome de pessoa (Maquininha / Transferência)
Trazem o nome da contraparte no MEMO. Dá para tentar casar com título pelo nome +
valor, mas o nome no MEMO nem sempre bate com o cadastro do cliente/fornecedor no
Omie (grafia, maiúsculas, abreviações).

---

## 6. Mapa de classificação proposto para este extrato

| Linha do OFX | Ação candidata no Omie |
|--------------|------------------------|
| DEBIT `... - Pagamento` | Baixa de conta a pagar (`/financas/contapagar/`) |
| DEBIT `... - Transferência \| Pix` | Baixa de conta a pagar **ou** `IncluirLancCC` se não houver título |
| CREDIT `... - Pix \| Maquininha` (nome pessoa) | Baixa de conta a receber, se houver título correspondente |
| CREDIT `Recebimento vendas - Antecipação` | **Definir**: recebimento consolidado de cartão / lançamento CC |
| CREDIT `IFOODCOM ...` | **Definir**: recebimento de marketplace / lançamento CC |

---

## 7. Perguntas de negócio antes do protótipo

1. Os créditos de **antecipação de vendas** e de **iFood** têm título
   correspondente no Omie, ou entram como lançamento consolidado em conta
   corrente? (Define se são baixa de título ou `IncluirLancCC`.)
2. Os **pagamentos a fornecedor** já existem como contas a pagar no Omie no
   momento da conciliação? (Se sim, é baixa; se não, viraria exceção.)
3. Qual a **conta corrente no Omie** (`nCodCC`) que corresponde a esta conta
   Stone (`ACCTID` 6684788-0)?
4. A Stone **reexporta o mesmo `FITID`** para o mesmo período? (Define a
   estratégia de idempotência.)

---

_Análise elaborada a partir do arquivo de referência real, para documentação
interna do projeto de conciliação._
