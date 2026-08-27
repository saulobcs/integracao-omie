# Pendências e Confirmações

Itens em aberto que precisam ser confirmados antes de finalizar a implementação.

---

## P1 — Mapeamento da conta corrente Omie (`nCodCC`)

**Status:** aberto — a confirmar.

Qual conta corrente no Omie (`nCodCC`) corresponde à conta Stone do extrato
(`ACCTID` 6684788-0, banco 0197)? E quais são os `nCodCC` das contas destino de
crédito ("Conta de crédito", "Conta Pix", "Conta iFood")?

- **Impacto:** sem isso, o mapa de configuração em
  [`03-regras-de-roteamento.md`](./03-regras-de-roteamento.md) fica com
  `ncodcc_destino: null`. Necessário para executar `IncluirLancCC`.
- **Como obter:** `ListarContasCorrentes` (`/api/v1/geral/contacorrente/`).

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

**Status:** aberto — confirmar na página logada do serviço.

- `LancarPagamento` (baixa de contas a pagar) e `LancarRecebimento` aceitam um
  **código de integração da baixa** (para correlacionar com o `FITID`)?
- Identificação exata do título na baixa: `codigo_lancamento` (nCodTitulo) vs.
  código de integração.
- `IncluirLancCC`: comportamento ao reenviar um `cCodIntLanc` já usado (erro de
  duplicidade vs. upsert)? Define a força da idempotência server-side.

### P3.1 — Derivação FITID → `cCodIntLanc` (limite de 20 caracteres)

**Status:** aberto — decisão técnica.

O `cCodIntLanc` do `IncluirLancCC` é **string(20)** e **obrigatório**, mas o FITID
da Stone é um **UUID de 36 caracteres** — não cabe direto (ver
[`05-analise-endpoints.md`](./05-analise-endpoints.md), seção 2).

**Proposta:** derivar `cCodIntLanc` de um **hash determinístico** do FITID (ex.:
20 primeiros hex de `sha256(fitid)`), garantindo que o mesmo FITID gere sempre o
mesmo código (idempotência) e caiba em 20 chars. Persistir o vínculo
`FITID ⇄ cCodIntLanc ⇄ nCodLanc/codigo_baixa` na tabela de rastreio.

**A validar:** risco de colisão (desprezível no volume atual) e se 20 hex são
suficientes; se necessário, usar base62 para caber mais entropia em 20 chars.

---

## P4 — Tratamento de transferências Pix de débito (freelancer / motoboy)

**Status:** aberto — definir tratativa para evitar cair no manual.

**Contexto do negócio:** os débitos `... - Transferência | Pix` são, em geral,
**pagamentos a freelancer e motoboy** (mão de obra), e não a fornecedores com
título em contas a pagar.

**Desafio de classificação:** o `MEMO` traz apenas o **nome da pessoa** (ex.:
"MICHELI FERNANDA RIBEIRO DA SILVA - Transferência | Pix"), variável e sem sufixo
padronizado que os diferencie de outras transferências Pix de débito. Casar por
sufixo (` - Transferência | Pix`) não separa "pagamento a motoboy" de outros usos
do mesmo tipo de transação.

**Opções a decidir:**
1. Rotear todo débito `- Transferência | Pix` para uma **conta/categoria de
   pagamento de mão de obra** via `IncluirLancCC` (simples, mas agrupa tudo).
2. Manter uma **lista de nomes conhecidos** (freelancers/motoboys) no mapa de
   configuração para classificar por nome + tipo.
3. Buscar em **contas a pagar** primeiro (caso esses pagamentos sejam
   provisionados como título) e, se não achar, aplicar a regra 1.
4. Deixar no **manual** (comportamento padrão atual) — a ser evitado conforme
   solicitado.

**A definir:** qual das opções (ou combinação) adotar, e se há categoria/conta
específica no Omie para pagamento de mão de obra.

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
