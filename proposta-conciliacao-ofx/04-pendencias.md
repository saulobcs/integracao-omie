# Pendências e Confirmações

Itens que precisam ser confirmados antes de finalizar a implementação.

## Quadro-resumo

| # | Tema | Status |
|---|------|--------|
| P1 | `nCodCC` das contas + categoria | **Parcial** — contas mapeadas; falta `cCodCateg` |
| P2 | Estabilidade do FITID entre reexportações | **Aberto** — validar em teste operacional |
| P3 | Idempotência das operações | **Parcial** — crédito resolvido; baixa a confirmar |
| P3.1 | Derivação FITID → `cCodIntLanc` | **Resolvido** |
| P4 | Débito Pix (mão de obra) | **Parcial** — roteia p/ baixa; falta fallback sem título |
| P5 | Documento de origem (antecipação) | **Aberto** — validação contábil |
| P6 | Estornos de pagamento (crédito) | **Aberto** — sem regra; cai no manual |

---

## P1 — Mapeamento da conta corrente Omie (`nCodCC`)

**Status:** PARCIALMENTE RESOLVIDO — contas mapeadas; falta a categoria (`cCodCateg`).

Os `nCodCC` de origem e destino já estão preenchidos no roteamento do cliente
[`clientes/haru/roteamento.json`](../conciliador-ofx/clientes/haru/roteamento.json):

- **Stone** (origem `9250313570`) → destinos: Stone - Cartão de Crédito
  (`9064882272`), Stone - Débito (`9064886018`), Stone - PIX (`9064890501`),
  iFood (`9078464090`).
- **Sicredi** (origem `9062604986`) → destinos: Sodexo (`9127278683`), Alelo
  (`9127278424`), iFood (`9078464090`), Integralização de Capital (`9081411426`).

**Resíduo (ainda pendente):** todas as regras estão com **`ccodcateg: null`**. A
categoria do lançamento (`detalhes.cCodCateg` do `IncluirLancCC`) ainda não foi
definida por conta destino.

- **Como obter as categorias:** `ListarCategorias` (`/api/v1/geral/categorias/`).

---

## P2 — Estabilidade do `FITID` entre reexportações (Stone)

**Status:** aberto — a confirmar. **Premissa de trabalho:** assumir que o
`FITID` é **o mesmo número** ao reexportar o mesmo período.

A Stone mantém o mesmo `FITID` (UUID) ao exportar novamente o mesmo período, ou
regenera a cada exportação?

- **Se estável (premissa atual):** o `FITID` sozinho garante idempotência e
  rastreio.
- **Se regenerado:** adicionar chave composta de reforço
  (`DTPOSTED` + `TRNAMT` + hash do `MEMO`).
- **Como validar:** exportar o mesmo período duas vezes e comparar os `FITID`.

---

## P3 — Parâmetros de idempotência/identificação nas baixas (API Omie)

**Status:** PARCIALMENTE RESOLVIDO — idempotência do crédito garantida; baixa a confirmar.

- **`IncluirLancCC` (crédito) — RESOLVIDO:** antes de incluir, o conciliador
  consulta `ConsultaLancCC` pelo `cCodIntLanc` derivado do FITID; se já existir,
  **não** reinclui e registra "já existe" (ver `acoes.py`). A idempotência não
  depende mais só do comportamento server-side de `cCodIntLanc` duplicado —
  passou a ser garantida pelo próprio fluxo (consulta-antes-de-incluir).
- **`LancarPagamento` (baixa) — pendente:** confirmar se a baixa aceita um
  **código de integração próprio** (para correlacionar com o FITID). Hoje a
  baixa usa `codigo_lancamento` (nCodTitulo) + `observacao` com o FITID; falta um
  identificador de idempotência da baixa em si.
- **Identificação do título na baixa:** `codigo_lancamento` (nCodTitulo) é o
  usado atualmente.

### P3.1 — Derivação FITID → `cCodIntLanc` (limite de 20 caracteres)

**Status:** RESOLVIDO — implementado no conciliador.

