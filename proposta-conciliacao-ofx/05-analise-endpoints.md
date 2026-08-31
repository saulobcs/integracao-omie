# Análise dos Endpoints Usados no Fluxo

Análise detalhada dos endpoints da API Omie envolvidos na conciliação OFX,
com payload de requisição, resposta e o que **pode** e **não pode** ser feito.

> **Fontes:** documentação interna
> [`../docs-erp-omie/03-modulos-e-servicos.md`](../docs-erp-omie/03-modulos-e-servicos.md)
> (levantada das páginas oficiais) + artigos oficiais da Central de Ajuda Omie.
> Envelope, autenticação e paginação: ver
> [`../docs-erp-omie/02-autenticacao-e-requisicoes.md`](../docs-erp-omie/02-autenticacao-e-requisicoes.md).
>
> **Limitação de coleta:** as páginas de cada serviço no `app.omie.com.br` são
> SPAs (renderizadas em JS) e **não são raspáveis** por fetch. A lista completa e
> literal de parâmetros/tipos de cada `call` só é visível na página logada do
> Portal do Desenvolvedor ("Teste agora mesmo"). Os campos abaixo vêm da doc
> interna + artigos oficiais; itens não confirmados estão sinalizados.

---

## Envelope comum a todos

```json
POST https://app.omie.com.br/api/v1/<modulo>/<recurso>/
Content-Type: application/json

{
  "call": "<Metodo>",
  "app_key": "SEU_APP_KEY",
  "app_secret": "SEU_APP_SECRET",
  "param": [ { ...parametros do metodo... } ]
}
```

- `param` é **sempre um array** com um objeto.
- Erros de negócio podem vir com HTTP != 200 e corpo com `faultstring`/`faultcode`
  → **sempre inspecionar o corpo**, não confiar só no status.

---

## Mapa: qual endpoint para cada rota do conciliador

| Rota do conciliador | Endpoint | `call` | Papel |
|---------------------|----------|--------|-------|
| (setup) mapear conta | `/geral/contacorrente/` | `ListarContasCorrentes` | Descobrir `nCodCC` (pendência P1) |
| (setup) categorias | `/geral/categorias/` | `ListarCategorias` | Descobrir valores válidos de `cCodCateg` |
| (setup) tipos de documento | `/geral/tiposdoc/` | `PesquisarTipoDocumento` | Descobrir valores válidos de `cTipo` (PIX/DIN/BOL/TED...) |
| credito_roteado | `/financas/contacorrentelancamentos/` | `IncluirLancCC` | Lançar crédito na conta destino |
| baixa_conta_pagar (buscar) | `/financas/pesquisartitulos/` | `PesquisarTitulos` | Localizar o título a pagar |
| baixa_conta_pagar (baixar) | `/financas/contapagar/` | `LancarPagamento` | Dar baixa no título |
| (conferência) | `/financas/extrato/` | `ExtratoContaCorrente` | Conferir saldo pós-processamento |

---

## 1. `ListarContasCorrentes` — descobrir os `nCodCC`

**Endpoint:** `/api/v1/geral/contacorrente/` · **Uso:** setup (resolve pendência P1).

### Requisição (param)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `pagina` | integer | Página (inicia em 1) |
| `registros_por_pagina` | integer | ≤ 100 (recomendado) |
| `apenas_importado_api` | string(1) | S/N |

### Resposta (campos-chave por conta)
| Campo | Descrição |
|-------|-----------|
| `nCodCC` | **ID interno da conta corrente** (é o que precisamos) |
| `cCodCCInt` | Código de integração da conta (string 20) |
| `tipo_conta_corrente` | CC/CX/CP/CR... |
| `codigo_banco` | Código do banco (string 3) |
| `descricao` | Descrição da conta (string 40) |
| `numero_conta_corrente` | Número da conta |
| `inativo` | S/N |

### Pode / Não pode
- **Pode:** listar todas as contas e mapear a conta Stone (`ACCTID` 6684788-0) e as
  contas destino (crédito/Pix/iFood) aos seus `nCodCC`.
- **Atenção:** o OFX traz `ACCTID`/`BANKID`, mas o casamento com a conta do Omie
  provavelmente será **manual** (conferindo `numero_conta_corrente`/`descricao`),
  pois o número pode estar formatado diferente. Preenche o mapa de config uma vez.

---

## 1a. `ListarCategorias` — valores válidos de `cCodCateg`

**Endpoint:** `/api/v1/geral/categorias/` · **Uso:** setup (descobrir os códigos de
categoria que vão em `detalhes.cCodCateg` do `IncluirLancCC`).

### Requisição (param)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `pagina` | integer | Página (inicia em 1) |
| `registros_por_pagina` | integer | ≤ 100 (recomendado) |
| `filtrar_apenas_ativas` | string(1) | S/N (opcional) |

### Resposta (campos-chave por categoria)
| Campo | Descrição |
|-------|-----------|
| `codigo` | **Código da categoria (string 20)** — é o valor que vai em `cCodCateg` |
| `descricao` | Descrição da categoria |
| `natureza` | Natureza (receita/despesa...) |
| `tipo_categoria` | Tipo da categoria |
| `codigo_dre` | Conta do DRE associada |
| `conta_inativa` | S/N |