O `cCodIntLanc` do `IncluirLancCC` é **string(20)** e **obrigatório**, mas o FITID
da Stone é um **UUID de 36 caracteres** — não cabe direto (ver
[`05-analise-endpoints.md`](./05-analise-endpoints.md), seção 2).

**Solução implementada:** a função `_derivar_ccodintlanc` em
`conciliador-ofx/conciliador/acoes.py` deriva o `cCodIntLanc` de um **hash
determinístico** do FITID: se o FITID couber em 20 chars, usa ele direto; caso
contrário, usa os **20 primeiros hex de `sha256(fitid)`**. Determinístico → o
mesmo FITID sempre gera o mesmo código (idempotência preservada). O FITID
original é mantido no payload como `fitid_origem` para rastreio.

**A validar (residual):** risco de colisão é desprezível no volume atual; se for
preciso mais entropia em 20 chars, migrar para base62.

---

## P4 — Tratamento de transferências Pix de débito (freelancer / motoboy)

**Status:** DECISÃO PARCIAL — roteado para baixa de conta a pagar; falta o fallback.

**Decisão adotada (opção 3):** o débito `... - Transferência | Pix` é roteado para
**`baixar_conta_pagar`** (ver `clientes/haru/roteamento.json`, regra "Pagamento via PIX
(Transferência)"). O conciliador pesquisa um título a pagar em aberto (venc. hoje
±5 dias) e casa por **valor exato + `nome_fantasia` contido no MEMO**.

**Resíduo (ainda pendente):** quando **não** há título correspondente (caso comum
de mão de obra sem provisionamento), a transação cai em **manual**. Falta decidir
o fallback — por exemplo, rotear para uma **conta/categoria de pagamento de mão de
obra** via `IncluirLancCC` (opção 1 original). Isso depende de existir essa
categoria/conta no Omie.

**Nota:** o mesmo sufixo ` - Transferência | Pix` também aparece em **crédito**
(iFood); o motor separa pelo sinal da transação, então não há conflito entre a
regra de crédito iFood e a de débito.

---

## P6 — Estornos de pagamento (crédito)

**Status:** aberto — descoberto no dry-run. Definir tratativa.

O processamento do OFX de referência encontrou 1 crédito com MEMO
`"CONNECT TELECOMUNICACOES LTDA - Estorno | Pagamento"` — um **estorno** (dinheiro
que voltou de um pagamento). Não casa com nenhuma regra de crédito (não é
antecipação, iFood nem maquininha), então caiu corretamente em **manual**.

**Evidência (dry-run 27/08):** 1 transação em manual, valor R$ 172,43, FITID
próprio — rastreável. Nenhuma regra implementada ainda (decisão de negócio).

**A definir:** como tratar estornos? Opções:
1. Regra própria de crédito → reverter/estornar a baixa do pagamento original
   (idealmente vinculando ao título/baixa que gerou o pagamento).
2. Lançamento de crédito em conta corrente com categoria de estorno.
3. Manter no manual (comportamento atual).

> **Nota técnica de implementação:** o MEMO do estorno é
> `"... - Estorno | Pagamento"` — contém a palavra "Pagamento". Se uma regra de
> estorno for criada, ela precisa vir **antes** de qualquer regra que case
> "Pagamento" e ser específica para crédito, para não ser confundida com a baixa
> de contas a pagar (que é débito). Como estorno é crédito e a baixa é débito, o
> sinal já separa os dois — mas convém validar isso ao configurar.

> Aponta para a necessidade de uma regra para MEMOs que contenham "Estorno".

---

## P5 — Créditos de antecipação e o "documento de origem"

**Status:** observação — validar com a contabilidade.

As boas práticas Omie recomendam que lançamentos derivem de um documento de
origem (ver [`../docs-erp-omie/04-boas-praticas.md`](../docs-erp-omie/04-boas-praticas.md),
seção 4). O roteamento de créditos via `IncluirLancCC` cria lançamentos avulsos
em conta corrente. Confirmar com a contabilidade se esse tratamento é aceitável
para antecipação de vendas / repasses de marketplace, ou se deveria existir um
documento de origem no Omie.

---

_Documento de pendências para documentação interna do projeto de conciliação._