### Pode / Não pode
- **Pode:** listar as categorias disponíveis e escolher o `codigo` correto para
  cada regra de roteamento (preenche os `ccodcateg: null` de
  [`03-regras-de-roteamento.md`](./03-regras-de-roteamento.md)).
- **Atenção:** o campo é opcional no `IncluirLancCC`, mas para categorizar o
  lançamento corretamente o `codigo` precisa existir e estar ativo.

---

## 1b. `PesquisarTipoDocumento` — valores válidos de `cTipo`

**Endpoint:** `/api/v1/geral/tiposdoc/` · **Uso:** setup (descobrir os códigos de
tipo de documento que vão em `detalhes.cTipo` do `IncluirLancCC`).

### Requisição (param)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `filtrar_por_codigo` | string(5) | Opcional — busca direta por código |
| `filtrar_por_descricao` | string | Opcional — busca por descrição |

*(Sem filtro, retorna a lista completa de tipos de documento.)*

### Resposta (campos-chave por tipo)
| Campo | Descrição |
|-------|-----------|
| `codigo` | **Código do tipo de documento (string 5)** — é o valor que vai em `cTipo` (ex.: PIX, DIN, BOL, TED) |
| `descricao` | Descrição do tipo |

### Pode / Não pode
- **Pode:** obter a lista canônica de tipos aceitos e mapear cada regra de crédito
  ao `cTipo` adequado (ex.: crédito Pix → `PIX`).
- **Atenção:** usar sempre o `codigo` retornado por este endpoint; valores
  "chutados" podem ser rejeitados pela Omie.

---

## 2. `IncluirLancCC` — lançar crédito roteado (rota `credito_roteado`)

**Endpoint:** `/api/v1/financas/contacorrentelancamentos/`

### Requisição (param)
| Campo | Tipo | Obrig. | Descrição |
|-------|------|--------|-----------|
| `cCodIntLanc` | **string(20)** | **sim** | **Código de integração do lançamento** — âncora de idempotência |
| `cabecalho.nCodCC` | integer | **sim** | Conta corrente destino (do mapa) |
| `cabecalho.dDtLanc` | date dd/mm/aaaa | sim | Data do lançamento |
| `cabecalho.nValorLanc` | decimal | sim | Valor |
| `detalhes.cCodCateg` | string | — | Categoria Omie |
| `detalhes.cTipo` | string | — | DIN/BOL/TED/PIX... |
| `transferencia.nCodCCDestino` | integer | — | Só p/ transferência entre contas |

### Resposta
| Campo | Descrição |
|-------|-----------|
| `nCodLanc` | ID do lançamento criado |
| `cCodIntLanc` | Eco do código de integração enviado |
| `cCodStatus` / `cDesStatus` | Status da operação |

### Pode / Não pode
- **Pode:** criar um lançamento de crédito na conta destino com um identificador
  próprio (`cCodIntLanc`).
- **PONTO CRÍTICO — limite de 20 caracteres:** `cCodIntLanc` é **string(20)**, mas
  o FITID da Stone é um **UUID de 36 caracteres**. **O FITID não cabe direto.**
  Solução recomendada: gerar um **hash determinístico** do FITID truncado a 20
  chars (ex.: 20 primeiros hex de um SHA-256 do FITID). Determinístico = mesmo
  FITID gera sempre o mesmo `cCodIntLanc` → idempotência server-side preservada.
- **Idempotência server-side:** sendo `cCodIntLanc` obrigatório e único, reenviar
  o mesmo código tende a ser rejeitado pela Omie (a confirmar o comportamento
  exato: erro vs. upsert).
- **Não pode/atenção:** não é baixa de título — é lançamento avulso em conta
  corrente. Ver ressalva de "documento de origem" (pendência P5).

---

## 3. `PesquisarTitulos` — localizar título a pagar (rota `baixa_conta_pagar`)

**Endpoint:** `/api/v1/financas/pesquisartitulos/`

### Requisição (filtros principais)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cNatureza` | string(1) | **P** (pagar) / R (receber) |
| `nValorTitulo` | decimal | Valor do título |
| `dDtVenc` | date | Vencimento |
| `cCPFCNPJCliente` | string | Documento da contraparte |
| `cStatus` | string | EMABERTO/ATRASADO/LIQUIDADO/RECEBIDO... |
| `cTipo`, `cOperacao`, `cChaveNFe` | string | Filtros adicionais |
| `nCodTitulo` / `cCodIntTitulo` | int/string | Busca direta por ID |

### Resposta (por título)
| Campo | Descrição |
|-------|-----------|
| `nCodTitulo` | **ID do título** (usado depois no `LancarPagamento`) |
| `cCodIntTitulo` | Código de integração do título |
| `cStatus` | Situação atual |
| `nValorTitulo` | Valor |
| `dDtVenc` | Vencimento |

### Pode / Não pode
- **Pode:** buscar candidatos a baixa por valor + status EMABERTO/ATRASADO.
- **NÃO PODE (limitação real):** o OFX **não traz CPF/CNPJ nem número de
  documento** — só nome no MEMO. Então a busca fica por **valor + data**, o que
  pode retornar **múltiplos candidatos** (há valores repetidos no extrato). O
  filtro por documento, que seria o mais preciso, não é alimentável pelo OFX.
- **Regra:** achou exatamente 1 título EMABERTO → seguir p/ baixa. 0 ou >1 →
  fila manual.

---

## 4. `LancarPagamento` — baixar título a pagar (rota `baixa_conta_pagar`)

**Endpoint:** `/api/v1/financas/contapagar/`

> **Correção da doc interna:** o método de baixa é **`LancarPagamento`**
> (confirmado no [artigo oficial](https://ajuda.omie.com.br/pt-BR/articles/8257476-baixando-uma-conta-a-pagar-via-api)),
> e **não** um bloco `pagamento` embutido — isso era uma inferência. Simétrico ao
> `LancarRecebimento` das contas a receber.

### Requisição (param — dados mínimos de baixa)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `codigo_lancamento` (nCodTitulo) | integer | Título a baixar (vindo do `PesquisarTitulos`) |
| `codigo_baixa` | — | Identificador da baixa (retorno) |
| `valor` | decimal | Valor pago |
| `data` | date | Data da baixa |
| `id_conta_corrente` | integer | Conta de saída do pagamento |
| `observacao` | string | Texto livre (pode carregar o FITID p/ rastreio) |

*(A lista exata de campos só na página logada — confirmar em P3.)*

### Resposta
| Campo | Descrição |
|-------|-----------|
| `codigo_lancamento` | ID do lançamento/título |
| `codigo_baixa` | **Identificador exclusivo desta baixa** — âncora de rastreio |

### Pode / Não pode
- **Pode:** baixar um título a pagar e obter `codigo_baixa` para rastreio.
- **Atenção — fluxo de aprovação:** o artigo oficial indica que a conta pode ser
  **baixada OU encaminhada para Fluxo de Aprovação** se essa opção estiver
  configurada na conta. Ou seja, a baixa **pode não ser imediata** — tratar esse
  estado na conferência.
- **Idempotência:** confirmar se `LancarPagamento` aceita um código de integração
  da baixa (pendência P3). Se não aceitar, a idempotência depende só da tabela de
  vínculo local (FITID já processado).

---

## 5. `ExtratoContaCorrente` — conferência de saldo (leitura)

**Endpoint:** `/api/v1/financas/extrato/`

### Resposta (campos-chave)
| Campo | Descrição |
|-------|-----------|
| `nCodCC` | Conta consultada |
| `dPeriodoInicial` / `dPeriodoFinal` | Período |
| `nSaldoAnterior` | Saldo no início |
| `nSaldoAtual` | Saldo atual no Omie |
| `nSaldoConciliado` | Saldo conciliado |
| `nSaldoDisponivel` | Saldo disponível |
| `listaMovimentos[]` | Movimentos (`nValorDocumento`, `cSituacao`) |

### Pode / Não pode
- **Pode:** conferir se o `nSaldoAtual` do Omie bate com o `LEDGERBAL` do OFX
  após o processamento — validação de fechamento.
- **NÃO PODE:** este endpoint é **somente leitura**. Não importa extrato, não
  concilia, não cria movimento. É consulta.

---

## Síntese — o que o fluxo pode e não pode fazer via API

### Pode
- Lançar créditos roteados em conta corrente (`IncluirLancCC`) com identificador
  próprio.
- Buscar e baixar títulos a pagar (`PesquisarTitulos` + `LancarPagamento`).
- Conferir saldo final (`ExtratoContaCorrente`).
- Rastrear tudo por `nCodLanc`/`codigo_baixa` + o código de integração enviado.

### Não pode (limitações estruturais)
- **Não** importar o arquivo OFX nem alimentar a tela nativa de Conciliação
  Bancária (não há endpoint).
- **Não** casar títulos por CPF/CNPJ/documento a partir do OFX (o arquivo não traz
  esses dados) — matching fica por valor + data, com ambiguidade em valores
  repetidos.
- **Não** garantir baixa imediata em contas a pagar se houver Fluxo de Aprovação
  configurado.
- **Não** usar o FITID inteiro como código de integração em `IncluirLancCC`
  (limite de 20 chars vs. UUID de 36) — exige hash/derivação.

---

## Pendências que esta análise reforça

- **P1** — obter `nCodCC` via `ListarContasCorrentes`; e resolver os valores de
  `cCodCateg` (via `ListarCategorias`) e `cTipo` (via `PesquisarTipoDocumento`)
  para preencher o mapa de roteamento.
- **P3** — confirmar, na página logada, os campos de idempotência/identificação em
  `IncluirLancCC` (comportamento do `cCodIntLanc` duplicado) e em `LancarPagamento`.
- **Nova sub-pendência (P3.1):** definir a **estratégia de derivação do FITID → 
  `cCodIntLanc`** (hash determinístico de 20 chars) e persistir o vínculo
  FITID ⇄ cCodIntLanc ⇄ nCodLanc/codigo_baixa.

---

_Análise elaborada para documentação interna do projeto de conciliação._
